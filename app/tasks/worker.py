"""Celery tasks."""

import logging
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

from .celery import celery_app
from app.core.config import get_settings
from app.services.ocr.service import OCRService
from app.services.agents import OCRAgent, DecisionAgent
from app.core.models import ExtractionResult
from app.core.validators import validate_invoice
from app.core.metrics import PipelineContext

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.extract_invoice", bind=True, max_retries=2)
def extract_invoice_task(self, file_path: str) -> Dict[str, Any]:
    """Extract invoice data using multi-agent pipeline."""
    settings = get_settings()
    path = Path(file_path)
    ctx = PipelineContext(pipeline_id=str(uuid4())[:8])

    if not path.exists():
        return ExtractionResult(status="error", error="File not found").model_dump()

    with ctx.track("ocr") as step:
        try:
            ocr_result = OCRService().extract_with_fallback(str(path))
            step.provider = ocr_result.provider
            step.confidence = ocr_result.confidence
        except Exception as e:
            return ExtractionResult(
                status="error", error=str(e), pipeline_metrics=ctx.get_summary()
            ).model_dump()

    if not ocr_result.text.strip():
        return ExtractionResult(
            status="error", error="No text extracted", pipeline_metrics=ctx.get_summary()
        ).model_dump()

    with ctx.track("quality") as step:
        quality = OCRAgent().assess_quality(ocr_result)
        step.confidence = quality.confidence

    with ctx.track("extraction") as step:
        try:
            decision = DecisionAgent().decide(ocr_result.text)
            step.confidence = decision.confidence
        except Exception as e:
            return ExtractionResult(
                status="error",
                error=str(e),
                ocr_text=ocr_result.text,
                pipeline_metrics=ctx.get_summary(),
            ).model_dump()

    with ctx.track("validation"):
        validations = validate_invoice(decision.result)

    return ExtractionResult(
        status="ok",
        data=decision.result,
        ocr_text=ocr_result.text,
        validations=validations,
        agent_decision=decision,
        pipeline_metrics=ctx.get_summary(),
    ).model_dump()


@celery_app.task(name="tasks.health_check")
def health_check_task() -> Dict[str, str]:
    return {"status": "ok"}

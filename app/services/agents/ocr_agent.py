"""OCR Agent - Evaluates OCR quality and decides on retry strategy."""

import logging
from typing import Optional

from pydantic_ai import Agent

from app.core.config import get_settings
from app.prompts.ocr_prompts import OCR_QUALITY_SYSTEM_PROMPT, OCR_RETRY_PARAMS
from app.core.models import OCRQualityAssessment, OCRResult

logger = logging.getLogger(__name__)


class OCRAgent:
    """
    Agent 1: OCR Quality Assessment
    
    Evaluates the quality of OCR output and determines if retry is needed.
    """

    def __init__(self):
        self.settings = get_settings()
        self._agent = self._create_agent()

    def _create_agent(self) -> Agent:
        """Create the Pydantic AI agent for OCR quality assessment."""
        model = f"openai:{self.settings.openai_model}"
        
        return Agent(
            model,
            output_type=OCRQualityAssessment,
            system_prompt=OCR_QUALITY_SYSTEM_PROMPT,
        )

    def assess_quality(self, ocr_result: OCRResult) -> OCRQualityAssessment:
        """
        Assess the quality of OCR output.

        Args:
            ocr_result: The OCR extraction result to evaluate

        Returns:
            Quality assessment with retry recommendation
        """
        if not ocr_result.text.strip():
            logger.warning("Empty OCR text - marking as poor quality")
            return OCRQualityAssessment(
                quality="poor",
                confidence=0.0,
                issues=["empty_text"],
                should_retry=True,
                suggested_params={"det_db_thresh": 0.2},
            )

        # Quick heuristic checks before calling LLM
        text = ocr_result.text
        
        # Check for obvious quality issues
        quick_issues = []
        
        # Too short for an invoice
        if len(text) < 50:
            quick_issues.append("text_too_short")
        
        # No numbers (invoices should have amounts)
        if not any(c.isdigit() for c in text):
            quick_issues.append("no_numbers")
        
        # Excessive special characters (garbled text indicator)
        special_ratio = sum(1 for c in text if not c.isalnum() and not c.isspace()) / len(text)
        if special_ratio > 0.3:
            quick_issues.append("excessive_special_chars")

        # If quick checks find issues, skip LLM call
        if len(quick_issues) >= 2:
            logger.info(f"Quick quality check failed: {quick_issues}")
            return OCRQualityAssessment(
                quality="poor",
                confidence=0.3,
                issues=quick_issues,
                should_retry=True,
                suggested_params=self._get_retry_params(quick_issues),
            )

        # Use LLM for detailed assessment
        try:
            result = self._agent.run_sync(
                f"Evaluate this OCR text quality:\n\n{text[:2000]}"  # Limit text length
            )
            assessment = result.output
            
            # Add suggested params if retry needed
            if assessment.should_retry and not assessment.suggested_params:
                assessment.suggested_params = self._get_retry_params(assessment.issues)
            
            logger.info(f"OCR quality: {assessment.quality} (confidence: {assessment.confidence:.2f})")
            return assessment
            
        except Exception as e:
            logger.error(f"OCR Agent error: {e}")
            # Fallback to confidence-based assessment
            return OCRQualityAssessment(
                quality="good" if ocr_result.confidence > 0.7 else "poor",
                confidence=ocr_result.confidence,
                issues=["assessment_failed"],
                should_retry=ocr_result.confidence < 0.5,
            )

    def _get_retry_params(self, issues: list) -> dict:
        """Get suggested OCR parameters based on identified issues."""
        params = {}
        for issue in issues:
            if issue in OCR_RETRY_PARAMS:
                params.update(OCR_RETRY_PARAMS[issue])
        return params if params else {"det_db_thresh": 0.3}

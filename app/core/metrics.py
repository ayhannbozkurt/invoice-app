"""Pipeline metrics for observability."""

import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class StepMetrics:
    """Metrics for a pipeline step."""

    name: str
    started_at: datetime
    duration_ms: Optional[float] = None
    status: str = "running"
    confidence: Optional[float] = None
    provider: Optional[str] = None
    error: Optional[str] = None

    def complete(self, confidence: Optional[float] = None):
        self.duration_ms = (datetime.now() - self.started_at).total_seconds() * 1000
        self.status = "completed"
        self.confidence = confidence

    def fail(self, error: str):
        self.duration_ms = (datetime.now() - self.started_at).total_seconds() * 1000
        self.status = "failed"
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        result = {"name": self.name, "status": self.status}
        if self.duration_ms:
            result["duration_ms"] = round(self.duration_ms, 2)
        if self.confidence:
            result["confidence"] = round(self.confidence, 3)
        if self.provider:
            result["provider"] = self.provider
        if self.error:
            result["error"] = self.error
        return result


@dataclass
class PipelineContext:
    """Tracks pipeline execution metrics."""

    pipeline_id: str
    started_at: datetime = field(default_factory=datetime.now)
    steps: List[StepMetrics] = field(default_factory=list)

    @contextmanager
    def track(self, step_name: str):
        """Track a pipeline step."""
        step = StepMetrics(name=step_name, started_at=datetime.now())
        self.steps.append(step)
        logger.info(f"[{self.pipeline_id}] {step_name}: started")

        try:
            yield step
            if step.status == "running":
                step.complete()
            logger.info(f"[{self.pipeline_id}] {step_name}: done ({step.duration_ms:.0f}ms)")
        except Exception as e:
            step.fail(str(e))
            raise

    def get_summary(self) -> Dict[str, Any]:
        total = sum(s.duration_ms or 0 for s in self.steps)
        return {
            "pipeline_id": self.pipeline_id,
            "total_duration_ms": round(total, 2),
            "steps": [s.to_dict() for s in self.steps],
        }

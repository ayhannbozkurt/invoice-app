"""Celery application configuration."""

from celery import Celery
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "invoice_extraction",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.worker"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max per task
    task_soft_time_limit=240,  # Soft limit at 4 minutes
    worker_prefetch_multiplier=1,  # Process one task at a time (OCR is heavy)
)

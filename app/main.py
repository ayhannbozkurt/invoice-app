"""Invoice Data Extraction API."""

import logging
from pathlib import Path
from uuid import uuid4

from celery.result import AsyncResult
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse

from app.tasks.celery import celery_app
from app.tasks.worker import extract_invoice_task
from app.core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

settings = get_settings()
DATA_DIR = Path(settings.data_dir)
DATA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Invoice Extraction API",
    description="Multi-agent invoice data extraction",
    version="2.0.0",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": "2.0.0"}


@app.post("/invoices", response_class=JSONResponse)
async def create_invoice(file: UploadFile = File(...)) -> JSONResponse:
    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/tiff", "application/pdf"}
    if file.content_type and file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}",
        )

    extension = Path(file.filename or "").suffix or ".bin"
    job_id = str(uuid4())
    file_path = DATA_DIR / f"{job_id}{extension}"

    content = await file.read()
    file_path.write_bytes(content)

    task = extract_invoice_task.delay(str(file_path))

    return JSONResponse({
        "job_id": job_id,
        "task_id": task.id,
        "message": "Invoice queued for processing",
    })


@app.get("/invoices/{task_id}", response_class=JSONResponse)
def get_invoice(task_id: str) -> JSONResponse:
    result = AsyncResult(task_id, app=celery_app)

    if result.state == "PENDING":
        return JSONResponse({"state": "PENDING", "message": "Task is waiting"})

    if result.state == "STARTED":
        return JSONResponse({"state": "STARTED", "message": "Task is processing"})

    if result.state == "FAILURE":
        return JSONResponse(
            status_code=500,
            content={"state": "FAILURE", "error": str(result.info)},
        )

    return JSONResponse({"state": result.state, "result": result.result})


@app.delete("/invoices/{job_id}")
def delete_invoice(job_id: str) -> JSONResponse:
    for ext in [".jpg", ".jpeg", ".png", ".webp", ".tiff", ".bin"]:
        file_path = DATA_DIR / f"{job_id}{ext}"
        if file_path.exists():
            file_path.unlink()
            return JSONResponse({"status": "deleted", "job_id": job_id})

    raise HTTPException(status_code=404, detail="Invoice not found")

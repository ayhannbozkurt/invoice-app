# Invoice Data Extraction System

An intelligent document processing solution using **multi-agent architecture** to extract structured data from invoice images.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Invoice Image                             │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   OCR Provider Chain                             │
│   ┌─────────────────┐    ┌─────────────────┐                    │
│   │   PaddleOCR     │───▶│    EasyOCR      │  ← Auto Fallback   │
│   │   (Primary)     │    │   (Fallback)    │                    │
│   └─────────────────┘    └─────────────────┘                    │
│   • Retry logic with exponential backoff                        │
│   • Confidence-based provider selection                         │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Agent 1: OCR Agent                             │
│   • Quality assessment (heuristic + LLM)                        │
│   • Decides if re-OCR needed                                    │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                Agent 2: Extraction Agent(s)                      │
│   ┌──────────────┐    ┌──────────────┐                         │
│   │   OpenAI     │    │   Ollama     │   ← Parallel Execution  │
│   │  GPT-4o-mini │    │  Llama 3.2   │                         │
│   └──────────────┘    └──────────────┘                         │
│   • Few-shot examples for better accuracy                       │
│   • Turkish + English invoice support                           │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Agent 3: Decision Agent                         │
│   • Compares parallel results                                   │
│   • Heuristic scoring + LLM arbitration                         │
│   • Selects best extraction                                     │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Validation                                  │
│   • Arithmetic checks (qty × price = total)                     │
│   • Tax validation (18% KDV)                                    │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Pipeline Metrics                                │
│   • Step-by-step timing (OCR, Quality, LLM, Validation)         │
│   • Confidence scores per step                                  │
│   • Provider tracking                                           │
└─────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
invoice-app/
├── app/
│   ├── core/              # Settings, models, validators, metrics, retry
│   ├── main.py            # FastAPI endpoints
│   ├── prompts/           # LLM prompts (few-shot examples)
│   ├── services/
│   │   ├── agents/        # OCR, extraction, decision agents
│   │   └── ocr/           # OCR providers + service chain
│   └── tasks/             # Celery app + worker pipeline
├── data/                  # OCR inputs + runtime uploads
├── tests/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## Key Features

| Feature | Description |
|---------|-------------|
| **Multi-Agent Pipeline** | 3 specialized agents for quality, extraction, and decision |
| **OCR Provider Chain** | PaddleOCR + EasyOCR with automatic fallback |
| **Parallel LLM Execution** | OpenAI + Ollama run simultaneously |
| **Few-Shot Learning** | Turkish & English invoice examples for better accuracy |
| **Smart Decision Making** | Heuristic scoring + LLM arbitration for best result |
| **Pipeline Observability** | Step-by-step timing, confidence scores, provider tracking |
| **Type-Safe Config** | Pydantic Settings for environment variables |

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service health check |
| `POST` | `/invoices` | Upload invoice for processing |
| `GET` | `/invoices/{task_id}` | Get extraction result with metrics |
| `DELETE` | `/invoices/{job_id}` | Delete uploaded file |

### Response Example

```json
{
  "status": "ok",
  "data": {
    "general_fields": {
      "invoice_number": "FTR-2024-001",
      "date": "2024-01-15",
      "supplier_name": "ABC Teknoloji A.Ş.",
      "total_amount": 35695.00,
      "currency": "TRY"
    },
    "items": [...]
  },
  "validations": {
    "item_calculations": [...],
    "tax_validation": {...},
    "all_valid": true
  },
  "pipeline_metrics": {
    "pipeline_id": "a1b2c3d4",
    "total_duration_ms": 3690,
    "steps_completed": 4,
    "steps": [
      {"name": "ocr_extraction", "duration_ms": 1250, "confidence": 0.85, "provider": "paddleocr"},
      {"name": "quality_assessment", "duration_ms": 340, "confidence": 0.92},
      {"name": "llm_extraction", "duration_ms": 2100, "confidence": 0.88},
      {"name": "validation", "duration_ms": 15}
    ]
  }
}
```

## Configuration

Environment variables (via `.env` file):

```env
# LLM Provider
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Ollama (for parallel execution)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2

# OCR Settings
OCR_LANG=en
OCR_MAX_RETRIES=3
OCR_PROVIDERS=["paddleocr", "easyocr"]  # Provider priority order
EASYOCR_LANGS=["en", "tr"]
MIN_CONFIDENCE_THRESHOLD=0.7

# Parallel LLM
PARALLEL_LLM_ENABLED=true

# Redis/Celery
REDIS_URL=redis://redis:6379/0
```

## Running Locally

```bash
# Install dependencies
uv sync

# Set PYTHONPATH
export PYTHONPATH=.

# Start Redis
docker run -d -p 6379:6379 redis

# Start Celery worker
uv run celery -A app.tasks.celery worker -l info

# Start API
uv run uvicorn app.main:app --reload

## PDF Support
The system automatically handles PDF files by converting them to images:
- Multi-page PDFs are supported
- Each page is processed individually
- Results are combined with page breaks

## Testing
Run the comprehensive test suite:
```bash
uv run pytest tests/ -v
```
```

## Docker Deployment

```bash
docker compose up --build
```

## OCR Provider Chain

The system uses a provider chain pattern for OCR with automatic fallback:

1. **PaddleOCR (Primary)**: Fast, accurate for most documents
2. **EasyOCR (Fallback)**: Better for some edge cases, different character recognition

Each provider is tried in order until one succeeds with acceptable confidence. If all providers fail, the best result (highest confidence) is returned.

```python
# Manual provider selection
ocr_service.extract_with_specific_provider(
    "invoice.jpg",
    provider_name="easyocr",
    lang="tr"
)
```

## Data Directory Behavior

- `data/` contains OCR input files (sample invoices) and runtime uploads.
- Existing files in `data/` are not processed automatically.
- To process a file, upload via API or call the task with a file path.

### OCR Input Example

```bash
# Upload a local file from data/ for OCR + extraction
curl -F "file=@data/fatura2.jpg" http://localhost:8000/invoices
```

## Few-Shot Learning

The extraction prompts include examples for:
- Turkish B2B invoices (KDV, Fatura format)
- English business invoices (USD, standard format)
- Retail receipts (simplified format)

This improves LLM extraction accuracy by showing expected input/output patterns.

---

**License**: MIT

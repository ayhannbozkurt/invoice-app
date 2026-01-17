"""Pydantic models for invoice extraction system."""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class InvoiceItem(BaseModel):
    """Single line item from an invoice."""

    product_name: Optional[str] = Field(None, description="Product or service name")
    quantity: Optional[float] = Field(None, description="Quantity of items")
    unit_price: Optional[float] = Field(None, description="Price per unit")
    total_price: Optional[float] = Field(None, description="Total price for this line")
    description: Optional[str] = Field(None, description="Additional description")


class InvoiceGeneral(BaseModel):
    """General invoice header fields."""

    invoice_number: Optional[str] = Field(None, description="Invoice number/ID")
    date: Optional[str] = Field(None, description="Invoice date")
    supplier_name: Optional[str] = Field(None, description="Supplier/vendor name")
    total_amount: Optional[float] = Field(None, description="Total invoice amount")
    currency: Optional[str] = Field(None, description="Currency code (TRY, USD, EUR)")


class InvoiceExtraction(BaseModel):
    """Complete invoice extraction result."""

    general_fields: InvoiceGeneral
    items: List[InvoiceItem]


class OCRResult(BaseModel):
    """Result from OCR processing."""

    text: str = Field(..., description="Extracted text from image")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="OCR confidence score")
    language: str = Field(default="unknown", description="Detected language")
    retry_count: int = Field(default=0, description="Number of OCR retries performed")
    provider: str = Field(default="unknown", description="OCR provider used (paddleocr, easyocr)")


class OCRQualityAssessment(BaseModel):
    """OCR Agent's quality assessment result."""

    quality: Literal["good", "poor"] = Field(..., description="Overall quality rating")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in assessment")
    issues: List[str] = Field(default_factory=list, description="Identified issues")
    should_retry: bool = Field(default=False, description="Whether to retry OCR")
    suggested_params: Optional[dict] = Field(None, description="Suggested OCR params for retry")


class AgentDecision(BaseModel):
    """Decision Agent's final selection from parallel LLM results."""

    selected_source: str = Field(..., description="Which LLM result was selected")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in decision")
    reasoning: str = Field(..., description="Why this result was chosen")
    result: InvoiceExtraction = Field(..., description="The selected extraction result")


class ExtractionResult(BaseModel):
    """Complete pipeline result with metadata."""

    status: Literal["ok", "error"] = Field(..., description="Processing status")
    data: Optional[InvoiceExtraction] = Field(None, description="Extracted data")
    ocr_text: Optional[str] = Field(None, description="Raw OCR text")
    validations: Optional[dict] = Field(None, description="Validation results")
    agent_decision: Optional[AgentDecision] = Field(None, description="Decision agent result")
    error: Optional[str] = Field(None, description="Error message if failed")
    pipeline_metrics: Optional[dict] = Field(None, description="Pipeline execution metrics")

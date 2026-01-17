"""Tests for Invoice Extraction API."""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_check(self):
        """Health endpoint returns OK status."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "version": "2.0.0"}


class TestInvoicesEndpoint:
    """Tests for /invoices endpoint."""

    def test_upload_invalid_file_type(self):
        """Reject unsupported file types."""
        response = client.post(
            "/invoices",
            files={"file": ("test.txt", b"content", "text/plain")}
        )
        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]

    # Note: Upload tests for valid files require Redis to be running
    # Run these tests with: docker compose up redis -d && pytest tests/


class TestModelsImport:
    """Test that all models can be imported."""

    def test_import_core_models(self):
        """Core models import successfully."""
        from app.core.models import (
            InvoiceExtraction,
            InvoiceItem,
            InvoiceGeneral,
            OCRResult,
            ExtractionResult,
            AgentDecision,
        )
        assert InvoiceExtraction is not None
        assert OCRResult is not None

    def test_import_prompts(self):
        """Prompts import successfully."""
        from app.prompts import (
            EXTRACTION_SYSTEM_PROMPT,
            EXTRACTION_USER_PROMPT,
            OCR_QUALITY_SYSTEM_PROMPT,
            DECISION_SYSTEM_PROMPT,
        )
        assert EXTRACTION_SYSTEM_PROMPT is not None
        assert len(EXTRACTION_SYSTEM_PROMPT) > 0

    def test_import_services(self):
        """Services import successfully."""
        from app.services import (
            OCRService,
            OCRAgent,
            ExtractionAgent,
            DecisionAgent,
        )
        assert OCRService is not None
        assert DecisionAgent is not None


class TestValidators:
    """Test invoice validation functions."""

    def test_validate_item_calculation_correct(self):
        """Valid item calculation passes."""
        from app.core.validators import validate_item_calculation
        from app.core.models import InvoiceItem

        item = InvoiceItem(
            product_name="Test Product",
            quantity=2,
            unit_price=10.0,
            total_price=20.0,
        )
        result = validate_item_calculation(item, 0)
        assert result["valid"] is True

    def test_validate_item_calculation_incorrect(self):
        """Invalid item calculation fails."""
        from app.core.validators import validate_item_calculation
        from app.core.models import InvoiceItem

        item = InvoiceItem(
            product_name="Test Product",
            quantity=2,
            unit_price=10.0,
            total_price=25.0,  # Wrong: should be 20
        )
        result = validate_item_calculation(item, 0)
        assert result["valid"] is False

    def test_validate_tax_with_kdv(self):
        """Tax validation with 18% KDV."""
        from app.core.validators import validate_tax
        from app.core.models import InvoiceExtraction, InvoiceGeneral, InvoiceItem

        extraction = InvoiceExtraction(
            general_fields=InvoiceGeneral(total_amount=118.0),
            items=[InvoiceItem(total_price=100.0)],
        )
        result = validate_tax(extraction, tax_rate=0.18)
        assert result["valid"] is True
        assert result.get("vat_applied") is True

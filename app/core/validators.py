"""Validation functions for invoice data."""

from typing import Any, Dict, List
from app.core.models import InvoiceExtraction, InvoiceItem


def validate_item_calculation(item: InvoiceItem, index: int) -> Dict[str, Any]:
    """Validate quantity × unit_price = total_price for a single item."""
    if not all([item.quantity, item.unit_price, item.total_price]):
        return {
            "item_index": index,
            "product": item.product_name,
            "valid": True,
            "skipped": True,
            "reason": "Missing required fields for calculation",
        }

    expected = round(item.quantity * item.unit_price, 2)
    actual = round(item.total_price, 2)
    is_valid = abs(expected - actual) < 0.01

    return {
        "item_index": index,
        "product": item.product_name,
        "expected": expected,
        "actual": actual,
        "valid": is_valid,
    }


def validate_tax(data: InvoiceExtraction, tax_rate: float = 0.18) -> Dict[str, Any]:
    """Validate if total includes correct VAT (default 18% KDV for Turkey)."""
    items_total = sum(
        item.total_price for item in data.items if item.total_price is not None
    )

    if items_total <= 0 or not data.general_fields.total_amount:
        return {
            "valid": True,
            "skipped": True,
            "reason": "Insufficient data for tax validation",
        }

    actual_total = data.general_fields.total_amount
    expected_with_tax = round(items_total * (1 + tax_rate), 2)
    tax_diff = abs(expected_with_tax - actual_total)
    no_tax_diff = abs(items_total - actual_total)

    # Check if tax is applied
    if tax_diff < 1:
        return {
            "items_subtotal": items_total,
            "expected_with_tax": expected_with_tax,
            "actual_total": actual_total,
            "tax_rate": tax_rate,
            "vat_applied": True,
            "valid": True,
        }

    # Check if no tax scenario
    if no_tax_diff < 1:
        return {
            "items_subtotal": items_total,
            "actual_total": actual_total,
            "vat_applied": False,
            "valid": True,
        }

    # Mismatch
    return {
        "items_subtotal": items_total,
        "expected_with_tax": expected_with_tax,
        "actual_total": actual_total,
        "tax_rate": tax_rate,
        "valid": False,
        "error": "Total does not match items subtotal with or without tax",
    }


def validate_invoice(data: InvoiceExtraction) -> Dict[str, Any]:
    """Run all validations on invoice extraction result."""
    item_validations = [
        validate_item_calculation(item, i) for i, item in enumerate(data.items)
    ]

    tax_validation = validate_tax(data)

    all_valid = all(v.get("valid", True) for v in item_validations) and tax_validation.get("valid", True)

    return {
        "item_calculations": item_validations,
        "tax_validation": tax_validation,
        "all_valid": all_valid,
    }

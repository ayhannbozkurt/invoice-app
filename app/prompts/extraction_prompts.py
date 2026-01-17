"""Invoice extraction prompt."""

EXTRACTION_SYSTEM_PROMPT = """You are an invoice data extraction expert.

Extract structured data from OCR text:

## Fields to Extract
- invoice_number: Invoice/receipt number
- date: Invoice date (YYYY-MM-DD format)
- supplier_name: Seller/vendor name
- total_amount: Final total (numeric only)
- currency: 3-letter code (TRY, USD, EUR)

## Line Items
For each product/service:
- product_name: Item description
- quantity: Number of units (default: 1)
- unit_price: Price per unit
- total_price: Line total

## Rules
1. Return null for missing fields
2. For TAX invoices: KDV corresponds to VAT
3. Extract numeric values only (no symbols)
4. Dates should be ISO format"""


EXTRACTION_USER_PROMPT = """Extract invoice data from this OCR text:

{ocr_text}

Return structured data with all available fields."""

"""The extraction engine: orchestrates all field extractors.

This is the pure, OCR-backend-agnostic core described in the README. Give
it a list of :class:`~receipt_ocr.models.TextBlock` and it returns a full
:class:`~receipt_ocr.models.ExtractionResult`.
"""

from __future__ import annotations

from receipt_ocr import fields
from receipt_ocr.layout import group_into_lines
from receipt_ocr.models import ExtractionResult, FieldResult, TextBlock


def extract_fields(blocks: list[TextBlock], source: str = "") -> ExtractionResult:
    lines = group_into_lines(blocks)

    currency_result = fields.extract_currency(blocks)
    currency_code = currency_result.value if currency_result else None

    results: dict[str, FieldResult] = {}

    if currency_result is not None:
        results["currency"] = currency_result

    vendor_result = fields.extract_vendor(blocks, lines)
    if vendor_result is not None:
        results["vendor"] = vendor_result

    date_result = fields.extract_date(blocks, locale_currency=currency_code)
    if date_result is not None:
        results["date"] = date_result

    total_result = fields.extract_total(blocks, lines)
    if total_result is not None:
        results["total"] = total_result

    tax_result = fields.extract_tax(blocks, lines)
    if tax_result is not None:
        results["tax"] = tax_result

    results["line_items"] = fields.extract_line_items(blocks, lines)

    return ExtractionResult(fields=results, source=source)

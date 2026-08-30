"""receipt-ocr: extract structured fields from receipt/invoice OCR output.

This package does NOT perform image processing itself for the interesting
part of the pipeline. The field-extraction engine (:mod:`receipt_ocr.engine`)
operates purely on a list of :class:`receipt_ocr.models.TextBlock` objects
(text + bounding box + OCR confidence). OCR backends (:mod:`receipt_ocr.backends`)
are responsible for turning an image into that list.
"""

from receipt_ocr.models import ExtractionResult, FieldResult, LineItem, TextBlock

__all__ = [
    "ExtractionResult",
    "FieldResult",
    "LineItem",
    "TextBlock",
]

__version__ = "0.1.0"

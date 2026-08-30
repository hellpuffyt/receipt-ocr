"""Core data models used across the extraction engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class TextBlock:
    """A single unit of OCR output: recognized text plus its bounding box.

    Coordinates are in an arbitrary but consistent unit (pixels, typically),
    with the origin at the top-left of the image, ``top`` increasing
    downward. ``confidence`` is the OCR engine's own confidence for this
    block, normalized to the 0-100 range (matching Tesseract's convention).
    """

    text: str
    left: float
    top: float
    width: float
    height: float
    confidence: float = 100.0
    page: int = 0
    index: int = 0
    """Position of this block in the original OCR reading order."""

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height

    @property
    def cx(self) -> float:
        return self.left + self.width / 2

    @property
    def cy(self) -> float:
        return self.top + self.height / 2

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
            "confidence": self.confidence,
            "page": self.page,
            "index": self.index,
        }


@dataclass(frozen=True)
class Evidence:
    """A pointer back to the OCR block(s) that produced a field value."""

    text: str
    blocks: tuple[int, ...] = field(default_factory=tuple)
    """Indices (``TextBlock.index``) of the contributing blocks."""
    reason: str = ""
    """Short human-readable explanation of why this value was chosen."""

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "blocks": list(self.blocks), "reason": self.reason}


@dataclass(frozen=True)
class FieldResult:
    """The outcome of extracting a single field: value + confidence + why."""

    name: str
    value: Any
    confidence: float
    evidence: Evidence | None = None

    def to_dict(self) -> dict[str, Any]:
        value = self.value
        if isinstance(value, Decimal):
            value = str(value)
        elif hasattr(value, "to_dict"):
            value = value.to_dict()
        elif isinstance(value, list):
            value = [v.to_dict() if hasattr(v, "to_dict") else v for v in value]
        return {
            "value": value,
            "confidence": round(self.confidence, 4),
            "evidence": self.evidence.to_dict() if self.evidence else None,
        }


@dataclass(frozen=True)
class LineItem:
    """One row of a receipt's itemized line-item table."""

    description: str
    amount: Decimal | None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    line_index: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "amount": str(self.amount) if self.amount is not None else None,
            "quantity": str(self.quantity) if self.quantity is not None else None,
            "unit_price": str(self.unit_price) if self.unit_price is not None else None,
        }


@dataclass
class ExtractionResult:
    """All extracted fields for one receipt/invoice image."""

    fields: dict[str, FieldResult]
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "fields": {name: fr.to_dict() for name, fr in self.fields.items()},
        }

    def review_queue(self, min_confidence: float) -> list[str]:
        """Names of fields whose confidence is below ``min_confidence``."""
        return [
            name
            for name, fr in self.fields.items()
            if fr.confidence < min_confidence
        ]

from __future__ import annotations

from receipt_ocr.models import TextBlock


def make_block(
    text: str,
    left: float,
    top: float,
    width: float = 40.0,
    height: float = 12.0,
    confidence: float = 90.0,
    index: int | None = None,
) -> TextBlock:
    """Convenience constructor for synthetic OCR blocks in tests."""
    return TextBlock(
        text=text,
        left=left,
        top=top,
        width=width,
        height=height,
        confidence=confidence,
        index=index if index is not None else 0,
    )


def make_blocks(rows: list[tuple[str, float, float]], **kwargs: object) -> list[TextBlock]:
    """Build a list of blocks from (text, left, top) tuples, auto-indexing."""
    blocks = []
    for i, (text, left, top) in enumerate(rows):
        blocks.append(
            TextBlock(
                text=text,
                left=left,
                top=top,
                width=kwargs.get("width", 40.0),  # type: ignore[arg-type]
                height=kwargs.get("height", 12.0),  # type: ignore[arg-type]
                confidence=kwargs.get("confidence", 90.0),  # type: ignore[arg-type]
                index=i,
            )
        )
    return blocks

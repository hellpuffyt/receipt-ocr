"""Layout helpers: grouping OCR blocks into lines/rows and page geometry."""

from __future__ import annotations

from dataclasses import dataclass

from receipt_ocr.models import TextBlock


@dataclass(frozen=True)
class Line:
    """A row of blocks that share roughly the same vertical position."""

    blocks: tuple[TextBlock, ...]

    @property
    def top(self) -> float:
        return min(b.top for b in self.blocks)

    @property
    def bottom(self) -> float:
        return max(b.bottom for b in self.blocks)

    @property
    def text(self) -> str:
        return " ".join(b.text for b in sorted(self.blocks, key=lambda b: b.left))


def group_into_lines(blocks: list[TextBlock], tolerance_ratio: float = 0.6) -> list[Line]:
    """Group blocks into lines using vertical (top/center) proximity.

    ``tolerance_ratio`` is multiplied by the median block height to decide
    how close two blocks' vertical centers must be to belong to the same
    line. Blocks are processed in top-to-bottom, then left-to-right order.
    """
    if not blocks:
        return []

    heights = sorted(b.height for b in blocks if b.height > 0)
    median_height = heights[len(heights) // 2] if heights else 10.0
    tolerance = max(median_height * tolerance_ratio, 1.0)

    ordered = sorted(blocks, key=lambda b: (b.cy, b.left))
    lines: list[list[TextBlock]] = []
    for block in ordered:
        placed = False
        for line in lines:
            line_cy = sum(b.cy for b in line) / len(line)
            if abs(block.cy - line_cy) <= tolerance:
                line.append(block)
                placed = True
                break
        if not placed:
            lines.append([block])

    result = [Line(tuple(sorted(line, key=lambda b: b.left))) for line in lines]
    result.sort(key=lambda ln: ln.top)
    return result


def page_bounds(blocks: list[TextBlock]) -> tuple[float, float, float, float]:
    """Return (min_left, min_top, max_right, max_bottom) across all blocks."""
    if not blocks:
        return (0.0, 0.0, 0.0, 0.0)
    return (
        min(b.left for b in blocks),
        min(b.top for b in blocks),
        max(b.right for b in blocks),
        max(b.bottom for b in blocks),
    )


def relative_vertical_position(block: TextBlock, blocks: list[TextBlock]) -> float:
    """0.0 = top of the page, 1.0 = bottom, based on the full block set."""
    _, min_top, _, max_bottom = page_bounds(blocks)
    span = max_bottom - min_top
    if span <= 0:
        return 0.0
    return (block.cy - min_top) / span

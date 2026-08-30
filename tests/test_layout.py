from receipt_ocr.layout import group_into_lines, page_bounds, relative_vertical_position
from tests.conftest import make_block


class TestGroupIntoLines:
    def test_blocks_on_same_row_grouped(self) -> None:
        blocks = [
            make_block("TOTAL", 10, 100, index=0),
            make_block("$42.10", 100, 101, index=1),
        ]
        lines = group_into_lines(blocks)
        assert len(lines) == 1
        assert lines[0].text == "TOTAL $42.10"

    def test_blocks_on_different_rows_separated(self) -> None:
        blocks = [
            make_block("TOTAL", 10, 100, index=0),
            make_block("$42.10", 100, 200, index=1),
        ]
        lines = group_into_lines(blocks)
        assert len(lines) == 2

    def test_empty_input(self) -> None:
        assert group_into_lines([]) == []

    def test_lines_sorted_top_to_bottom(self) -> None:
        blocks = [
            make_block("SECOND", 10, 200, index=0),
            make_block("FIRST", 10, 100, index=1),
        ]
        lines = group_into_lines(blocks)
        assert [ln.text for ln in lines] == ["FIRST", "SECOND"]

    def test_blocks_within_line_sorted_left_to_right(self) -> None:
        blocks = [
            make_block("World", 100, 100, index=0),
            make_block("Hello", 10, 101, index=1),
        ]
        lines = group_into_lines(blocks)
        assert lines[0].text == "Hello World"

    def test_slightly_skewed_row_still_grouped(self) -> None:
        # A couple of pixels of vertical jitter (common in real OCR output)
        # should not split a visual row into two lines.
        blocks = [
            make_block("Qty", 10, 100, height=12, index=0),
            make_block("Item", 60, 103, height=12, index=1),
            make_block("Price", 200, 98, height=12, index=2),
        ]
        lines = group_into_lines(blocks)
        assert len(lines) == 1


class TestPageBounds:
    def test_bounds_of_multiple_blocks(self) -> None:
        blocks = [
            make_block("A", 0, 0, width=10, height=10, index=0),
            make_block("B", 50, 50, width=10, height=10, index=1),
        ]
        left, top, right, bottom = page_bounds(blocks)
        assert (left, top, right, bottom) == (0, 0, 60, 60)

    def test_bounds_of_empty_list(self) -> None:
        assert page_bounds([]) == (0.0, 0.0, 0.0, 0.0)


class TestRelativeVerticalPosition:
    def test_top_block_near_zero(self) -> None:
        blocks = [
            make_block("Top", 0, 0, height=10, index=0),
            make_block("Bottom", 0, 500, height=10, index=1),
        ]
        pos = relative_vertical_position(blocks[0], blocks)
        assert pos < 0.1

    def test_bottom_block_near_one(self) -> None:
        blocks = [
            make_block("Top", 0, 0, height=10, index=0),
            make_block("Bottom", 0, 500, height=10, index=1),
        ]
        pos = relative_vertical_position(blocks[1], blocks)
        assert pos > 0.9

    def test_zero_span_returns_zero(self) -> None:
        blocks = [make_block("Only", 0, 100, height=0, index=0)]
        assert relative_vertical_position(blocks[0], blocks) == 0.0

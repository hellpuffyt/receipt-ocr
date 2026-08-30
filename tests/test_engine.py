from decimal import Decimal
from pathlib import Path

from receipt_ocr.backends import JsonBackend
from receipt_ocr.engine import extract_fields

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "sample_receipt.json"


class TestEngineEndToEnd:
    def test_extracts_all_fields_from_sample_receipt(self) -> None:
        blocks = JsonBackend().extract(SAMPLE)
        result = extract_fields(blocks, source=str(SAMPLE))

        assert result.fields["vendor"].value == "GREENLEAF MARKET"
        assert result.fields["currency"].value == "USD"
        assert str(result.fields["date"].value) == "2024-03-14"
        assert result.fields["total"].value == Decimal("119.55")
        assert result.fields["tax"].value == Decimal("8.86")
        assert len(result.fields["line_items"].value) >= 4

    def test_total_is_not_the_largest_line_item(self) -> None:
        # Regression guard: 89.99 (Olive Oil) is the single largest line
        # item on the sample receipt but is not the total.
        blocks = JsonBackend().extract(SAMPLE)
        result = extract_fields(blocks, source=str(SAMPLE))
        assert result.fields["total"].value != Decimal("89.99")

    def test_review_queue_empty_for_confident_sample(self) -> None:
        blocks = JsonBackend().extract(SAMPLE)
        result = extract_fields(blocks, source=str(SAMPLE))
        assert result.review_queue(min_confidence=0.5) == []

    def test_review_queue_flags_low_confidence_threshold(self) -> None:
        blocks = JsonBackend().extract(SAMPLE)
        result = extract_fields(blocks, source=str(SAMPLE))
        # With a very high bar, at least the weaker fields should show up.
        queue = result.review_queue(min_confidence=0.99)
        assert len(queue) > 0

    def test_to_dict_is_json_serializable(self) -> None:
        import json

        blocks = JsonBackend().extract(SAMPLE)
        result = extract_fields(blocks, source=str(SAMPLE))
        # Decimal/date values are converted to strings by to_dict/default=str.
        json.dumps(result.to_dict(), default=str)

    def test_empty_input_produces_no_crash(self) -> None:
        result = extract_fields([], source="empty")
        assert result.fields["line_items"].value == []
        assert "total" not in result.fields or result.fields["total"] is None

from decimal import Decimal

from receipt_ocr import fields
from receipt_ocr.layout import group_into_lines
from tests.conftest import make_block


def _lines(blocks):  # type: ignore[no-untyped-def]
    return group_into_lines(blocks)


class TestExtractTotal:
    def test_picks_keyword_adjacent_amount_not_largest_number(self) -> None:
        # The largest number on the receipt (89.99, a single expensive item)
        # is NOT the total; the total keyword-adjacent amount (42.10) is.
        blocks = [
            make_block("Olive Oil", 10, 100, index=0),
            make_block("$89.99", 200, 100, index=1),
            make_block("TOTAL", 10, 200, index=2, confidence=97),
            make_block("$42.10", 200, 200, index=3, confidence=95),
        ]
        result = fields.extract_total(blocks, _lines(blocks))
        assert result is not None
        assert result.value == Decimal("42.10")

    def test_prefers_strong_keyword_over_subtotal(self) -> None:
        blocks = [
            make_block("Subtotal", 10, 100, index=0),
            make_block("$100.00", 200, 100, index=1),
            make_block("Grand Total", 10, 150, index=2),
            make_block("$108.00", 200, 150, index=3),
        ]
        result = fields.extract_total(blocks, _lines(blocks))
        assert result is not None
        assert result.value == Decimal("108.00")

    def test_amount_on_next_line_below_keyword(self) -> None:
        blocks = [
            make_block("TOTAL DUE", 10, 100, index=0),
            make_block("$77.50", 10, 120, index=1),
        ]
        result = fields.extract_total(blocks, _lines(blocks))
        assert result is not None
        assert result.value == Decimal("77.50")

    def test_falls_back_to_largest_amount_when_no_keyword(self) -> None:
        blocks = [
            make_block("Item A", 10, 100, index=0),
            make_block("$5.00", 200, 100, index=1),
            make_block("Item B", 10, 120, index=2),
            make_block("$15.00", 200, 120, index=3),
        ]
        result = fields.extract_total(blocks, _lines(blocks))
        assert result is not None
        assert result.value == Decimal("15.00")
        assert result.confidence < 0.4  # honestly low confidence for the guess

    def test_returns_none_when_no_amounts_at_all(self) -> None:
        blocks = [make_block("Thank you for visiting", 10, 100, index=0)]
        result = fields.extract_total(blocks, _lines(blocks))
        assert result is None

    def test_ambiguous_thousands_amount_gets_lower_confidence(self) -> None:
        clean_blocks = [
            make_block("TOTAL", 10, 100, index=0),
            make_block("$42.10", 200, 100, index=1),
        ]
        ambiguous_blocks = [
            make_block("TOTAL", 10, 100, index=0),
            make_block("$1,234", 200, 100, index=1),
        ]
        clean = fields.extract_total(clean_blocks, _lines(clean_blocks))
        ambiguous = fields.extract_total(ambiguous_blocks, _lines(ambiguous_blocks))
        assert clean is not None and ambiguous is not None
        assert ambiguous.confidence < clean.confidence

    def test_subtotal_alone_is_not_mistaken_for_total(self) -> None:
        blocks = [
            make_block("Subtotal", 10, 100, index=0),
            make_block("$100.00", 200, 100, index=1),
        ]
        result = fields.extract_total(blocks, _lines(blocks))
        # No real "total" keyword present -> low-confidence fallback, and it
        # should not report a spuriously high confidence for "subtotal".
        assert result is not None
        assert result.confidence < 0.4


class TestExtractTax:
    def test_finds_tax_by_keyword(self) -> None:
        blocks = [
            make_block("Sales Tax", 10, 100, index=0),
            make_block("$8.86", 200, 100, index=1),
        ]
        result = fields.extract_tax(blocks, _lines(blocks))
        assert result is not None
        assert result.value == Decimal("8.86")

    def test_missing_tax_line_returns_none(self) -> None:
        blocks = [
            make_block("Item", 10, 100, index=0),
            make_block("$5.00", 200, 100, index=1),
            make_block("TOTAL", 10, 150, index=2),
            make_block("$5.00", 200, 150, index=3),
        ]
        result = fields.extract_tax(blocks, _lines(blocks))
        assert result is None

    def test_vat_keyword_recognized(self) -> None:
        blocks = [
            make_block("VAT", 10, 100, index=0),
            make_block("EUR 4.20", 200, 100, index=1),
        ]
        result = fields.extract_tax(blocks, _lines(blocks))
        assert result is not None
        assert result.value == Decimal("4.20")

    def test_tax_id_label_not_confused_with_tax_amount(self) -> None:
        blocks = [
            make_block("Tax ID: 998877", 10, 100, index=0),
            make_block("Item", 10, 120, index=1),
            make_block("$5.00", 200, 120, index=2),
        ]
        result = fields.extract_tax(blocks, _lines(blocks))
        assert result is None

    def test_gst_keyword_recognized(self) -> None:
        blocks = [
            make_block("GST", 10, 100, index=0),
            make_block("$3.30", 200, 100, index=1),
        ]
        result = fields.extract_tax(blocks, _lines(blocks))
        assert result is not None
        assert result.value == Decimal("3.30")


class TestExtractVendor:
    def test_picks_largest_top_line(self) -> None:
        blocks = [
            make_block("GREENLEAF MARKET", 10, 10, height=22, index=0),
            make_block("123 Baker Street", 10, 40, height=10, index=1),
            make_block("Springfield", 10, 55, height=10, index=2),
        ]
        result = fields.extract_vendor(blocks, _lines(blocks))
        assert result is not None
        assert result.value == "GREENLEAF MARKET"

    def test_skips_phone_numbers(self) -> None:
        blocks = [
            make_block("555-123-4567", 10, 10, height=20, index=0),
            make_block("CORNER CAFE", 10, 40, height=14, index=1),
        ]
        result = fields.extract_vendor(blocks, _lines(blocks))
        assert result is not None
        assert result.value == "CORNER CAFE"

    def test_skips_receipt_header_word(self) -> None:
        blocks = [
            make_block("RECEIPT", 10, 10, height=20, index=0),
            make_block("CORNER CAFE", 10, 40, height=14, index=1),
        ]
        result = fields.extract_vendor(blocks, _lines(blocks))
        assert result is not None
        assert result.value == "CORNER CAFE"

    def test_skips_date_line(self) -> None:
        blocks = [
            make_block("14/03/2024", 10, 10, height=20, index=0),
            make_block("CORNER CAFE", 10, 40, height=14, index=1),
        ]
        result = fields.extract_vendor(blocks, _lines(blocks))
        assert result is not None
        assert result.value == "CORNER CAFE"

    def test_merges_two_line_business_name(self) -> None:
        blocks = [
            make_block("GREENLEAF", 10, 10, height=20, index=0),
            make_block("MARKET", 10, 34, height=20, index=1),
            make_block("123 Baker Street", 10, 60, height=10, index=2),
        ]
        result = fields.extract_vendor(blocks, _lines(blocks))
        assert result is not None
        assert result.value == "GREENLEAF MARKET"

    def test_empty_blocks_returns_none(self) -> None:
        assert fields.extract_vendor([], []) is None


class TestExtractCurrency:
    def test_detects_usd(self) -> None:
        blocks = [make_block("$42.10", 10, 10, index=0)]
        result = fields.extract_currency(blocks)
        assert result is not None
        assert result.value == "USD"

    def test_detects_eur_by_majority(self) -> None:
        blocks = [
            make_block("€10.00", 10, 10, index=0),
            make_block("€5.00", 10, 30, index=1),
            make_block("$3.00", 10, 50, index=2),
        ]
        result = fields.extract_currency(blocks)
        assert result is not None
        assert result.value == "EUR"

    def test_no_currency_found(self) -> None:
        blocks = [make_block("42.10", 10, 10, index=0)]
        result = fields.extract_currency(blocks)
        assert result is not None
        assert result.value is None
        assert result.confidence == 0.0

    def test_detects_iso_code(self) -> None:
        blocks = [make_block("Total GBP 20.00", 10, 10, index=0)]
        result = fields.extract_currency(blocks)
        assert result is not None
        assert result.value == "GBP"


class TestExtractDateField:
    def test_finds_date_among_blocks(self) -> None:
        blocks = [
            make_block("Date:", 10, 10, index=0),
            make_block("14/03/2024", 60, 10, index=1),
        ]
        result = fields.extract_date(blocks, locale_currency=None)
        assert result is not None
        assert str(result.value) == "2024-03-14"

    def test_no_date_present(self) -> None:
        blocks = [make_block("Thank you", 10, 10, index=0)]
        result = fields.extract_date(blocks, locale_currency=None)
        assert result is None

    def test_ambiguous_date_lower_confidence(self) -> None:
        unambiguous_blocks = [make_block("25/03/2024", 10, 10, index=0)]
        ambiguous_blocks = [make_block("03/04/2024", 10, 10, index=0)]
        unambiguous = fields.extract_date(unambiguous_blocks, locale_currency=None)
        ambiguous = fields.extract_date(ambiguous_blocks, locale_currency=None)
        assert unambiguous is not None and ambiguous is not None
        assert ambiguous.confidence < unambiguous.confidence

    def test_locale_hint_changes_ambiguous_result(self) -> None:
        blocks = [make_block("03/04/2024", 10, 10, index=0)]
        us_result = fields.extract_date(blocks, locale_currency="USD")
        eu_result = fields.extract_date(blocks, locale_currency="EUR")
        assert us_result is not None and eu_result is not None
        assert str(us_result.value) == "2024-03-04"
        assert str(eu_result.value) == "2024-04-03"


class TestExtractLineItems:
    def test_extracts_simple_items(self) -> None:
        blocks = [
            make_block("Header Store", 10, 10, index=0),
            make_block("Apples", 10, 50, index=1),
            make_block("$6.50", 200, 50, index=2),
            make_block("Bread", 10, 70, index=3),
            make_block("$4.20", 200, 70, index=4),
            make_block("TOTAL", 10, 100, index=5),
            make_block("$10.70", 200, 100, index=6),
        ]
        result = fields.extract_line_items(blocks, _lines(blocks))
        descriptions = [item.description for item in result.value]
        assert "Apples" in descriptions
        assert "Bread" in descriptions

    def test_excludes_total_and_tax_lines(self) -> None:
        blocks = [
            make_block("Header Store", 10, 10, index=0),
            make_block("Apples", 10, 50, index=1),
            make_block("$6.50", 200, 50, index=2),
            make_block("Subtotal", 10, 70, index=3),
            make_block("$6.50", 200, 70, index=4),
            make_block("Tax", 10, 90, index=5),
            make_block("$0.50", 200, 90, index=6),
            make_block("TOTAL", 10, 110, index=7),
            make_block("$7.00", 200, 110, index=8),
        ]
        result = fields.extract_line_items(blocks, _lines(blocks))
        descriptions = [item.description for item in result.value]
        assert descriptions == ["Apples"]

    def test_excludes_reference_numbers(self) -> None:
        blocks = [
            make_block("Header Store", 10, 10, index=0),
            make_block("Receipt #4471", 10, 30, index=1),
            make_block("Apples", 10, 50, index=2),
            make_block("$6.50", 200, 50, index=3),
        ]
        result = fields.extract_line_items(blocks, _lines(blocks))
        descriptions = [item.description for item in result.value]
        assert "Receipt #4471" not in descriptions
        assert descriptions == ["Apples"]

    def test_detects_quantity_and_unit_price(self) -> None:
        blocks = [
            make_block("Header Store", 10, 10, index=0),
            make_block("2", 10, 50, width=10, index=1),
            make_block("x", 25, 50, width=10, index=2),
            make_block("Eggs", 40, 50, index=3),
            make_block("$5.00", 200, 50, index=4),
            make_block("$10.00", 260, 50, index=5),
        ]
        result = fields.extract_line_items(blocks, _lines(blocks))
        assert len(result.value) == 1
        item = result.value[0]
        assert item.amount == Decimal("10.00")
        assert item.quantity == Decimal("2")
        assert item.unit_price == Decimal("5.00")

    def test_empty_receipt_returns_empty_list(self) -> None:
        blocks = [make_block("Thank you", 10, 10, index=0)]
        result = fields.extract_line_items(blocks, _lines(blocks))
        assert result.value == []
        assert result.confidence == 0.0

    def test_excludes_phone_and_address_lines(self) -> None:
        blocks = [
            make_block("Header Store", 10, 10, index=0),
            make_block("555-123-4567", 10, 30, index=1),
            make_block("123 Main Street", 10, 50, index=2),
            make_block("Apples", 10, 70, index=3),
            make_block("$6.50", 200, 70, index=4),
        ]
        result = fields.extract_line_items(blocks, _lines(blocks))
        descriptions = [item.description for item in result.value]
        assert descriptions == ["Apples"]

    def test_bare_integer_not_treated_as_price(self) -> None:
        # A row with only a bare integer (no decimal, no currency marker)
        # should not be picked up as a priced line item.
        blocks = [
            make_block("Header Store", 10, 10, index=0),
            make_block("Table 12", 10, 50, index=1),
        ]
        result = fields.extract_line_items(blocks, _lines(blocks))
        assert result.value == []


class TestNoisyOcr:
    def test_extracts_total_despite_noisy_surrounding_text(self) -> None:
        blocks = [
            make_block("T0TAL", 10, 100, index=0, confidence=55),  # noisy OCR of "TOTAL"
            make_block("$42.10", 200, 100, index=1, confidence=60),
        ]
        # A noisy keyword like "T0TAL" won't match our keyword regex, so this
        # should fall back to the low-confidence largest-amount heuristic.
        result = fields.extract_total(blocks, _lines(blocks))
        assert result is not None
        assert result.value == Decimal("42.10")
        assert result.confidence < 0.4

    def test_low_confidence_ocr_block_lowers_field_confidence(self) -> None:
        high_conf_blocks = [
            make_block("TOTAL", 10, 100, index=0, confidence=95),
            make_block("$42.10", 200, 100, index=1, confidence=95),
        ]
        low_conf_blocks = [
            make_block("TOTAL", 10, 100, index=0, confidence=95),
            make_block("$42.10", 200, 100, index=1, confidence=20),
        ]
        high = fields.extract_total(high_conf_blocks, _lines(high_conf_blocks))
        low = fields.extract_total(low_conf_blocks, _lines(low_conf_blocks))
        assert high is not None and low is not None
        assert low.confidence < high.confidence

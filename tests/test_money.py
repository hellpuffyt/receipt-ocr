from decimal import Decimal

from receipt_ocr.money import (
    find_amounts,
    find_currency,
    is_ambiguous_thousands,
    normalize_number,
)


class TestNormalizeNumber:
    def test_plain_integer(self) -> None:
        assert normalize_number("42") == Decimal("42")

    def test_plain_decimal_us(self) -> None:
        assert normalize_number("42.10") == Decimal("42.10")

    def test_plain_decimal_european(self) -> None:
        assert normalize_number("42,10") == Decimal("42.10")

    def test_us_thousands_and_decimal(self) -> None:
        assert normalize_number("1,234.56") == Decimal("1234.56")

    def test_european_thousands_and_decimal(self) -> None:
        assert normalize_number("1.234,56") == Decimal("1234.56")

    def test_space_grouped_european(self) -> None:
        assert normalize_number("1 234,56") == Decimal("1234.56")

    def test_negative_amount(self) -> None:
        assert normalize_number("-12.50") == Decimal("-12.50")

    def test_single_comma_two_decimals_treated_as_decimal(self) -> None:
        assert normalize_number("12,50") == Decimal("12.50")

    def test_single_dot_two_decimals_treated_as_decimal(self) -> None:
        assert normalize_number("12.50") == Decimal("12.50")

    def test_single_separator_three_digits_treated_as_thousands(self) -> None:
        # Ambiguous, but the standard convention treats "1,234" as 1234.
        assert normalize_number("1,234") == Decimal("1234")

    def test_single_dot_three_digits_treated_as_thousands(self) -> None:
        assert normalize_number("1.234") == Decimal("1234")

    def test_one_decimal_digit(self) -> None:
        assert normalize_number("12.5") == Decimal("12.5")

    def test_empty_string_returns_none(self) -> None:
        assert normalize_number("") is None

    def test_garbage_returns_none(self) -> None:
        assert normalize_number("abc") is None

    def test_large_thousands_grouping(self) -> None:
        assert normalize_number("12,345,678.90") == Decimal("12345678.90")

    def test_large_european_grouping(self) -> None:
        assert normalize_number("12.345.678,90") == Decimal("12345678.90")


class TestAmbiguousThousands:
    def test_flagged_for_three_trailing_digits(self) -> None:
        assert is_ambiguous_thousands("1,234") is True

    def test_not_flagged_for_two_trailing_digits(self) -> None:
        assert is_ambiguous_thousands("12.50") is False

    def test_not_flagged_with_no_separator(self) -> None:
        assert is_ambiguous_thousands("1234") is False

    def test_not_flagged_with_two_distinct_separators(self) -> None:
        assert is_ambiguous_thousands("1,234.56") is False


class TestFindAmounts:
    def test_finds_single_amount(self) -> None:
        results = find_amounts("Total: $42.10")
        values = [v for _, v in results]
        assert Decimal("42.10") in values

    def test_finds_multiple_amounts(self) -> None:
        results = find_amounts("2 x $5.00 = $10.00")
        values = [v for _, v in results]
        assert Decimal("2") in values
        assert Decimal("5.00") in values
        assert Decimal("10.00") in values

    def test_no_amounts_in_plain_text(self) -> None:
        assert find_amounts("Thank you for shopping") == []

    def test_ignores_alphanumeric_tokens(self) -> None:
        # "ABC123" should not be parsed as the amount "123".
        results = find_amounts("SKU ABC123")
        assert results == []

    def test_finds_amount_with_currency_symbol_adjacent(self) -> None:
        results = find_amounts("EUR 1.234,56 due")
        values = [v for _, v in results]
        assert Decimal("1234.56") in values


class TestFindCurrency:
    def test_dollar_symbol(self) -> None:
        assert find_currency("$42.10") == "USD"

    def test_euro_symbol(self) -> None:
        assert find_currency("€42,10") == "EUR"

    def test_pound_symbol(self) -> None:
        assert find_currency("£42.10") == "GBP"

    def test_iso_code(self) -> None:
        assert find_currency("Total EUR 42.10") == "EUR"

    def test_yen_symbol(self) -> None:
        assert find_currency("¥4200") == "JPY"

    def test_rupee_symbol(self) -> None:
        assert find_currency("₹420.50") == "INR"

    def test_no_currency_found(self) -> None:
        assert find_currency("Total 42.10") is None

    def test_case_insensitive_symbol_token(self) -> None:
        assert find_currency("CHF 42.10") == "CHF"

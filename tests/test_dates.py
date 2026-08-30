from datetime import date

from receipt_ocr.dates import parse_date


class TestUnambiguousFormats:
    def test_iso_format(self) -> None:
        result = parse_date("2024-03-14")
        assert result is not None
        assert result.value == date(2024, 3, 14)
        assert result.ambiguous is False

    def test_iso_format_slashes(self) -> None:
        result = parse_date("2024/03/14")
        assert result is not None
        assert result.value == date(2024, 3, 14)

    def test_day_over_12_forces_dmy(self) -> None:
        # 25 cannot be a month -> unambiguous DD/MM/YYYY.
        result = parse_date("25/03/2024")
        assert result is not None
        assert result.value == date(2024, 3, 25)
        assert result.ambiguous is False

    def test_second_component_over_12_forces_mdy(self) -> None:
        # "03/25/2024": 25 can't be a month -> MM/DD/YYYY.
        result = parse_date("03/25/2024")
        assert result is not None
        assert result.value == date(2024, 3, 25)
        assert result.ambiguous is False

    def test_month_name_day_first(self) -> None:
        result = parse_date("14 Mar 2024")
        assert result is not None
        assert result.value == date(2024, 3, 14)
        assert result.ambiguous is False

    def test_month_name_full(self) -> None:
        result = parse_date("14 March 2024")
        assert result is not None
        assert result.value == date(2024, 3, 14)

    def test_month_name_first(self) -> None:
        result = parse_date("March 14, 2024")
        assert result is not None
        assert result.value == date(2024, 3, 14)

    def test_month_name_first_abbreviated(self) -> None:
        result = parse_date("Mar 14 2024")
        assert result is not None
        assert result.value == date(2024, 3, 14)

    def test_two_digit_year(self) -> None:
        result = parse_date("14/03/24")
        assert result is not None
        assert result.value == date(2024, 3, 14)

    def test_dashes_as_separator(self) -> None:
        result = parse_date("14-03-2024")
        assert result is not None
        assert result.value == date(2024, 3, 14)

    def test_dots_as_separator(self) -> None:
        result = parse_date("14.03.2024")
        assert result is not None
        assert result.value == date(2024, 3, 14)


class TestAmbiguousFormats:
    def test_ambiguous_defaults_to_dmy_without_locale_hint(self) -> None:
        # 03/04/2024 could be March 4 or April 3; default (no USD hint) is DD/MM.
        result = parse_date("03/04/2024")
        assert result is not None
        assert result.value == date(2024, 4, 3)
        assert result.ambiguous is True

    def test_ambiguous_uses_mdy_with_usd_locale_hint(self) -> None:
        result = parse_date("03/04/2024", locale_currency="USD")
        assert result is not None
        assert result.value == date(2024, 3, 4)
        assert result.ambiguous is True

    def test_ambiguous_uses_dmy_with_eur_locale_hint(self) -> None:
        result = parse_date("03/04/2024", locale_currency="EUR")
        assert result is not None
        assert result.value == date(2024, 4, 3)
        assert result.ambiguous is True

    def test_ambiguous_confidence_flag_not_set_for_unambiguous(self) -> None:
        result = parse_date("31/01/2024")
        assert result is not None
        assert result.ambiguous is False


class TestNoMatch:
    def test_no_date_in_text(self) -> None:
        assert parse_date("Thank you for shopping") is None

    def test_invalid_date_rejected(self) -> None:
        # Neither 32/13 nor 13/32 is a valid day/month combination.
        assert parse_date("32/13/2024") is None

    def test_finds_date_embedded_in_longer_text(self) -> None:
        result = parse_date("Date: 14/03/2024 Time: 10:22")
        assert result is not None
        assert result.value == date(2024, 3, 14)

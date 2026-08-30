"""Date parsing with DD/MM vs MM/DD disambiguation.

Receipts use a wide range of date formats. This module tries several
patterns and, when a numeric date is ambiguous (both components <= 12),
uses a locale hint (typically derived from the detected currency) to
break the tie, while honestly lowering confidence for the ambiguous case.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

_MONTH_NAMES = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

# yyyy-mm-dd or yyyy/mm/dd (ISO-like; unambiguous)
_ISO_RE = re.compile(r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b")

# numeric d/m/y or m/d/y with 2 or 4 digit year
_NUMERIC_RE = re.compile(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\b")

# "12 Jan 2024", "12-Jan-2024", "Jan 12, 2024", "January 12 2024"
_MONTH_NAME_RE = re.compile(
    r"\b(\d{1,2})[-\s]+([A-Za-z]{3,9})[-\s,]+(\d{2,4})\b"
)
_MONTH_NAME_FIRST_RE = re.compile(
    r"\b([A-Za-z]{3,9})[-\s]+(\d{1,2}),?\s+(\d{2,4})\b"
)

# Countries/currencies that conventionally use MM/DD/YYYY.
MDY_LOCALE_CURRENCIES = {"USD"}


@dataclass(frozen=True)
class ParsedDate:
    value: date
    raw: str
    ambiguous: bool = False
    """True if the numeric day/month order could not be determined from
    the digits alone and a locale-based default was used."""


def _full_year(y: int) -> int:
    if y < 100:
        return 2000 + y if y < 70 else 1900 + y
    return y


def _try_build(year: int, month: int, day: int) -> date | None:
    try:
        return date(_full_year(year), month, day)
    except ValueError:
        return None


def parse_date(
    text: str, locale_currency: str | None = None
) -> ParsedDate | None:
    """Find and parse the first plausible date in ``text``.

    ``locale_currency`` (an ISO currency code) is used only to disambiguate
    a numeric date where both the first and second components are <= 12.
    """
    m = _ISO_RE.search(text)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        dt = _try_build(y, mo, d)
        if dt:
            return ParsedDate(dt, m.group(0), ambiguous=False)

    m = _MONTH_NAME_RE.search(text)
    if m:
        day_s, month_s, year_s = m.groups()
        month = _MONTH_NAMES.get(month_s.lower()[:3]) or _MONTH_NAMES.get(month_s.lower())
        if month:
            dt = _try_build(int(year_s), month, int(day_s))
            if dt:
                return ParsedDate(dt, m.group(0), ambiguous=False)

    m = _MONTH_NAME_FIRST_RE.search(text)
    if m:
        month_s, day_s, year_s = m.groups()
        month = _MONTH_NAMES.get(month_s.lower()[:3]) or _MONTH_NAMES.get(month_s.lower())
        if month:
            dt = _try_build(int(year_s), month, int(day_s))
            if dt:
                return ParsedDate(dt, m.group(0), ambiguous=False)

    m = _NUMERIC_RE.search(text)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return _disambiguate_numeric(a, b, y, m.group(0), locale_currency)

    return None


def _disambiguate_numeric(
    a: int, b: int, year: int, raw: str, locale_currency: str | None
) -> ParsedDate | None:
    a_valid_day = 1 <= a <= 31
    b_valid_day = 1 <= b <= 31
    if a > 12 and b <= 12:
        # a must be the day -> DD/MM/YYYY
        dt = _try_build(year, b, a)
        return ParsedDate(dt, raw, ambiguous=False) if dt else None
    if b > 12 and a <= 12:
        # b must be the day -> MM/DD/YYYY
        dt = _try_build(year, a, b)
        return ParsedDate(dt, raw, ambiguous=False) if dt else None
    if not a_valid_day or not b_valid_day:
        return None

    # Both components <= 12: genuinely ambiguous. Use locale hint.
    use_mdy = locale_currency in MDY_LOCALE_CURRENCIES
    dt = _try_build(year, a, b) if use_mdy else _try_build(year, b, a)
    if dt is None:
        return None
    return ParsedDate(dt, raw, ambiguous=True)

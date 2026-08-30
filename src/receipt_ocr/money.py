"""Parsing of monetary amounts and currency symbols from noisy OCR text.

Receipts are not consistent about number formatting: ``1,234.56`` (US/UK),
``1.234,56`` (much of Europe/Latin America), ``1 234,56`` (France/Scandinavia)
and bare ``1234.56`` all show up in the wild. This module normalizes any of
those into a :class:`decimal.Decimal` without assuming a US locale.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

# Currency symbols mapped to their ISO 4217 code (best-effort; symbols like
# "$" are ambiguous across locales, so we default to the most common market).
_SYMBOL_TO_CODE = {
    "$": "USD",
    "us$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "₹": "INR",
    "₩": "KRW",
    "₽": "RUB",
    "r$": "BRL",
    "kr": "SEK",
    "fr": "CHF",
    "chf": "CHF",
    "rs": "INR",
    "rs.": "INR",
    "₱": "PHP",
    "₺": "TRY",
    "zl": "PLN",
}

_ISO_CODES = {
    "USD", "EUR", "GBP", "JPY", "INR", "KRW", "RUB", "BRL", "SEK", "NOK",
    "DKK", "CHF", "CAD", "AUD", "NZD", "CNY", "HKD", "SGD", "MXN", "ZAR",
    "PHP", "TRY", "PLN", "THB", "IDR", "VND", "AED", "SAR",
}

# A number-like token: digits with optional grouping/decimal separators.
_AMOUNT_RE = re.compile(
    r"""
    (?<![A-Za-z0-9])
    (?P<sign>-)?
    (?P<num>
        \d{1,3}(?:[.,  ]\d{3})*(?:[.,]\d{1,2})?
        |
        \d+(?:[.,]\d{1,2})?
    )
    (?![A-Za-z0-9])
    """,
    re.VERBOSE,
)

_CURRENCY_TOKEN_RE = re.compile(
    r"(?P<sym>US\$|R\$|CHF|Rs\.?|[$€£¥₹₩₽₱₺]|kr|zl)",
    re.IGNORECASE,
)

_ISO_TOKEN_RE = re.compile(r"\b([A-Z]{3})\b")


@dataclass(frozen=True)
class ParsedAmount:
    value: Decimal
    currency: str | None
    raw: str
    ambiguous_separator: bool = False


def normalize_number(raw: str) -> Decimal | None:
    """Parse a single numeric token into a Decimal, without assuming a locale.

    Handles thousands/decimal separator ambiguity heuristically:

    - Two distinct separators present -> the *last* one is the decimal
      separator (e.g. ``1.234,56`` or ``1,234.56``).
    - One separator, exactly 2 digits after it -> treated as decimal.
    - One separator, exactly 3 digits after it -> treated as a thousands
      grouping (integer amount), UNLESS the whole token has only that one
      group of <=3 digits before it too and no other cues (kept as
      thousands per standard convention).
    - One separator, 1 digit after it -> decimal (e.g. ``12.5``).
    """
    raw = raw.strip()
    if not raw:
        return None
    text = raw.replace(" ", "").replace(" ", "")
    sign = -1 if text.startswith("-") else 1
    text = text.lstrip("-").strip()
    if not text:
        return None

    # Find separators in order of appearance.
    seps = [ch for ch in text if ch in ".,"]

    if not seps:
        try:
            return Decimal(text) * sign
        except InvalidOperation:
            return None

    distinct = sorted(set(seps), key=lambda c: text.rindex(c))
    if len(distinct) >= 2:
        # Determine decimal separator as whichever appears last in string.
        last_dot = text.rfind(".")
        last_comma = text.rfind(",")
        decimal_sep = "." if last_dot > last_comma else ","
        thousands_sep = "," if decimal_sep == "." else "."
        cleaned = text.replace(thousands_sep, "").replace(decimal_sep, ".")
        try:
            return Decimal(cleaned) * sign
        except InvalidOperation:
            return None

    sep = distinct[0]
    idx = text.rfind(sep)
    frac_len = len(text) - idx - 1
    if frac_len == 3:
        # thousands grouping, e.g. "1.234" or "1,234"
        cleaned = text.replace(sep, "")
        try:
            return Decimal(cleaned) * sign
        except InvalidOperation:
            return None
    # 1 or 2 (or other) digits after the separator: treat as decimal point.
    cleaned = text.replace(sep, ".")
    try:
        return Decimal(cleaned) * sign
    except InvalidOperation:
        return None


def is_ambiguous_thousands(raw: str) -> bool:
    """True if ``raw`` has exactly one separator with 3 trailing digits.

    Such tokens (``1,234`` or ``1.234``) are genuinely ambiguous between
    "one thousand two hundred thirty-four" and a rare 3-decimal currency;
    callers may want to lower confidence when this holds.
    """
    text = raw.strip().lstrip("-")
    seps = [ch for ch in text if ch in ".,"]
    if len(set(seps)) != 1:
        return False
    sep = seps[0]
    idx = text.rfind(sep)
    return len(text) - idx - 1 == 3


def find_amounts(text: str) -> list[tuple[str, Decimal]]:
    """Find all plausible monetary amounts in ``text``.

    Returns a list of (raw matched substring, parsed Decimal) tuples.
    """
    results: list[tuple[str, Decimal]] = []
    for m in _AMOUNT_RE.finditer(text):
        raw = m.group(0)
        if not re.search(r"\d", raw):
            continue
        value = normalize_number(raw)
        if value is None:
            continue
        results.append((raw, value))
    return results


def find_currency(text: str) -> str | None:
    """Best-effort detection of a currency code from a text block."""
    iso_match = _ISO_TOKEN_RE.search(text)
    if iso_match and iso_match.group(1) in _ISO_CODES:
        return iso_match.group(1)
    sym_match = _CURRENCY_TOKEN_RE.search(text)
    if sym_match:
        sym = sym_match.group("sym").lower()
        return _SYMBOL_TO_CODE.get(sym)
    return None

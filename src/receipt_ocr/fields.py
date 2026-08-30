"""Field extractors: total, tax, vendor, date, currency, line items.

Each extractor operates purely on a list of :class:`~receipt_ocr.models.TextBlock`
and returns a :class:`~receipt_ocr.models.FieldResult` (or ``None`` when the
field cannot be found at all).
"""

from __future__ import annotations

import re
from decimal import Decimal

from receipt_ocr.dates import ParsedDate, parse_date
from receipt_ocr.layout import Line, relative_vertical_position
from receipt_ocr.models import Evidence, FieldResult, LineItem, TextBlock
from receipt_ocr.money import find_amounts, find_currency, is_ambiguous_thousands

# --------------------------------------------------------------------------
# Keyword tables
# --------------------------------------------------------------------------

TOTAL_STRONG = [
    "grand total", "total due", "amount due", "balance due",
    "total amount", "total to pay", "total payable", "amount payable",
    "net total", "total paid",
]
TOTAL_WEAK = ["total"]
TOTAL_EXCLUDE_PHRASES = [
    "subtotal", "sub total", "sub-total", "total items", "total qty",
    "total quantity", "no. of items", "number of items",
]

TAX_STRONG = ["sales tax", "vat amount", "gst amount", "total tax"]
TAX_WEAK = ["tax", "vat", "gst", "hst", "pst"]
TAX_EXCLUDE_PHRASES = ["tax invoice", "tax id", "tax no", "vat no", "vat reg", "vat number"]

FOOTER_NOISE = [
    "thank you", "thanks for", "come again", "please come", "customer copy",
    "www.", "http", "cashier", "register", "receipt no", "order no",
    "invoice no", "table", "server:", "change", "cash", "tender", "card",
    "visa", "mastercard", "approved", "auth code", "signature",
]

VENDOR_EXCLUDE_HINTS = [
    "receipt", "invoice", "tax invoice", "table", "server", "order",
    "tel:", "phone", "fax", "www.", "http", "date", "time",
]

_PHONE_RE = re.compile(r"\b\d{3}[-.\s]?\d{3,4}[-.\s]?\d{4}\b")
_QTY_PREFIX_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(?:x|@|pcs?|units?)\b", re.IGNORECASE)
_ADDRESS_HINT_RE = re.compile(
    r"\b(street|st\.|avenue|ave\.|road|rd\.|blvd|suite|floor|zip|p\.?o\.? box)\b",
    re.IGNORECASE,
)
_REFERENCE_NUMBER_RE = re.compile(r"#\s*\d+|\bno\.?\s*[:#]?\s*\d+", re.IGNORECASE)
_PRICE_LIKE_RE = re.compile(
    r"[.,]\d{1,2}\b|US\$|R\$|CHF|Rs\.?|[$€£¥₹₩₽₱₺]|\b[A-Z]{3}\b"
)


def _looks_like_price(text: str) -> bool:
    """True if ``text`` has decimal-fraction or currency-marker evidence,
    as opposed to a bare integer (e.g. a receipt/order reference number)."""
    return bool(_PRICE_LIKE_RE.search(text))


def _contains_any(text: str, phrases: list[str]) -> bool:
    lower = text.lower()
    return any(p in lower for p in phrases)


def _keyword_strength(text: str, strong: list[str], weak: list[str], exclude: list[str]) -> float:
    lower = text.lower()
    if _contains_any(lower, exclude):
        return 0.0
    for phrase in strong:
        if phrase in lower:
            return 1.0
    for phrase in weak:
        if re.search(rf"\b{re.escape(phrase)}\b", lower):
            return 0.6
    return 0.0


# --------------------------------------------------------------------------
# Currency
# --------------------------------------------------------------------------


def extract_currency(blocks: list[TextBlock]) -> FieldResult | None:
    votes: dict[str, list[TextBlock]] = {}
    for b in blocks:
        code = find_currency(b.text)
        if code:
            votes.setdefault(code, []).append(b)
    if not votes:
        return FieldResult(name="currency", value=None, confidence=0.0, evidence=None)

    best_code, best_blocks = max(votes.items(), key=lambda kv: len(kv[1]))
    total_votes = sum(len(v) for v in votes.values())
    agreement = len(best_blocks) / total_votes
    avg_conf = sum(b.confidence for b in best_blocks) / len(best_blocks) / 100.0
    confidence = min(1.0, 0.5 * agreement + 0.5 * avg_conf)
    evidence = Evidence(
        text=best_blocks[0].text,
        blocks=(best_blocks[0].index,),
        reason=f"currency symbol/code detected in {len(best_blocks)} block(s)",
    )
    return FieldResult(name="currency", value=best_code, confidence=confidence, evidence=evidence)


# --------------------------------------------------------------------------
# Amount-keyword based fields (total, tax)
# --------------------------------------------------------------------------


def _amount_candidates_on_line(line: Line) -> list[tuple[Decimal, TextBlock, str, bool]]:
    """Return (value, block, raw_text, ambiguous) for every amount-looking
    block on a line, scanning right-to-left blocks individually (not the
    joined line text) so we can attribute evidence to a single block."""
    candidates = []
    for b in sorted(line.blocks, key=lambda bl: -bl.left):
        for raw, value in find_amounts(b.text):
            if value < 0:
                continue
            candidates.append((value, b, raw, is_ambiguous_thousands(raw)))
    return candidates


def _find_keyword_amount(
    blocks: list[TextBlock],
    lines: list[Line],
    strong: list[str],
    weak: list[str],
    exclude: list[str],
    field_name: str,
) -> FieldResult | None:
    best: tuple[float, Decimal, TextBlock, str, bool, Line] | None = None

    for i, line in enumerate(lines):
        strength = _keyword_strength(line.text, strong, weak, exclude)
        if strength <= 0.0:
            continue

        # Prefer an amount on the same line; fall back to the next line.
        candidates = _amount_candidates_on_line(line)
        source_line = line
        if not candidates and i + 1 < len(lines):
            candidates = _amount_candidates_on_line(lines[i + 1])
            source_line = lines[i + 1]
        if not candidates:
            continue

        value, block, raw, ambiguous = candidates[0]
        position_bonus = relative_vertical_position(block, blocks)
        conf_factor = block.confidence / 100.0
        ambiguity_penalty = 0.15 if ambiguous else 0.0
        score = (
            0.5 * strength
            + 0.2 * position_bonus
            + 0.3 * conf_factor
            - ambiguity_penalty
        )
        if best is None or score > best[0]:
            best = (score, value, block, raw, ambiguous, source_line)

    if best is None:
        return None

    score, value, block, raw, ambiguous, source_line = best
    confidence = max(0.0, min(1.0, score))
    evidence = Evidence(
        text=source_line.text,
        blocks=(block.index,),
        reason=(
            f"matched near a {field_name} keyword"
            + (" (ambiguous separator)" if ambiguous else "")
        ),
    )
    return FieldResult(name=field_name, value=value, confidence=confidence, evidence=evidence)


def extract_total(blocks: list[TextBlock], lines: list[Line]) -> FieldResult | None:
    result = _find_keyword_amount(
        blocks, lines, TOTAL_STRONG, TOTAL_WEAK, TOTAL_EXCLUDE_PHRASES, "total"
    )
    if result is not None:
        return result

    # Fallback: no keyword found at all. Use the largest amount on the page,
    # but with a low confidence since this is a weak heuristic.
    all_amounts: list[tuple[Decimal, TextBlock]] = []
    for b in blocks:
        for _raw, value in find_amounts(b.text):
            if value >= 0:
                all_amounts.append((value, b))
    if not all_amounts:
        return None
    value, block = max(all_amounts, key=lambda t: t[0])
    evidence = Evidence(
        text=block.text,
        blocks=(block.index,),
        reason="no total keyword found; used the largest amount on the page",
    )
    return FieldResult(name="total", value=value, confidence=0.25, evidence=evidence)


def extract_tax(blocks: list[TextBlock], lines: list[Line]) -> FieldResult | None:
    return _find_keyword_amount(blocks, lines, TAX_STRONG, TAX_WEAK, TAX_EXCLUDE_PHRASES, "tax")


# --------------------------------------------------------------------------
# Date
# --------------------------------------------------------------------------


def extract_date(blocks: list[TextBlock], locale_currency: str | None) -> FieldResult | None:
    best: tuple[float, TextBlock, ParsedDate] | None = None
    for b in blocks:
        parsed = parse_date(b.text, locale_currency=locale_currency)
        if parsed is None:
            continue
        conf_factor = b.confidence / 100.0
        ambiguity_penalty = 0.2 if parsed.ambiguous else 0.0
        score = 0.7 + 0.3 * conf_factor - ambiguity_penalty
        if best is None or score > best[0]:
            best = (score, b, parsed)

    if best is None:
        return None
    score, block, parsed = best
    confidence = max(0.0, min(1.0, score))
    evidence = Evidence(
        text=block.text,
        blocks=(block.index,),
        reason=(
            "ambiguous day/month order; used locale default"
            if parsed.ambiguous
            else "matched date pattern"
        ),
    )
    return FieldResult(name="date", value=parsed.value, confidence=confidence, evidence=evidence)


# --------------------------------------------------------------------------
# Vendor
# --------------------------------------------------------------------------


def _vendor_eligible(text: str) -> bool:
    if not text:
        return False
    if _PHONE_RE.search(text) or _ADDRESS_HINT_RE.search(text):
        return False
    if _contains_any(text, VENDOR_EXCLUDE_HINTS):
        return False
    if parse_date(text) is not None:
        return False
    alpha_ratio = sum(c.isalpha() for c in text) / max(len(text), 1)
    return alpha_ratio >= 0.4


def extract_vendor(blocks: list[TextBlock], lines: list[Line]) -> FieldResult | None:
    if not lines:
        return None
    heights = sorted(b.height for b in blocks if b.height > 0)
    median_height = heights[len(heights) // 2] if heights else 10.0

    candidate_lines = lines[: min(6, len(lines))]
    eligible = [_vendor_eligible(line.text.strip()) for line in candidate_lines]
    avg_heights = [
        sum(b.height for b in line.blocks) / len(line.blocks) if line.blocks else 0.0
        for line in candidate_lines
    ]

    # A business name is often printed across 2+ consecutive lines in the
    # same (typically large) font, e.g. "GREENLEAF" / "MARKET". Consider
    # contiguous runs of eligible lines with similar font size as a single
    # vendor candidate, in addition to each individual line.
    runs: list[tuple[float, str, tuple[TextBlock, ...], int]] = []
    i = 0
    n = len(candidate_lines)
    while i < n:
        if not eligible[i]:
            i += 1
            continue
        j = i
        run_lines = [candidate_lines[i]]
        while (
            j + 1 < n
            and eligible[j + 1]
            and avg_heights[j] > 0
            and abs(avg_heights[j + 1] - avg_heights[i]) / avg_heights[i] <= 0.3
        ):
            j += 1
            run_lines.append(candidate_lines[j])
        text = " ".join(ln.text.strip() for ln in run_lines)
        run_blocks = tuple(b for ln in run_lines for b in ln.blocks)
        run_avg_height = sum(avg_heights[i : j + 1]) / (j - i + 1)
        runs.append((run_avg_height, text, run_blocks, i))
        i = j + 1

    best: tuple[float, str, tuple[TextBlock, ...]] | None = None
    for avg_height, text, run_blocks, start_idx in runs:
        size_score = min(avg_height / median_height, 2.5) if median_height else 1.0
        position_bonus = 1.0 - (start_idx / max(len(candidate_lines), 1))
        score = 0.6 * size_score + 0.4 * position_bonus
        if best is None or score > best[0]:
            best = (score, text, run_blocks)

    if best is None:
        # Fall back to the very first non-empty line, low confidence.
        for line in lines:
            if line.text.strip():
                avg_conf = sum(b.confidence for b in line.blocks) / len(line.blocks)
                evidence = Evidence(
                    text=line.text,
                    blocks=tuple(b.index for b in line.blocks),
                    reason="fallback: first non-empty line (no clear vendor heuristic match)",
                )
                return FieldResult(
                    name="vendor",
                    value=line.text.strip(),
                    confidence=min(0.3, avg_conf / 100.0),
                    evidence=evidence,
                )
        return None

    score, text, run_blocks = best
    avg_conf = sum(b.confidence for b in run_blocks) / len(run_blocks)
    confidence = max(0.0, min(1.0, 0.5 * min(score, 1.0) + 0.5 * (avg_conf / 100.0)))
    evidence = Evidence(
        text=text,
        blocks=tuple(b.index for b in run_blocks),
        reason="top-of-receipt heuristic (font size + position)",
    )
    return FieldResult(name="vendor", value=text.strip(), confidence=confidence, evidence=evidence)


# --------------------------------------------------------------------------
# Line items
# --------------------------------------------------------------------------


def _is_skippable_line(text: str) -> bool:
    lower = text.lower()
    if _contains_any(lower, FOOTER_NOISE):
        return True
    if _keyword_strength(text, TOTAL_STRONG, TOTAL_WEAK, []) > 0:
        return True
    if _contains_any(lower, ["subtotal", "sub total", "sub-total"]):
        return True
    if _keyword_strength(text, TAX_STRONG, TAX_WEAK, []) > 0:
        return True
    if _PHONE_RE.search(text) or _ADDRESS_HINT_RE.search(text):
        return True
    if _REFERENCE_NUMBER_RE.search(text):
        return True
    return parse_date(text) is not None


def extract_line_items(blocks: list[TextBlock], lines: list[Line]) -> FieldResult:
    items: list[LineItem] = []
    all_conf: list[float] = []

    # Skip an initial header region (vendor/address/date block): first line
    # is very likely the vendor and is excluded outright.
    body_lines = lines[1:] if len(lines) > 1 else lines

    for i, line in enumerate(body_lines):
        text = line.text.strip()
        if not text or _is_skippable_line(text):
            continue

        amounts = [c for c in _amount_candidates_on_line(line) if _looks_like_price(c[2])]
        if not amounts:
            continue

        # Rightmost (largest `left`) amount block is the line total/price.
        amounts_by_position = sorted(amounts, key=lambda t: -t[1].left)
        price_value, price_block, _, ambiguous = amounts_by_position[0]

        qty_match = _QTY_PREFIX_RE.match(text)
        quantity = Decimal(qty_match.group(1)) if qty_match else None

        unit_price = None
        if len(amounts_by_position) >= 2 and quantity is not None:
            unit_price = amounts_by_position[1][0]

        description = text
        # Strip the trailing price token(s) from the description for
        # readability; keep it simple and robust to OCR noise.
        price_text = price_block.text.strip()
        if description.endswith(price_text):
            description = description[: -len(price_text)].strip()
        if not description:
            description = text

        conf = sum(b.confidence for b in line.blocks) / len(line.blocks)
        if ambiguous:
            conf *= 0.85
        all_conf.append(conf)

        items.append(
            LineItem(
                description=description,
                amount=price_value,
                quantity=quantity,
                unit_price=unit_price,
                line_index=i,
            )
        )

    confidence = (sum(all_conf) / len(all_conf) / 100.0) if all_conf else 0.0
    evidence = Evidence(
        text=f"{len(items)} candidate row(s)",
        blocks=tuple(),
        reason="rows with a trailing amount, excluding totals/tax/footer lines",
    )
    return FieldResult(name="line_items", value=items, confidence=confidence, evidence=evidence)

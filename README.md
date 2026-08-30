# receipt-ocr

Extract structured fields — `total`, `date`, `vendor`, `tax`, `currency`,
`line_items` — from receipt and invoice images, with an honest confidence
score per field so a human only has to review the fields the tool is
actually unsure about.

## What

Generic OCR gives you a wall of text with per-word bounding boxes. It does
not tell you which number is the total, whether `03/04/2024` means March
4th or April 3rd, or which line at the top is the vendor's name. `receipt-ocr`
takes OCR output (from Tesseract, or from a pre-extracted JSON file) and
applies layout- and pattern-aware heuristics to pull out the fields
bookkeeping actually needs, each with a 0-1 confidence score and a pointer
back to the OCR block(s) it came from.

## Why

Blind trust in OCR output is a bad idea for financial data - handwriting-grade
noise, currency ambiguity, and locale-dependent date/number formats are all
common in real receipts. Rather than pretending every extracted field is
equally reliable, this tool scores each one and produces a **review queue**
of only the fields below a confidence threshold, so a human reviewer's time
goes where it's actually needed.

## Features

- **Total**: found via keyword proximity (`total`, `amount due`, `balance
  due`, ...) and position on the page — not simply "the largest number on
  the receipt" (which is often a single expensive line item, not the total).
- **Date**: supports ISO (`2024-03-14`), numeric (`14/03/2024`,
  `03/14/2024`), and month-name (`14 Mar 2024`, `March 14, 2024`) formats.
  When a numeric date is genuinely ambiguous (both components ≤ 12), it is
  disambiguated using a locale hint derived from the detected currency, and
  the resulting confidence is honestly lowered to reflect the guess.
- **Vendor**: top-of-receipt heuristic using font size (block height) and
  position, filtering out addresses, phone numbers, and generic headers
  like "RECEIPT" or "INVOICE".
- **Tax / VAT**: keyword-based (`tax`, `vat`, `gst`, `hst`, `pst`, ...),
  separate from `total`, and not confused with "Tax Invoice" or "VAT No."
  labels that aren't amounts.
- **Currency**: detected from symbols (`$`, `€`, `£`, `¥`, `₹`, ...) and ISO
  codes (`USD`, `EUR`, ...) anywhere on the receipt, by majority vote.
- **Line items**: rows with a trailing amount, excluding totals/tax/subtotal/
  footer noise, with best-effort quantity and unit-price detection for rows
  like `2 x Free-range Eggs (12)  $5.00  $10.00`.
- **Locale-aware money parsing**: `1,234.56`, `1.234,56`, and `1 234,56` are
  all parsed correctly without assuming a US locale; a heuristic flags and
  down-weights genuinely ambiguous amounts like `1,234` (thousands grouping
  vs. an unusual 3-decimal currency).
- **Confidence per field**, combining OCR block confidence, keyword/pattern
  strength, and positional evidence — plus a `--min-confidence` gate that
  produces a **review queue** of only the uncertain fields.

## Architecture

```
Image ──▶ OcrBackend.extract() ──▶ list[TextBlock] ──▶ engine.extract_fields() ──▶ ExtractionResult
          (Tesseract or JSON)       (text + bbox +       (pure, OCR-agnostic)      (value + confidence
                                      OCR confidence)                               + evidence per field)
```

The field-extraction engine (`receipt_ocr.engine`, `receipt_ocr.fields`,
`receipt_ocr.money`, `receipt_ocr.dates`, `receipt_ocr.layout`) never
imports an OCR library. It operates entirely on `TextBlock` objects
(text + bounding box + confidence), which makes it deterministic and fully
testable with synthetic fixtures, independent of whatever OCR engine
produced them.

## Backends

`receipt_ocr.backends.OcrBackend` is a `typing.Protocol` with one method:
`extract(image_path) -> list[TextBlock]`.

| Backend | Native dependencies | Use case |
|---|---|---|
| `JsonBackend` | None | Pre-extracted OCR output (any OCR engine, or synthetic test fixtures). **This is what CI and the test suite use.** |
| `TesseractBackend` | `pytesseract` + `Pillow` (Python) and the system `tesseract` binary | Real images, when Tesseract is installed. |

`TesseractBackend` uses an optional import: it raises a clear `RuntimeError`
if `pytesseract`/`Pillow` aren't installed, rather than failing at import
time. The package, its CLI's JSON-backend path, and its entire test suite
work with **zero native OCR dependencies**.

## Installation

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"     # Windows
# or
.venv/bin/python -m pip install -e ".[dev]"                # macOS/Linux
```

To use `TesseractBackend` against real images, additionally install the
`ocr` extra and the system Tesseract binary:

```bash
pip install "receipt-ocr[ocr]"
# then install the tesseract binary for your OS, e.g.:
#   macOS:   brew install tesseract
#   Ubuntu:  apt-get install tesseract-ocr
#   Windows: https://github.com/UB-Mannheim/tesseract/wiki
```

## Usage

```bash
# JSON backend (no native dependencies):
receipt-ocr samples/sample_receipt.json --min-confidence 0.6

# Tesseract backend, against a real image (requires the ocr extra + tesseract binary):
receipt-ocr path/to/receipt.jpg --backend tesseract
```

As a library:

```python
from receipt_ocr.backends import JsonBackend
from receipt_ocr.engine import extract_fields

blocks = JsonBackend().extract("samples/sample_receipt.json")
result = extract_fields(blocks, source="samples/sample_receipt.json")

print(result.fields["total"].value)         # Decimal("119.55")
print(result.fields["total"].confidence)    # e.g. 0.83
print(result.review_queue(min_confidence=0.6))  # fields to have a human check
```

## Examples

Input (`samples/sample_receipt.json`) is a JSON array of OCR blocks like:

```json
{"text": "TOTAL", "left": 30, "top": 260, "width": 70, "height": 16, "confidence": 97.0}
```

Running `receipt-ocr samples/sample_receipt.json` produces (abridged):

```json
{
  "fields": {
    "currency": { "value": "USD", "confidence": 0.95, "evidence": {"text": "$6.50", "..." : "..."} },
    "vendor":   { "value": "GREENLEAF MARKET", "confidence": 0.98, "evidence": { "...": "..." } },
    "date":     { "value": "2024-03-14", "confidence": 0.98, "evidence": { "...": "..." } },
    "total":    { "value": "119.55", "confidence": 0.75, "evidence": { "...": "..." } },
    "tax":      { "value": "8.86", "confidence": 0.92, "evidence": { "...": "..." } },
    "line_items": { "value": [ { "description": "Organic Apples 2kg", "amount": "6.50" }, "..." ] }
  },
  "review_queue": []
}
```

## Testing

```bash
pytest
ruff check .
mypy
```

All three are enforced in CI (`.github/workflows/ci.yml`) across Python
3.10-3.13 on Ubuntu, Windows, and macOS, plus a dedicated lint/mypy job and
a CLI smoke-test job that runs the JSON backend end to end — no Tesseract
install anywhere in CI.

The test suite (`tests/`) uses synthetic `TextBlock` fixtures covering
hard cases: a receipt where the largest number on the page is not the
total, ambiguous DD/MM vs MM/DD dates, a missing tax line, multiple
currencies, and noisy/low-confidence OCR text.

## Limitations

Be realistic about what this tool can and can't do:

- **Accuracy depends entirely on the OCR backend's output quality.** The
  extraction engine can only be as good as the text blocks and bounding
  boxes it receives. Skewed photos, glare, faded thermal-paper receipts,
  and handwriting will degrade `TesseractBackend` output significantly, and
  no amount of downstream heuristics fully compensates for that.
  `JsonBackend` (which is what CI and this README's examples exercise) is
  only as good as whatever produced its input JSON.
- The heuristics are tuned for typical Western-style itemized receipts and
  invoices. Non-tabular or heavily stylized layouts (e.g. some restaurant
  or multi-column invoices) may extract line items incorrectly.
- Vendor detection is a font-size/position heuristic, not a business-name
  database lookup - it can pick up a slogan or address line on unusual
  layouts.
- Date disambiguation, when genuinely ambiguous, falls back to a locale
  guess based on detected currency (defaulting to DD/MM unless USD is
  detected) - this is a heuristic, not certainty, and the field's
  confidence is intentionally lowered to reflect that.
- This tool does not do any image preprocessing (deskew, denoise, binarize)
  itself; that is left to the OCR backend.
- Multi-page receipts are represented via `TextBlock.page`, but the
  extractors currently treat all blocks as one logical document — per-page
  handling is a possible future enhancement.

## Security

- No network calls are made by this library or CLI.
- `JsonBackend` parses input with the standard library `json` module (no
  arbitrary code execution).
- Do not commit real customer receipts/invoices containing PII to a public
  repository; the bundled `samples/sample_receipt.json` is entirely
  synthetic.
- Report security issues by opening a private security advisory on GitHub
  rather than a public issue.

## License

MIT - see [LICENSE](LICENSE).

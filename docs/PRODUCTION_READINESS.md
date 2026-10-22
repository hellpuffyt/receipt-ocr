# Production readiness — receipt-ocr

Audit date: 2026-10-22. Tested commit: `4ac0555` (branch `audit/production-readiness`, based on `main` @ `1738142`).

## Scope

Field extraction (total, date, vendor, tax, currency, line items) with per-field confidence and a
review queue, from OCR text blocks. Backends: `JsonBackend` (pre-extracted OCR JSON, no native deps)
and `TesseractBackend` (optional `ocr` extra + system `tesseract`).

## Platforms

CPython 3.10+; engine has no runtime dependencies. Verified on macOS 27 (Apple M5), CPython 3.12.14.

## What was and was not verified

- **Verified:** the OCR-agnostic engine via the test suite (synthetic `TextBlock` fixtures) and the
  bundled sample (`total 119.55` = line items 110.69 + tax 8.86; date `14/03/2024` with USD → 2024-03-14).
  Money parsing probed manually: `1,234.56`, `1.234,56`, `1 234,56`, `1.234.567,89`, `.99` correct;
  invalid dates (`2024-02-30`) rejected; ambiguous `03/04/2024` flagged `ambiguous=True`.
- **Not verified:** `TesseractBackend` and accuracy on real images. `brew info tesseract` shows 5.5.3
  available but not installed; per the audit rules no OCR engine or models were installed. The
  missing-dependency path is tested (`test_tesseract_backend_without_extras_is_an_error_message`,
  skipped automatically when the extra *is* installed, with a stated reason).

## Clean-clone verification (commit `4ac0555`)

```bash
git clone -b audit/production-readiness <local clone> receipt-ocr && cd receipt-ocr
uv venv --python 3.12 .venv && uv pip install -e ".[dev]"     # README: python -m venv + pip
receipt-ocr samples/sample_receipt.json --min-confidence 0.6  # USD, GREENLEAF MARKET, 2024-03-14, 119.55, 8.86; queue []
receipt-ocr x.jpg --backend tesseract                         # exit 2 with install hint (no traceback)
pytest && ruff check . && mypy                                # 128 passed / clean / clean
```

## Commands and results

| Command | Baseline (`1738142`) | After (`4ac0555`) |
| --- | --- | --- |
| `pytest` | exit 0 — 124 passed, 0 failed, 0 skipped | exit 0 — 128 passed, 0 failed, 0 skipped |
| `ruff check .` / `mypy` | exit 0 / exit 0 | exit 0 / exit 0 |
| `uvx pip-audit` | — | no known vulnerabilities |

CI status — default branch: success (`1738142`, 2026-08-30); audit branch: pending until pushed.

## Bugs found and fixed

| Severity | Bug | Regression test |
| --- | --- | --- |
| Medium (wrong money) | `-$2.00` / `-€1,50` parsed positive (sign outside the number token); a coupon line became a +line item | `tests/test_money.py::test_minus_before_a_currency_symbol_is_a_negative_amount`, `tests/test_fields.py::test_a_discount_line_is_not_a_positive_line_item` |
| Medium (supply chain) | install hints `pip install receipt-ocr[ocr]` fetch an unrelated PyPI project | README + error message point at the checkout |
| Low (crash) | Tesseract backend construction `RuntimeError` escaped the CLI handler | `tests/test_cli.py::test_tesseract_backend_without_extras_is_an_error_message` |

## Security review

No network; JSON parsed with `json`; Tesseract invoked via `pytesseract` (not exercised). History
secret scan: no hits. `pip-audit`: clean. Workflow permissions `contents: read`.

## Known limitations

Negatives/discounts ignored for totals and line items; `(12.00)` read as positive; accuracy depends on
OCR quality; Tesseract path unverified (above).

## Acceptance checklist

| # | Item | Expected | Evidence | Result |
| --- | --- | --- | --- | --- |
| 1 | Sample receipt fields | total 119.55, tax 8.86, date 2024-03-14 | clean clone | PASS |
| 2 | Locale-aware money parsing | correct decimals | tests + probe | PASS |
| 3 | Ambiguous dates flagged | ambiguous=True, lower confidence | tests | PASS |
| 4 | Signs not lost | `-$2.00` negative | new tests | PASS |
| 5 | Missing OCR extras → message | exit 2 | new test | PASS |
| 6 | Real images via Tesseract | fields extracted | not run | NOT VERIFIED |

## Classification proposal

**Partially Verified** — engine verified on fixtures; the real OCR path was not run (no Tesseract).

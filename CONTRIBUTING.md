# Contributing

Thanks for considering a contribution to receipt-ocr.

## Setup

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"   # Windows
# or: .venv/bin/python -m pip install -e ".[dev]"        # macOS/Linux
```

## Before opening a PR

Run the same gates CI runs:

```bash
pytest
ruff check .
mypy
```

All three must pass. `mypy` runs in `strict` mode.

## Design principles to preserve

- The field-extraction engine (`receipt_ocr.engine`, `receipt_ocr.fields`,
  `receipt_ocr.money`, `receipt_ocr.dates`, `receipt_ocr.layout`) must stay
  100% independent of any OCR vendor. It only ever consumes `TextBlock`
  objects. If you add a new extractor or heuristic, add synthetic-block
  fixtures for it in `tests/` rather than an image.
- New OCR backends should be optional imports behind the `OcrBackend`
  protocol, with a clear `RuntimeError` if their native dependency is
  missing, and must not be required for `pytest`, `ruff`, or `mypy` to pass.
- Don't assume a US locale: add test cases for at least one non-US date
  format and one non-USD currency for any new date/money handling.

## Reporting bugs

Please include the input `TextBlock`/JSON that reproduces the issue where
possible - that lets us turn it directly into a regression test.

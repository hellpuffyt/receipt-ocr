# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed

- A minus sign before a currency symbol (`-$2.00`, `-€1,50`) was dropped, so a
  discount line became a positive line item, while `-2.00` was negative.
- `--backend tesseract` without the `ocr` extra raised an uncaught
  `RuntimeError` traceback instead of an error message (exit 2).
- Install hints said `pip install receipt-ocr[ocr]`, which fetches an unrelated
  PyPI package of the same name; they now point at the local checkout.

- With real (word-level) Tesseract output, dates written as several words
  (`14 Mar 2024`, `March 14, 2024`) were never found, because dates were only
  parsed per block. Whole lines are now also tried.
- Line-item descriptions kept anything right of the price when it was a
  separate block (`Espresso 2,80 EUR`); the description is now the text left
  of the price.

### Added

- `tests/test_tesseract_integration.py`: synthetic receipts rendered at test
  time and run through the real Tesseract binary (skipped when it is absent).
- README "Verification status", negative-amount
  limitation, `SECURITY.md`, `.editorconfig`, `docs/PRODUCTION_READINESS.md`.

## [0.1.0] - 2026-08-30

### Added

- Pure, OCR-backend-agnostic extraction engine (`receipt_ocr.engine`) operating on
  `TextBlock` lists (text + bounding box + confidence).
- `OcrBackend` protocol with two implementations: `JsonBackend` (loads pre-extracted
  blocks from JSON, zero native dependencies) and `TesseractBackend` (optional,
  requires the `ocr` extra plus a system `tesseract` install).
- Field extractors: `total`, `tax`, `vendor`, `date`, `currency`, `line_items`, each
  returning a value, a 0-1 confidence score, and evidence pointing back to the
  source OCR block(s).
- Locale-aware money parsing (`receipt_ocr.money`) supporting US/UK, European, and
  space-grouped number formats without assuming a US locale.
- Date parsing (`receipt_ocr.dates`) with DD/MM vs MM/DD disambiguation.
- CLI (`receipt-ocr`) with `--backend`, `--min-confidence`, and a review-queue of
  low-confidence fields in the JSON output.

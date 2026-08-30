# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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

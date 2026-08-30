"""Command-line interface for receipt-ocr."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from receipt_ocr.backends import JsonBackend, OcrBackend
from receipt_ocr.engine import extract_fields
from receipt_ocr.models import ExtractionResult


def _build_backend(name: str) -> OcrBackend:
    if name == "json":
        return JsonBackend()
    if name == "tesseract":
        from receipt_ocr.backends import TesseractBackend

        return TesseractBackend()
    raise ValueError(f"unknown backend: {name}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="receipt-ocr",
        description=(
            "Extract structured fields (total, date, vendor, tax, line items) "
            "from a receipt/invoice."
        ),
    )
    parser.add_argument(
        "input",
        help=(
            "Path to the input file (JSON blocks by default, "
            "or an image with --backend tesseract)"
        ),
    )
    parser.add_argument(
        "--backend",
        choices=["json", "tesseract"],
        default="json",
        help="OCR backend to use (default: json, which requires zero native dependencies)",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.6,
        help=(
            "Fields with confidence below this threshold are listed in the "
            "review queue (default: 0.6)"
        ),
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation for output (default: 2)",
    )
    parser.add_argument(
        "-o", "--output",
        help="Write JSON output to this file instead of stdout",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    backend = _build_backend(args.backend)
    try:
        blocks = backend.extract(args.input)
    except FileNotFoundError:
        print(f"error: input file not found: {args.input}", file=sys.stderr)
        return 2
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    result: ExtractionResult = extract_fields(blocks, source=str(Path(args.input)))

    payload = result.to_dict()
    payload["review_queue"] = result.review_queue(args.min_confidence)
    payload["min_confidence"] = args.min_confidence

    text = json.dumps(payload, indent=args.indent, default=str)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()

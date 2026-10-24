"""End-to-end: synthetic receipt images -> real Tesseract -> extracted fields.

The images are drawn at test time with Pillow's bundled font (no image files
are committed). These tests need the optional ``ocr`` extra *and* the system
``tesseract`` binary with English data; without them they are reported as
SKIPPED, never as passed. Run them explicitly with:

    pip install -e ".[dev,ocr]"      # plus the tesseract binary
    pytest tests/test_tesseract_integration.py -rs
"""

from __future__ import annotations

import importlib.util
import shutil
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

HAVE_TESSERACT = (
    shutil.which("tesseract") is not None
    and importlib.util.find_spec("pytesseract") is not None
    and importlib.util.find_spec("PIL") is not None
)

pytestmark = pytest.mark.skipif(
    not HAVE_TESSERACT,
    reason="needs the 'ocr' extra (pytesseract, Pillow) and the tesseract binary",
)


@dataclass(frozen=True)
class Receipt:
    name: str
    lines: list[tuple[str, str]]  # (left text, right-aligned amount)
    vendor: str
    date: str
    currency: str
    total: str
    tax: str
    items: list[tuple[str, str]]


RECEIPTS = [
    Receipt(
        name="usd-iso-date",
        lines=[
            ("CORNER BAKERY", ""),
            ("12 High Street", ""),
            ("Date: 2024-03-14", ""),
            ("Sourdough Loaf", "$4.20"),
            ("Coffee Beans", "$12.50"),
            ("Subtotal", "$16.70"),
            ("Sales Tax", "$1.34"),
            ("TOTAL", "$18.04"),
            ("Thank you", ""),
        ],
        vendor="CORNER BAKERY",
        date="2024-03-14",
        currency="USD",
        total="18.04",
        tax="1.34",
        items=[("Sourdough Loaf", "4.20"), ("Coffee Beans", "12.50")],
    ),
    Receipt(
        name="eur-comma-decimals-dmy",
        lines=[
            ("CAFE LUMIERE", ""),
            ("Rue de la Paix 4", ""),
            ("Datum 14/03/2024", ""),
            ("Espresso", "2,80 EUR"),
            ("Croissant", "1,90 EUR"),
            ("Grand Menu", "1.234,50 EUR"),
            ("VAT", "198,42 EUR"),
            ("TOTAL", "1.239,20 EUR"),
        ],
        vendor="CAFE LUMIERE",
        date="2024-03-14",
        currency="EUR",
        total="1239.20",
        tax="198.42",
        items=[("Espresso", "2.80"), ("Croissant", "1.90"), ("Grand Menu", "1234.50")],
    ),
    Receipt(
        name="gbp-month-name-vat",
        lines=[
            ("NORTHGATE BOOKS", ""),
            ("14 Mar 2024", ""),
            # Amounts carry the ISO code: Pillow's bundled font renders "£"
            # in a way eng Tesseract reads as "k"/"X"/"&" (seen in testing).
            ("Paperback Novel", "8.99 GBP"),
            ("Notebook", "3.50 GBP"),
            ("VAT", "2.08 GBP"),
            ("TOTAL", "12.49 GBP"),
        ],
        vendor="NORTHGATE BOOKS",
        date="2024-03-14",
        currency="GBP",
        total="12.49",
        tax="2.08",
        items=[("Paperback Novel", "8.99"), ("Notebook", "3.50")],
    ),
]


def _render(receipt: Receipt, path: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.load_default(size=28)
    title = ImageFont.load_default(size=38)
    image = Image.new("L", (900, 60 + 48 * len(receipt.lines)), 255)
    draw = ImageDraw.Draw(image)
    for row, (left, right) in enumerate(receipt.lines):
        y = 30 + 48 * row
        draw.text((40, y), left, fill=0, font=title if row == 0 else font)
        if right:
            draw.text((860 - draw.textlength(right, font=font), y), right, fill=0, font=font)
    image.save(path)


@pytest.mark.parametrize("receipt", RECEIPTS, ids=[r.name for r in RECEIPTS])
def test_real_tesseract_extracts_the_fields(receipt: Receipt, tmp_path: Path) -> None:
    from receipt_ocr.backends import TesseractBackend
    from receipt_ocr.engine import extract_fields

    image = tmp_path / f"{receipt.name}.png"
    _render(receipt, image)
    result = extract_fields(TesseractBackend().extract(image), source=str(image))
    fields = result.fields

    assert fields["vendor"].value == receipt.vendor
    assert str(fields["date"].value) == receipt.date
    assert fields["currency"].value == receipt.currency
    assert fields["total"].value == Decimal(receipt.total)
    assert fields["tax"].value == Decimal(receipt.tax)
    items = [(i.description, str(i.amount)) for i in fields["line_items"].value]
    assert items == receipt.items


def test_cli_runs_the_tesseract_backend(tmp_path: Path) -> None:
    import json
    import subprocess
    import sys

    image = tmp_path / "receipt.png"
    _render(RECEIPTS[0], image)
    completed = subprocess.run(
        [sys.executable, "-m", "receipt_ocr.cli", str(image), "--backend", "tesseract"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["fields"]["total"]["value"] == "18.04"

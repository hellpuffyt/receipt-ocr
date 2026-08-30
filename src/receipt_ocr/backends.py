"""OCR backends: turn an image (or pre-extracted JSON) into TextBlocks.

The extraction engine never talks to an OCR engine directly -- it only
consumes ``list[TextBlock]``. That keeps the interesting logic (field
extraction) fully testable without any native OCR dependency installed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, runtime_checkable

from receipt_ocr.models import TextBlock


@runtime_checkable
class OcrBackend(Protocol):
    """Anything that can turn an image path into a list of TextBlocks."""

    def extract(self, image_path: str | Path) -> list[TextBlock]:
        ...


class JsonBackend:
    """Loads pre-extracted OCR blocks from a JSON file.

    This backend has zero native dependencies and is what the test suite
    and CI exercise. The expected JSON shape is either a bare list of block
    objects, or ``{"blocks": [...]}``:

    .. code-block:: json

        {
          "blocks": [
            {"text": "TOTAL", "left": 10, "top": 200, "width": 40, "height": 12,
             "confidence": 96.0},
            {"text": "$42.10", "left": 60, "top": 200, "width": 50, "height": 12,
             "confidence": 91.5}
          ]
        }

    Missing ``confidence`` defaults to 100.0; missing ``page`` defaults to 0.
    """

    def extract(self, image_path: str | Path) -> list[TextBlock]:
        path = Path(image_path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        return blocks_from_json(raw)


def blocks_from_json(raw: object) -> list[TextBlock]:
    """Convert a parsed JSON document (list or {"blocks": [...]}) to TextBlocks."""
    if isinstance(raw, dict):
        items = raw.get("blocks", [])
    elif isinstance(raw, list):
        items = raw
    else:
        raise ValueError("JSON OCR input must be a list or an object with a 'blocks' key")

    blocks: list[TextBlock] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"block #{i} is not a JSON object")
        try:
            block = TextBlock(
                text=str(item["text"]),
                left=float(item["left"]),
                top=float(item["top"]),
                width=float(item["width"]),
                height=float(item["height"]),
                confidence=float(item.get("confidence", 100.0)),
                page=int(item.get("page", 0)),
                index=int(item.get("index", i)),
            )
        except KeyError as exc:
            raise ValueError(f"block #{i} missing required field {exc}") from exc
        blocks.append(block)
    return blocks


class TesseractBackend:
    """OCR backend backed by pytesseract + Pillow.

    This import is optional: the package installs and the JSON-driven
    parts of the CLI/tests work with zero native dependencies. Only
    constructing this class (or calling ``extract``) requires
    ``pytesseract`` (and the system ``tesseract`` binary) plus ``Pillow``
    to actually be installed.
    """

    def __init__(self, lang: str = "eng", tesseract_cmd: str | None = None) -> None:
        try:
            import pytesseract  # noqa: F401
        except ImportError as exc:  # pragma: no cover - exercised only without extras
            raise RuntimeError(
                "TesseractBackend requires the 'ocr' extra: "
                "install with `pip install receipt-ocr[ocr]`, and make sure the "
                "tesseract binary is installed on your system "
                "(https://tesseract-ocr.github.io/tessdoc/Installation.html)."
            ) from exc
        self.lang = lang
        self.tesseract_cmd = tesseract_cmd

    def extract(self, image_path: str | Path) -> list[TextBlock]:  # pragma: no cover
        try:
            import pytesseract
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError(
                "TesseractBackend requires the 'ocr' extra: "
                "install with `pip install receipt-ocr[ocr]`."
            ) from exc

        if self.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd

        image = Image.open(image_path)
        data = pytesseract.image_to_data(
            image, lang=self.lang, output_type=pytesseract.Output.DICT
        )

        blocks: list[TextBlock] = []
        n = len(data["text"])
        for i in range(n):
            text = data["text"][i].strip()
            if not text:
                continue
            conf_raw = data["conf"][i]
            try:
                conf = float(conf_raw)
            except (TypeError, ValueError):
                conf = 0.0
            if conf < 0:
                conf = 0.0
            blocks.append(
                TextBlock(
                    text=text,
                    left=float(data["left"][i]),
                    top=float(data["top"][i]),
                    width=float(data["width"][i]),
                    height=float(data["height"][i]),
                    confidence=conf,
                    page=0,
                    index=len(blocks),
                )
            )
        return blocks

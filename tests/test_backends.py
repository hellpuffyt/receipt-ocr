import json
from pathlib import Path

import pytest

from receipt_ocr.backends import JsonBackend, OcrBackend, TesseractBackend, blocks_from_json


class TestBlocksFromJson:
    def test_parses_bare_list(self) -> None:
        raw = [{"text": "TOTAL", "left": 1, "top": 2, "width": 3, "height": 4}]
        blocks = blocks_from_json(raw)
        assert len(blocks) == 1
        assert blocks[0].text == "TOTAL"
        assert blocks[0].confidence == 100.0

    def test_parses_wrapped_object(self) -> None:
        raw = {"blocks": [{"text": "TOTAL", "left": 1, "top": 2, "width": 3, "height": 4}]}
        blocks = blocks_from_json(raw)
        assert len(blocks) == 1

    def test_confidence_and_page_default(self) -> None:
        raw = [{"text": "X", "left": 0, "top": 0, "width": 1, "height": 1}]
        blocks = blocks_from_json(raw)
        assert blocks[0].confidence == 100.0
        assert blocks[0].page == 0

    def test_explicit_confidence_preserved(self) -> None:
        raw = [{"text": "X", "left": 0, "top": 0, "width": 1, "height": 1, "confidence": 42.5}]
        blocks = blocks_from_json(raw)
        assert blocks[0].confidence == 42.5

    def test_missing_required_field_raises(self) -> None:
        raw = [{"text": "X", "left": 0, "top": 0, "width": 1}]  # missing height
        with pytest.raises(ValueError, match="missing required field"):
            blocks_from_json(raw)

    def test_non_dict_block_raises(self) -> None:
        raw = ["not a dict"]
        with pytest.raises(ValueError, match="not a JSON object"):
            blocks_from_json(raw)

    def test_invalid_top_level_raises(self) -> None:
        with pytest.raises(ValueError, match="list or an object"):
            blocks_from_json("nonsense")

    def test_index_defaults_to_position(self) -> None:
        raw = [
            {"text": "A", "left": 0, "top": 0, "width": 1, "height": 1},
            {"text": "B", "left": 0, "top": 0, "width": 1, "height": 1},
        ]
        blocks = blocks_from_json(raw)
        assert [b.index for b in blocks] == [0, 1]


class TestJsonBackend:
    def test_loads_from_file(self, tmp_path: Path) -> None:
        payload = {"blocks": [{"text": "TOTAL", "left": 1, "top": 2, "width": 3, "height": 4}]}
        path = tmp_path / "blocks.json"
        path.write_text(json.dumps(payload), encoding="utf-8")

        backend = JsonBackend()
        blocks = backend.extract(path)
        assert len(blocks) == 1
        assert blocks[0].text == "TOTAL"

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        backend = JsonBackend()
        with pytest.raises(FileNotFoundError):
            backend.extract(tmp_path / "does_not_exist.json")

    def test_satisfies_ocr_backend_protocol(self) -> None:
        assert isinstance(JsonBackend(), OcrBackend)


class TestTesseractBackend:
    def test_construction_may_raise_if_pytesseract_missing(self) -> None:
        # We don't assert either way on the *outcome* (pytesseract may or may
        # not be installed in the environment running these tests), only
        # that constructing it never raises anything other than a clear
        # RuntimeError with actionable guidance.
        try:
            backend = TesseractBackend()
        except RuntimeError as exc:
            assert "ocr" in str(exc)
            assert "tesseract" in str(exc).lower()
        else:
            assert backend.lang == "eng"

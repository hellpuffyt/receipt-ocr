import json
from pathlib import Path

from receipt_ocr.cli import build_parser, run

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "sample_receipt.json"


class TestCliParser:
    def test_default_backend_is_json(self) -> None:
        args = build_parser().parse_args([str(SAMPLE)])
        assert args.backend == "json"

    def test_default_min_confidence(self) -> None:
        args = build_parser().parse_args([str(SAMPLE)])
        assert args.min_confidence == 0.6

    def test_min_confidence_override(self) -> None:
        args = build_parser().parse_args([str(SAMPLE), "--min-confidence", "0.9"])
        assert args.min_confidence == 0.9


class TestCliRun:
    def test_run_prints_json_to_stdout(self, capsys: object) -> None:
        exit_code = run([str(SAMPLE)])
        assert exit_code == 0
        captured = capsys.readouterr()  # type: ignore[attr-defined]
        payload = json.loads(captured.out)
        assert payload["fields"]["total"]["value"] == "119.55"

    def test_run_writes_to_output_file(self, tmp_path: Path) -> None:
        out_path = tmp_path / "out.json"
        exit_code = run([str(SAMPLE), "-o", str(out_path)])
        assert exit_code == 0
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        assert payload["fields"]["vendor"]["value"] == "GREENLEAF MARKET"

    def test_run_missing_file_returns_error_code(self, tmp_path: Path, capsys: object) -> None:
        missing = tmp_path / "does_not_exist.json"
        exit_code = run([str(missing)])
        assert exit_code == 2

    def test_run_includes_review_queue(self) -> None:
        exit_code = run([str(SAMPLE), "--min-confidence", "0.99"])
        assert exit_code == 0

    def test_run_with_high_min_confidence_flags_fields(self, capsys: object) -> None:
        run([str(SAMPLE), "--min-confidence", "0.99"])
        captured = capsys.readouterr()  # type: ignore[attr-defined]
        payload = json.loads(captured.out)
        assert len(payload["review_queue"]) > 0

    def test_unknown_backend_rejected_by_argparse(self) -> None:
        import pytest

        with pytest.raises(SystemExit):
            build_parser().parse_args([str(SAMPLE), "--backend", "nonsense"])

import json
lazy from pathlib import Path

import pytest

from validator.cli import main

from .helpers import load_case, save_dataset


@pytest.mark.parametrize(
    "kind", ["missing", "corrupt", "existing", "zero_limit"]
)
def test_cli_input_failures_are_code_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], kind: str
) -> None:
    dataset = save_dataset(tmp_path / "corpus", [load_case()])
    output = tmp_path / "result"
    extra = []
    if kind == "missing":
        dataset = tmp_path / "missing"
    elif kind == "corrupt":
        (dataset / "manifest.json").write_text("not JSON")
    elif kind == "existing":
        output.mkdir()
        (output / "keep").write_text("preserve")
    else:
        extra = ["--limit", "0"]
    assert (
        main(["validate", str(dataset), "--output", str(output), *extra]) == 2
    )
    assert capsys.readouterr().err
    if kind == "existing":
        assert (output / "keep").read_text() == "preserve"
    else:
        assert not output.exists()


def test_cli_validates_and_reports_partial_coverage(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dataset = save_dataset(tmp_path / "corpus", [load_case()])
    code = main(
        ["validate", str(dataset), "--output", str(tmp_path / "result")]
    )
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["counts"]["passed"] == 1
    assert report["field_counts"]["event_score_deltas"] == {"unsupported": 1}

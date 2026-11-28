import json
from typing import TYPE_CHECKING
lazy from pathlib import Path

import pytest
from validator.cli import main

if TYPE_CHECKING:
    from collections.abc import Callable

    from corpus.models import ScoringCase


@pytest.mark.parametrize(
    "kind", ["missing", "corrupt", "existing", "zero_limit"]
)
def test_cli_input_failures_are_code_two(
    load_case: Callable[..., ScoringCase],
    save_dataset: Callable[[Path, list[ScoringCase]], Path],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    kind: str,
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
    load_case: Callable[..., ScoringCase],
    save_dataset: Callable[[Path, list[ScoringCase]], Path],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    dataset = save_dataset(tmp_path / "corpus", [load_case()])
    output = tmp_path / "results" / "scoring" / "validation"
    code = main(["validate", str(dataset), "--output", str(output)])
    assert code == 0
    assert (output / "summary.json").is_file()
    report = json.loads(capsys.readouterr().out)
    assert report["counts"]["passed"] == 1
    assert report["field_counts"]["event_score_deltas"] == {"unsupported": 1}


@pytest.mark.parametrize(
    "arguments",
    [
        ["validate"],
        ["benchmark", "--samples", "1"],
        ["profile", "--method", "tracing"],
    ],
)
def test_cli_writes_only_the_final_summary(
    load_case: Callable[..., ScoringCase],
    save_dataset: Callable[[Path, list[ScoringCase]], Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    arguments: list[str],
) -> None:
    dataset = save_dataset(tmp_path / "corpus", [load_case()])
    output = tmp_path / "result"
    write_text = Path.write_text
    summaries = []

    def record_write(
        path: Path, data: str, *, encoding: str | None = None
    ) -> int:
        if path.name == "summary.json":
            summaries.append(json.loads(data))
        return write_text(path, data, encoding=encoding)

    monkeypatch.setattr(Path, "write_text", record_write)
    code = main(
        [
            arguments[0],
            str(dataset),
            "--output",
            str(output),
            "--limit",
            "1",
            *arguments[1:],
        ]
    )
    assert code == 0
    report = json.loads((output / "summary.json").read_bytes())
    assert report["purpose"] == arguments[0]
    assert summaries == [report]
    assert (output / "cases.jsonl").is_file()

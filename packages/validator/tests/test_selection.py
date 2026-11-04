import json
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from corpus import CorpusError, read_dataset

from validator import Selection, validate_dataset
from validator.validation import validate_case

from .helpers import load_case, save_dataset

if TYPE_CHECKING:
    from collections.abc import Iterator

    from corpus.models import ScoringCase


def test_case_id_filter_keeps_duplicates_and_zero_selection_fails(
    tmp_path: Path,
) -> None:
    case = load_case()
    dataset = save_dataset(tmp_path / "corpus", [case, case])
    selected = validate_dataset(
        dataset,
        tmp_path / "selected",
        selection=Selection(case_ids=(case["case_id"],)),
    )
    assert selected["selected_count"] == 2
    empty = validate_dataset(
        dataset,
        tmp_path / "empty",
        selection=Selection(case_ids=("not-present",)),
    )
    assert empty["exit_code"] == 1
    assert empty["scanned_count"] == 2
    assert empty["selected_count"] == 0


def test_validation_consumes_cases_incrementally(tmp_path: Path) -> None:
    dataset = save_dataset(tmp_path / "corpus", [load_case(), load_case()])
    with patch(
        "validator.validation.validate_case", wraps=validate_case
    ) as validate:

        def cases(directory: Path) -> Iterator[ScoringCase]:
            for index, case in enumerate(read_dataset(directory)):
                assert validate.call_count == index
                yield case

        with patch("validator.validation.read_dataset", side_effect=cases):
            summary = validate_dataset(dataset, tmp_path / "result")
    assert summary["counts"]["passed"] == 2


@pytest.mark.parametrize(
    "failure", [KeyboardInterrupt(), OSError("write failed")]
)
def test_interruption_and_write_failure_do_not_publish(
    tmp_path: Path, failure: BaseException
) -> None:
    dataset = save_dataset(tmp_path / "corpus", [load_case()])
    output = tmp_path / "result"
    target = (
        "pathlib.Path.write_text"
        if isinstance(failure, OSError)
        else "validator.validation.validate_case"
    )
    with patch(target, side_effect=failure), pytest.raises(type(failure)):
        validate_dataset(dataset, output)
    assert not output.exists()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["corpus"]


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_invalid_limit_is_rejected(limit: int) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        Selection(limit=limit)


def test_summary_identifies_inputs_environment_and_partial_coverage(
    tmp_path: Path,
) -> None:
    dataset = save_dataset(tmp_path / "corpus", [load_case(), load_case()])
    first = validate_dataset(dataset, tmp_path / "first")
    second = validate_dataset(dataset, tmp_path / "second")
    assert first["selection_sha256"] == second["selection_sha256"]
    assert len(first["selection_sha256"]) == 64
    assert first["corpus"]["manifest"]["record_count"] == 2
    assert first["environment"]["mahjong_version"] == version("mahjong")
    assert Path(first["environment"]["mahjong_path"]).is_dir()
    assert first["field_counts"]["event_score_deltas"] == {"unsupported": 2}
    assert first["field_counts"]["fu"] == {"matched": 2}
    assert first["complete"] is True


@pytest.mark.parametrize("kind", ["hash", "count"])
def test_later_corruption_after_limit_never_publishes_result(
    tmp_path: Path,
    kind: str,
) -> None:
    dataset = save_dataset(tmp_path / "corpus", [load_case(), load_case()])
    manifest = json.loads((dataset / "manifest.json").read_text())
    if kind == "hash":
        (dataset / manifest["files"][1]["path"]).write_bytes(b"broken")
    else:
        manifest["files"][1]["record_count"] = 2
        manifest["record_count"] = 3
        (dataset / "manifest.json").write_text(json.dumps(manifest))
    output = tmp_path / "result"
    with pytest.raises(CorpusError):
        validate_dataset(dataset, output, selection=Selection(limit=1))
    assert not output.exists()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["corpus"]


def test_filter_before_limit_retains_global_position_and_checks_all(
    tmp_path: Path,
) -> None:
    case = load_case("synthetic-sanma-tsumo")
    dataset = save_dataset(tmp_path / "corpus", [load_case(), case, case])
    output = tmp_path / "result"
    summary = validate_dataset(
        dataset, output, selection=Selection(player_count=3, limit=1)
    )
    assert summary["scanned_count"] == 3
    assert summary["selected_count"] == 1
    assert summary["counts"]["passed"] == 1
    result = json.loads((output / "cases.jsonl").read_text())
    assert result["position"] == 2
    assert result["case_id"] == case["case_id"]

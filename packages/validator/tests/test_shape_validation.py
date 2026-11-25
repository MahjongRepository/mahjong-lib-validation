import json
from pathlib import Path
from pstats import Stats
from typing import TYPE_CHECKING

import pytest
from corpus import write_dataset
from tenhou_converter import convert_files
from validator import (
    Selection,
    benchmark_dataset,
    profile_dataset,
    validate_dataset,
)
from validator.cli import main

if TYPE_CHECKING:
    from corpus import AgariCase, ShantenCase
    from tenhou_converter.conversion import ShapeTarget


@pytest.mark.parametrize("expected", [True, False])
def test_validate_14_tile_shape_with_ankan(
    tmp_path: Path, *, expected: bool
) -> None:
    case: AgariCase = {
        "schema_version": "v1",
        "case_type": "agari",
        "case_id": "four-melds-and-two-tiles",
        "source": {"platform": "tenhou", "log_id": "test", "event_index": 1},
        "player_count": 4,
        "input": {
            "concealed_tiles": [
                "4m",
                "5m",
                "6m",
                "7p",
                "8p",
                "9p",
                "1s",
                "2s",
                "3s",
                "1z" if expected else "2z",
                "1z",
            ],
            "melds": [
                {
                    "type": "ankan",
                    "tiles": ["1m"] * 4,
                    "called_tile_index": None,
                    "from_seat": None,
                }
            ],
        },
        "expected": {"is_agari": expected},
    }
    dataset = tmp_path / "dataset"
    write_dataset(
        dataset,
        [case],
        generator={"name": "test", "version": "1", "settings": {}},
        conversion={
            "input_count": 1,
            "converted_count": 1,
            "failed_by_reason": {},
            "excluded_by_reason": {},
        },
    )
    summary = validate_dataset(dataset, tmp_path / "result")
    assert summary["case_type"] == "agari"
    assert summary["field_counts"] == {"is_agari": {"matched": 1}}
    assert summary["exit_code"] == 0


@pytest.mark.parametrize(
    ("target", "case_type", "field", "expected"),
    [
        ("agari-tenpai", "agari", "is_agari", False),
        ("shanten-tenpai", "shanten", "shanten", 0),
        ("shanten-agari", "shanten", "shanten", -1),
    ],
)
def test_cli_validates_generated_cases(
    tmp_path: Path,
    target: ShapeTarget,
    case_type: str,
    field: str,
    expected: object,
) -> None:
    log = (
        Path(__file__).parents[2]
        / "tenhou-converter/tests/fixtures/sanma-three-nuki.xml"
    )
    dataset = tmp_path / "dataset"
    convert_files(log, dataset, target=target)
    output = tmp_path / "validate"
    assert (
        main(
            [
                "validate",
                str(dataset),
                "--player-count",
                "3",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    (line,) = (output / "cases.jsonl").read_text(encoding="utf-8").splitlines()
    result = json.loads(line)["fields"][field]
    assert result == {
        "status": "matched",
        "expected": expected,
        "actual": expected,
    }
    assert type(result["actual"]) is type(expected)
    assert (
        json.loads((output / "summary.json").read_bytes())["case_type"]
        == case_type
    )


@pytest.mark.parametrize(
    ("target", "case_type", "function_name"),
    [
        ("agari-complete", "agari", "is_agari"),
        ("shanten-tenpai", "shanten", "calculate_shanten"),
    ],
)
def test_measures_generated_cases(
    tmp_path: Path, target: ShapeTarget, case_type: str, function_name: str
) -> None:
    log = (
        Path(__file__).parents[2]
        / "tenhou-converter/tests/fixtures/four-ron.xml"
    )
    dataset = tmp_path / "dataset"
    convert_files(log, dataset, target=target)
    selection = Selection(limit=1)
    benchmark = benchmark_dataset(
        dataset, tmp_path / "benchmark", selection=selection, samples=1
    )
    assert (
        benchmark["case_type"]
        == benchmark["preflight"]["case_type"]
        == case_type
    )
    assert benchmark["complete"] is True
    assert benchmark["sample_count"] == 1

    output = tmp_path / "profile"
    profile = profile_dataset(
        dataset, output, selection=selection, method="tracing"
    )
    assert profile["case_type"] == case_type
    assert profile["preflight"]["case_type"] == case_type
    assert profile["processed_count"] == 1
    functions = (
        Stats(str(output / "profile.pstats")).get_stats_profile().func_profiles
    )
    assert functions[function_name].ncalls == "1"
    assert "prepare_agari_call" not in functions
    assert "prepare_shanten_call" not in functions


def test_shanten_positive_and_failed_preflight(tmp_path: Path) -> None:
    case: ShantenCase = {
        "schema_version": "v1",
        "case_type": "shanten",
        "case_id": "one-away-from-tenpai",
        "source": {"platform": "tenhou", "log_id": "test", "event_index": 1},
        "player_count": 4,
        "input": {
            "concealed_tiles": [
                "1m",
                "2m",
                "3m",
                "4p",
                "0p",
                "6p",
                "7s",
                "8s",
                "9s",
                "1z",
                "1z",
                "2z",
                "3z",
            ],
            "melds": [],
        },
        "expected": {"shanten": 0},
    }
    dataset = tmp_path / "dataset"
    write_dataset(
        dataset,
        [case],
        generator={"name": "test", "version": "1", "settings": {}},
        conversion={
            "input_count": 1,
            "converted_count": 1,
            "failed_by_reason": {},
            "excluded_by_reason": {},
        },
    )
    output = tmp_path / "benchmark"
    summary = benchmark_dataset(
        dataset, output, selection=Selection(limit=1), samples=1
    )
    assert summary["exit_code"] == 1
    assert summary["sample_count"] == 0
    (line,) = (output / "cases.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(line)["fields"]["shanten"] == {
        "status": "mismatched",
        "expected": 0,
        "actual": 1,
    }

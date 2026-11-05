import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from corpus import parse_case, write_dataset
from mahjong.hand_calculating.hand_response import HandResponse
from validator import validate_dataset
from validator.adapter import calculate, prepare_hand

if TYPE_CHECKING:
    from collections.abc import Callable

    from corpus.models import ScoringCase


@pytest.mark.parametrize("kind", ["unknown", "unsupported", "no_expectations"])
def test_all_unvalidated_cases_do_not_pass(
    load_case: Callable[..., ScoringCase],
    save_dataset: Callable[[Path, list[ScoringCase]], Path],
    tmp_path: Path,
    kind: str,
) -> None:
    case = load_case()
    if kind == "unsupported":
        case = load_case("majsoul-scoring")
    elif kind == "unknown":
        case["input"]["situation"]["riichi"] = None
        case["situation_provenance"]["unknown_fields"] = {
            "riichi": "missing events"
        }
    else:
        case["comparison"]["excluded_fields"] = [
            {"field": field, "reason": "test"} for field in case["expected"]
        ]
    dataset = save_dataset(tmp_path / "corpus", [case])
    summary = validate_dataset(dataset, tmp_path / "result")
    assert summary["exit_code"] == 1
    assert summary["counts"]["passed"] == 0


def test_impossible_red_tile_allocation_is_a_case_error(
    load_case: Callable[..., ScoringCase],
    save_dataset: Callable[[Path, list[ScoringCase]], Path],
    tmp_path: Path,
) -> None:
    case = load_case()
    case["input"]["concealed_tiles"] = [
        "5m",
        "5m",
        "5m",
        "5m",
        "1p",
        "2p",
        "3p",
        "4p",
        "6p",
        "7p",
        "1s",
        "2s",
        "3s",
    ]
    dataset = save_dataset(tmp_path / "corpus", [case, load_case()])
    summary = validate_dataset(dataset, tmp_path / "result")
    assert summary["counts"]["error"] == 1
    assert summary["counts"]["passed"] == 1


@pytest.mark.parametrize(
    "failure", [HandResponse(error="bad_hand"), RuntimeError("boom")]
)
def test_calculation_failure_is_saved_and_next_case_runs(
    load_case: Callable[..., ScoringCase],
    save_dataset: Callable[[Path, list[ScoringCase]], Path],
    tmp_path: Path,
    failure: HandResponse | Exception,
) -> None:
    dataset = save_dataset(tmp_path / "corpus", [load_case(), load_case()])
    case = load_case()
    good = calculate(
        prepare_hand(case["input"], case["round"], 4, case["ruleset"])
    )
    with patch("validator.validation.calculate", side_effect=[failure, good]):
        summary = validate_dataset(dataset, tmp_path / "result")
    assert summary["counts"]["error"] == 1
    assert summary["counts"]["passed"] == 1
    assert summary["exit_code"] == 1


def test_unknown_input_is_skipped_and_majsoul_is_unsupported(
    load_case: Callable[..., ScoringCase],
    save_dataset: Callable[[Path, list[ScoringCase]], Path],
    tmp_path: Path,
) -> None:
    unknown = load_case()
    unknown["input"]["situation"]["ippatsu"] = None
    unknown["situation_provenance"]["unknown_fields"] = {
        "ippatsu": "missing events"
    }
    dataset = save_dataset(
        tmp_path / "corpus",
        [load_case(), unknown, load_case("majsoul-scoring")],
    )
    summary = validate_dataset(dataset, tmp_path / "result")
    assert summary["counts"] == {
        "passed": 1,
        "mismatch": 0,
        "error": 0,
        "unsupported": 1,
        "skipped": 1,
    }
    assert summary["exit_code"] == 1


@pytest.mark.parametrize(
    "name", ["tenhou-kokushi", "synthetic-yakuman-ippatsu"]
)
def test_kokushi_uses_recorded_fu_exclusion(
    load_case: Callable[..., ScoringCase],
    save_dataset: Callable[[Path, list[ScoringCase]], Path],
    tmp_path: Path,
    name: str,
) -> None:
    dataset = save_dataset(tmp_path / "corpus", [load_case(name)])
    output = tmp_path / "result"
    summary = validate_dataset(dataset, output)
    assert summary["exit_code"] == 0
    result = json.loads((output / "cases.jsonl").read_text())
    assert result["fields"]["fu"]["status"] == "excluded"
    assert result["fields"]["han"]["status"] == "unavailable"
    assert result["fields"]["yakuman_multiplier"]["actual"] == 1


def test_sanma_tsumo_nuki_and_red_dora(
    load_case: Callable[..., ScoringCase],
    save_dataset: Callable[[Path, list[ScoringCase]], Path],
    tmp_path: Path,
) -> None:
    dataset = save_dataset(
        tmp_path / "corpus", [load_case("synthetic-sanma-tsumo")]
    )
    output = tmp_path / "result"
    summary = validate_dataset(dataset, output)
    assert summary["counts"]["passed"] == 1
    result = json.loads((output / "cases.jsonl").read_text())
    assert result["fields"]["han"]["actual"] == 5
    assert result["fields"]["payments_by_seat"]["actual"] == [4000, 0, 2000]


def test_yaku_identity_is_compared_even_when_han_matches(
    tmp_path: Path,
) -> None:
    fixture = (
        Path(__file__).parents[2] / "corpus/tests/fixtures/tenhou-scoring.json"
    )
    case = parse_case(json.loads(fixture.read_text(encoding="utf-8")))
    assert case["expected"]["yaku"] is not None
    case["expected"]["yaku"][0]["id"] = "pinfu"
    dataset = tmp_path / "corpus"
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
    output = tmp_path / "result"
    summary = validate_dataset(dataset, output)
    assert summary["counts"]["mismatch"] == 1
    assert summary["exit_code"] == 1
    result = json.loads((output / "cases.jsonl").read_text())
    assert result["fields"]["yaku"]["status"] == "mismatched"
    assert result["fields"]["han"]["status"] == "matched"


def test_validate_ron_from_corpus(tmp_path: Path) -> None:
    fixture = (
        Path(__file__).parents[2] / "corpus/tests/fixtures/tenhou-scoring.json"
    )
    case = parse_case(json.loads(fixture.read_text(encoding="utf-8")))
    dataset = tmp_path / "corpus"
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
    output = tmp_path / "result"
    summary = validate_dataset(dataset, output)
    assert summary["counts"] == {
        "passed": 1,
        "mismatch": 0,
        "error": 0,
        "unsupported": 0,
        "skipped": 0,
    }
    assert summary["exit_code"] == 0
    assert json.loads((output / "summary.json").read_text()) == summary
    result = json.loads((output / "cases.jsonl").read_text())
    assert result["fields"]["fu"] == {
        "status": "matched",
        "expected": 40,
        "actual": 40,
    }
    assert result["fields"]["winner_gain"]["actual"] == 3600

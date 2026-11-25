import json
from pathlib import Path
from typing import TYPE_CHECKING, assert_never, cast

from corpus import file_sha256, read_dataset, read_manifest

from validator.adapter import (
    MissingInputError,
    UnsupportedInputError,
    calculate,
    normalize_result,
    prepare_agari_call,
    prepare_scoring_case,
    prepare_shanten_call,
)
from validator.reporting import environment_info, result_directory
from validator.selection import Selection, SelectionScan
from validator.yaku import comparable_yaku

if TYPE_CHECKING:
    from collections.abc import Callable

    from corpus.models import (
        AgariCase,
        Case,
        Expected,
        ScoringCase,
        ShantenCase,
    )

    from validator.models import (
        CaseResult,
        CaseStatus,
        FieldResult,
        ValidationSummary,
    )
    from validator.selection import SelectedCase


def _unsupported_fields(case: ScoringCase) -> dict[str, str]:
    fields = {"event_score_deltas": "event aggregation is not implemented"}
    shared_allocation = any(
        entry["reason"] == "multiple_ron_allocation_unknown"
        for entry in case["comparison"]["excluded_fields"]
    )
    later_ron_with_bonus = (
        not case["input"]["situation"]["tsumo"]
        and case["win_number"] > 1
        and (case["round"]["honba"] > 0 or case["round"]["riichi_sticks"] > 0)
    )
    if shared_allocation or later_ron_with_bonus:
        fields.update(
            dict.fromkeys(
                (
                    "honba_points",
                    "riichi_stick_points",
                    "winner_gain",
                    "payments_by_seat",
                ),
                "individual multiple ron bonuses are not represented in input",
            )
        )
    return fields


def compare_result(
    case: ScoringCase, actual: Expected
) -> dict[str, FieldResult]:
    exclusions = {
        entry["field"]: entry["reason"]
        for entry in case["comparison"]["excluded_fields"]
    }
    fields: dict[str, FieldResult] = {}
    unsupported = _unsupported_fields(case)
    expected_values = cast("dict[str, object]", case["expected"])
    for name, value in actual.items():
        expected = expected_values[name]
        result: FieldResult = {
            "status": "matched",
            "expected": expected,
            "actual": value,
        }
        if name in exclusions:
            result.update(status="excluded", reason=exclusions[name])
        elif expected is None:
            result.update(
                status="unavailable", reason="expected value is not recorded"
            )
        elif name in unsupported:
            result.update(
                status="unsupported",
                reason=unsupported[name],
                actual=None,
            )
        else:
            left, right = expected, value
            if name == "yaku":
                expected_yaku = case["expected"]["yaku"]
                actual_yaku = actual["yaku"]
                if expected_yaku is not None and actual_yaku is not None:
                    left = comparable_yaku(expected_yaku)
                    right = comparable_yaku(actual_yaku)
            result["status"] = "matched" if left == right else "mismatched"
        fields[name] = result
    return fields


def validate_case(case: Case) -> CaseResult:
    match case["case_type"]:
        case "scoring":
            return _validate_scoring_case(case)
        case "agari":
            return _validate_value(
                case,
                "is_agari",
                expected=case["expected"]["is_agari"],
                prepare=prepare_agari_call,
            )
        case "shanten":
            return _validate_value(
                case,
                "shanten",
                expected=case["expected"]["shanten"],
                prepare=prepare_shanten_call,
            )
        case _ as case_type:
            assert_never(case_type)


def _validate_value[T: (AgariCase, ShantenCase)](
    case: T,
    name: str,
    *,
    expected: bool | int,
    prepare: Callable[[T], Callable[[], bool | int]],
) -> CaseResult:
    try:
        actual = prepare(case)()
    except Exception as e:  # noqa: BLE001 -- isolate target library failures
        return {
            "case_id": case["case_id"],
            "status": "error",
            "fields": {},
            "reason": f"{type(e).__name__}: {e}",
        }
    matched = type(actual) is type(expected) and actual == expected
    return {
        "case_id": case["case_id"],
        "status": "passed" if matched else "mismatch",
        "fields": {
            name: {
                "status": "matched" if matched else "mismatched",
                "expected": expected,
                "actual": actual,
            }
        },
    }


def _validate_scoring_case(case: ScoringCase) -> CaseResult:
    try:
        hand = prepare_scoring_case(case)
    except (MissingInputError, UnsupportedInputError) as e:
        return {
            "case_id": case["case_id"],
            "status": "skipped"
            if isinstance(e, MissingInputError)
            else "unsupported",
            "reason": str(e),
            "fields": {},
        }
    except ValueError as e:
        return {
            "case_id": case["case_id"],
            "status": "error",
            "fields": {},
            "reason": f"input preparation: {e}",
        }

    try:
        actual = normalize_result(hand, calculate(hand))
    except Exception as e:  # noqa: BLE001 -- isolate target library failures
        return {
            "case_id": case["case_id"],
            "status": "error",
            "fields": {},
            "reason": f"{type(e).__name__}: {e}",
        }

    fields = compare_result(case, actual)
    statuses = {field["status"] for field in fields.values()}
    status: CaseStatus = "skipped"
    if "mismatched" in statuses:
        status = "mismatch"
    elif "matched" in statuses:
        status = "passed"
    result: CaseResult = {
        "case_id": case["case_id"],
        "status": status,
        "fields": fields,
    }
    if status == "skipped":
        result["reason"] = "no comparable expectations"
    return result


def validate_dataset(
    dataset: str | Path,
    output: str | Path,
    *,
    selection: Selection | None = None,
) -> ValidationSummary:
    selection = selection or Selection()
    with result_directory(Path(output)) as staging:
        return _validate_dataset(dataset, staging, selection)


def _validate_dataset(
    dataset: str | Path,
    output: Path,
    selection: Selection,
    *,
    selected_cases: list[SelectedCase] | None = None,
) -> ValidationSummary:
    manifest_path = Path(dataset) / "manifest.json"
    manifest_sha256 = file_sha256(manifest_path)
    case_type = read_manifest(manifest_path)["case_type"]
    counts: dict[CaseStatus, int] = {
        "passed": 0,
        "mismatch": 0,
        "error": 0,
        "unsupported": 0,
        "skipped": 0,
    }
    scan = SelectionScan(selection, case_type)
    field_counts: dict[str, dict[str, int]] = {}

    with (output / "cases.jsonl").open("w", encoding="utf-8") as stream:
        for position, case in scan.select(read_dataset(dataset)):
            if selected_cases is not None:
                selected_cases.append((position, case))
            result = validate_case(case)
            result["position"] = position
            counts[result["status"]] += 1
            for name, field in result["fields"].items():
                statuses = field_counts.setdefault(name, {})
                statuses[field["status"]] = (
                    statuses.get(field["status"], 0) + 1
                )
            stream.write(json.dumps(result, ensure_ascii=False) + "\n")

    summary: ValidationSummary = {
        "counts": counts,
        "scanned_count": scan.scanned_count,
        "selected_count": scan.selected_count,
        "schema_version": "v1",
        "purpose": "validate",
        "case_type": case_type,
        "complete": True,
        "field_counts": field_counts,
        "selection_sha256": scan.selection_sha256,
        "selection": {
            "player_count": selection.player_count,
            "case_ids": list(selection.case_ids),
            "limit": selection.limit,
        },
        "corpus": {"manifest_sha256": manifest_sha256},
        "environment": environment_info(),
        "comparison_policy": (
            "v1: yaku dora+nuki_dora combined; "
            "event_score_deltas unsupported; "
            "indeterminate multiple ron allocation unsupported"
        )
        if case_type == "scoring"
        else "v1: exact comparison",
        "exit_code": int(
            not counts["passed"]
            or any(
                count for status, count in counts.items() if status != "passed"
            )
        ),
    }
    (output / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    return summary

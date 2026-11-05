import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, cast

from corpus import read_dataset, read_manifest

from validator.adapter import (
    MissingInputError,
    UnsupportedInputError,
    calculate,
    normalize_result,
    prepare_hand,
)
from validator.reporting import environment_info, result_directory
from validator.selection import Selection
from validator.yaku import comparable_yaku

if TYPE_CHECKING:
    from corpus.models import Expected, ScoringCase

    from validator.models import (
        CaseResult,
        CaseStatus,
        FieldResult,
        ValidationSummary,
    )


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
                expected_yaku, actual_yaku = (
                    case["expected"]["yaku"],
                    actual["yaku"],
                )
                if expected_yaku is not None and actual_yaku is not None:
                    left = comparable_yaku(expected_yaku)
                    right = comparable_yaku(actual_yaku)
            result["status"] = "matched" if left == right else "mismatched"
        fields[name] = result
    return fields


def validate_case(case: ScoringCase) -> CaseResult:
    try:
        hand = prepare_hand(
            case["input"], case["round"], case["player_count"], case["ruleset"]
        )
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
    dataset: str | Path, output: Path, selection: Selection
) -> ValidationSummary:
    manifest_path = Path(dataset) / "manifest.json"
    manifest = read_manifest(manifest_path)
    manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    counts: dict[CaseStatus, int] = {
        "passed": 0,
        "mismatch": 0,
        "error": 0,
        "unsupported": 0,
        "skipped": 0,
    }
    scanned = selected = 0
    digest = hashlib.sha256()
    field_counts: dict[str, dict[str, int]] = {}
    field_reasons: dict[str, dict[str, int]] = {}

    with (output / "cases.jsonl").open("w", encoding="utf-8") as stream:
        for scanned, case in enumerate(read_dataset(dataset), start=1):
            if not selection.matches(case, selected):
                continue
            selected += 1
            digest.update(
                (
                    json.dumps([scanned, case["case_id"]], ensure_ascii=False)
                    + "\n"
                ).encode("utf-8")
            )
            result = validate_case(case)
            result["position"] = scanned
            counts[result["status"]] += 1
            for name, field in result["fields"].items():
                statuses = field_counts.setdefault(name, {})
                statuses[field["status"]] = (
                    statuses.get(field["status"], 0) + 1
                )
                if "reason" in field:
                    reasons = field_reasons.setdefault(name, {})
                    reasons[field["reason"]] = (
                        reasons.get(field["reason"], 0) + 1
                    )
            stream.write(json.dumps(result, ensure_ascii=False) + "\n")

    summary: ValidationSummary = {
        "counts": counts,
        "scanned_count": scanned,
        "selected_count": selected,
        "schema_version": "v1",
        "purpose": "validate",
        "complete": True,
        "field_counts": field_counts,
        "field_reasons": field_reasons,
        "selection_sha256": digest.hexdigest(),
        "selection": {
            "player_count": selection.player_count,
            "case_ids": list(selection.case_ids),
            "limit": selection.limit,
        },
        "corpus": {"manifest": manifest, "manifest_sha256": manifest_sha256},
        "environment": environment_info(),
        "comparison_policy": (
            "v1: yaku dora+nuki_dora combined; "
            "event_score_deltas unsupported; "
            "indeterminate multiple ron allocation unsupported"
        ),
        "exit_code": int(
            not counts["passed"]
            or any(
                count for status, count in counts.items() if status != "passed"
            )
        ),
    }
    (output / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    return summary

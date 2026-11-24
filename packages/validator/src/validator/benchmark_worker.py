import hashlib
import json
import sys
from pathlib import Path
from time import perf_counter_ns
from typing import TYPE_CHECKING

from corpus import file_sha256, read_dataset

from validator.adapter import prepare_calculation, prepare_hand
from validator.selection import Selection, selection_digest_entry

if TYPE_CHECKING:
    from collections.abc import Callable

    from corpus.models import ScoringCase

    from validator.models import BenchmarkSample


def measure_batch(
    calls: list[tuple[int, str, Callable[[], object]]],
) -> BenchmarkSample:
    start = perf_counter_ns()
    try:
        for position, case_id, calculate in calls:  # noqa: B007 -- retain case identity on failure
            calculate()
    except Exception as error:  # noqa: BLE001 -- report library failures
        return {
            "status": "error",
            "position": position,
            "case_id": case_id,
            "reason": f"{type(error).__name__}: {error}",
        }
    elapsed_ns = perf_counter_ns() - start
    return {"status": "ok", "elapsed_ns": elapsed_ns}


def _prepare_calls(
    selected: list[tuple[int, ScoringCase]],
) -> list[tuple[int, str, Callable[[], object]]]:
    return [
        (
            position,
            case["case_id"],
            prepare_calculation(
                prepare_hand(
                    case["input"],
                    case["round"],
                    case["player_count"],
                    case["ruleset"],
                )
            ),
        )
        for position, case in selected
    ]


def _run() -> BenchmarkSample:
    request = json.load(sys.stdin)
    dataset = Path(request["dataset"])
    selection_args = request["selection"]
    selection = Selection(
        selection_args["player_count"],
        tuple(selection_args["case_ids"]),
        selection_args["limit"],
    )
    manifest_sha256 = file_sha256(dataset / "manifest.json")
    digest = hashlib.sha256()
    selected = []
    for position, case in enumerate(read_dataset(dataset), start=1):
        if selection.matches(case, len(selected)):
            digest.update(selection_digest_entry(position, case["case_id"]))
            selected.append((position, case))
    if (
        manifest_sha256 != request["manifest_sha256"]
        or digest.hexdigest() != request["selection_sha256"]
    ):
        msg = "benchmark worker selected a different dataset or case sequence"
        raise ValueError(msg)

    for _, _, calculate in _prepare_calls(selected):
        calculate()
        del calculate
    return measure_batch(_prepare_calls(selected))


if __name__ == "__main__":
    sys.stdout.write(json.dumps(_run()) + "\n")

import gc
import json
import os
import pickle
import sys
from pathlib import Path
from time import perf_counter_ns
from typing import TYPE_CHECKING

from validator.scoring_batch import prepare_calls, run_batch

if TYPE_CHECKING:
    from validator.scoring_batch import ScoringCall


def warm_and_check_inputs(calls: list[ScoringCall]) -> None:
    run_batch(calls)
    for position, case_id, calculate in calls:
        before = pickle.dumps(calculate)
        calculate()
        if pickle.dumps(calculate) != before:
            msg = f"prepared input changed at case {position} ({case_id})"
            raise ValueError(msg)


def wait_for_sampling() -> bool:
    return sys.stdin.readline() == "start\n"


def sample_batches(
    calls: list[ScoringCall], min_seconds: float
) -> tuple[int, int]:
    start = perf_counter_ns()
    repetitions = 0
    while True:
        run_batch(calls)
        repetitions += 1
        elapsed_ns = perf_counter_ns() - start
        if elapsed_ns / 1_000_000_000 >= min_seconds:
            return repetitions, elapsed_ns


def _run(request_path: Path) -> None:
    request = json.loads(request_path.read_text(encoding="utf-8"))
    calls = prepare_calls(request["selected"])
    warm_and_check_inputs(calls)
    gc_enabled = gc.isenabled()
    sys.stdout.write(f"ready {os.getpid()}\n")
    sys.stdout.flush()
    if wait_for_sampling():
        repetitions, elapsed_ns = sample_batches(calls, request["min_seconds"])
        sys.stdout.write(
            json.dumps(
                {
                    "repetitions": repetitions,
                    "elapsed_ns": elapsed_ns,
                    "gc_enabled": gc_enabled,
                }
            )
            + "\n",
        )


if __name__ == "__main__":
    _run(Path(sys.argv[1]))

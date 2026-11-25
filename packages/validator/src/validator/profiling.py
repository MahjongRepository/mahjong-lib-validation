import gc
import json
from pathlib import Path
from time import perf_counter_ns
from typing import TYPE_CHECKING
lazy from profiling.tracing import Profile

from validator.reporting import result_directory
from validator.scoring_batch import prepare_calls
from validator.validation import _validate_dataset

if TYPE_CHECKING:
    from corpus.models import ScoringCase

    from validator.models import ProfileSummary
    from validator.scoring_batch import ScoringCall
    from validator.selection import Selection


def _run_batch(calls: list[ScoringCall]) -> None:
    for _, _, calculate in calls:
        calculate()


def _collect_tracing(calls: list[ScoringCall], output: Path) -> int:
    try:
        profiler = Profile()
        start = perf_counter_ns()
        profiler.runcall(_run_batch, calls)
        elapsed_ns = perf_counter_ns() - start
        profiler.dump_stats(str(output))
    except Exception as e:
        msg = f"tracing collection failed: {type(e).__name__}: {e}"
        raise OSError(msg) from e
    return elapsed_ns


def profile_dataset(
    dataset: str | Path,
    output: str | Path,
    *,
    selection: Selection,
    method: str,
) -> ProfileSummary:
    if selection.limit is None:
        msg = "profile requires a positive limit"
        raise ValueError(msg)
    if method != "tracing":
        msg = f"method {method!r} is unavailable. Use --method tracing."
        raise ValueError(msg)

    with result_directory(Path(output)) as staging:
        selected: list[tuple[int, ScoringCase]] = []
        preflight = _validate_dataset(
            dataset, staging, selection, selected_cases=selected
        )
        exit_code = preflight["exit_code"]
        elapsed_ns = None
        processed_count = 0
        calls = prepare_calls(selected) if not exit_code else []
        gc_enabled = gc.isenabled()
        if not exit_code:
            elapsed_ns = _collect_tracing(calls, staging / "profile.pstats")
            processed_count = len(calls)
        summary: ProfileSummary = {
            "schema_version": "v1",
            "purpose": "profile",
            "complete": exit_code == 0,
            "exit_code": exit_code,
            "method": "tracing",
            "scope": "scoring_batch",
            "preflight": preflight,
            "settings": {
                "warmup_batches": 0,
                "reuse_inputs": False,
                "cache": "preserved_after_preflight",
                "gc_enabled": gc_enabled,
            },
            "case_count": preflight["selected_count"],
            "repetitions": int(exit_code == 0),
            "processed_count": processed_count,
            "elapsed_ns": elapsed_ns,
        }
        (staging / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False), encoding="utf-8"
        )

    return summary

import gc
import json
from math import isfinite
from pathlib import Path
from time import perf_counter_ns
from typing import TYPE_CHECKING
lazy from profiling.tracing import Profile

from validator.batch import run_batch
from validator.preparation import prepare_calls
from validator.reporting import result_directory
from validator.sampling_profile import collect_sampling
from validator.validation import collect_validation_results

if TYPE_CHECKING:
    from validator.batch import PreparedCall
    from validator.models import ProfileSettings, ProfileSummary
    from validator.selection import SelectedCase, Selection


MAX_SAMPLING_RATE_HZ = 1_000_000


def _collect_tracing(calls: list[PreparedCall], output: Path) -> int:
    try:
        profiler = Profile()
        start = perf_counter_ns()
        profiler.runcall(run_batch, calls)
        elapsed_ns = perf_counter_ns() - start
        profiler.dump_stats(str(output))
    except Exception as e:
        msg = f"tracing collection failed: {type(e).__name__}: {e}"
        raise OSError(msg) from e
    return elapsed_ns


def profile_dataset(  # noqa: PLR0913 -- dataset, selection and collection settings
    dataset: str | Path,
    output: str | Path,
    *,
    selection: Selection,
    method: str,
    min_seconds: float | None = None,
    sampling_rate_hz: int | None = None,
) -> ProfileSummary:
    if selection.limit is None:
        msg = "profile requires a positive limit"
        raise ValueError(msg)
    if method not in ("tracing", "sampling"):
        msg = f"method {method!r} is unavailable. Use --method tracing."
        raise ValueError(msg)
    if method == "tracing" and (
        min_seconds is not None or sampling_rate_hz is not None
    ):
        msg = "--min-seconds and --sampling-rate require --method sampling"
        raise ValueError(msg)
    duration = 3.0 if min_seconds is None else min_seconds
    rate = 1000 if sampling_rate_hz is None else sampling_rate_hz
    if not isfinite(duration) or duration <= 0:
        msg = "min-seconds must be finite and positive"
        raise ValueError(msg)
    if not 1 <= rate <= MAX_SAMPLING_RATE_HZ:
        msg = f"sampling-rate must be between 1 and {MAX_SAMPLING_RATE_HZ} Hz"
        raise ValueError(msg)

    with result_directory(Path(output)) as staging:
        selected: list[SelectedCase] = []
        preflight = collect_validation_results(
            dataset, staging, selection, selected_cases=selected
        )
        exit_code = preflight["exit_code"]
        elapsed_ns = None
        repetitions = 0
        sample_count = None

        settings: ProfileSettings
        if method == "tracing":
            settings = {
                "warmup_batches": 0,
                "reuse_inputs": False,
                "cache": "preserved_after_preflight",
                "gc_enabled": gc.isenabled(),
            }
            if not exit_code:
                calls = prepare_calls(selected)
                settings["gc_enabled"] = gc.isenabled()
                elapsed_ns = _collect_tracing(
                    calls, staging / "profile.pstats"
                )
                repetitions = 1
        else:
            settings = {
                "warmup_batches": 2,
                "reuse_inputs": True,
                "cache": "preserved_after_worker_warmup",
                "gc_enabled": gc.isenabled(),
                "min_seconds": duration,
                "sampling_rate_hz": rate,
                "synchronization_frames": ["wait_for_sampling"],
            }
            sample_count = 0
            if not exit_code:
                sample = collect_sampling(
                    selected,
                    staging / "profile.html",
                    min_seconds=duration,
                    rate_hz=rate,
                )
                repetitions = sample["repetitions"]
                elapsed_ns = sample["elapsed_ns"]
                sample_count = sample["sample_count"]
                settings["gc_enabled"] = sample["gc_enabled"]

        summary: ProfileSummary = {
            "case_type": preflight["case_type"],
            "schema_version": "v1",
            "purpose": "profile",
            "complete": exit_code == 0,
            "exit_code": exit_code,
            "method": method,
            "preflight": preflight,
            "settings": settings,
            "case_count": preflight["selected_count"],
            "repetitions": repetitions,
            "processed_count": repetitions * len(selected),
            "elapsed_ns": elapsed_ns,
        }
        if sample_count is not None:
            summary["sample_count"] = sample_count
        (staging / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False), encoding="utf-8"
        )

    return summary

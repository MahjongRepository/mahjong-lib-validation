from time import perf_counter_ns
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from validator.models import BenchmarkSample


type PreparedCall = tuple[int, str, Callable[[], object]]


def run_batch(calls: list[PreparedCall]) -> None:
    for _, _, calculate in calls:
        calculate()


def measure_batch(calls: list[PreparedCall]) -> BenchmarkSample:
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

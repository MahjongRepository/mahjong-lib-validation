import json
import subprocess
import sys
from pathlib import Path
from statistics import median, stdev
from typing import TYPE_CHECKING

from validator.reporting import result_directory
from validator.validation import _validate_dataset

if TYPE_CHECKING:
    from validator.models import (
        BenchmarkSample,
        BenchmarkStatistics,
        BenchmarkSummary,
        ValidationSummary,
    )
    from validator.selection import Selection


def _run_sample(
    dataset: str | Path, preflight: ValidationSummary
) -> BenchmarkSample:
    request = {
        "dataset": str(Path(dataset).resolve()),
        "selection": preflight["selection"],
        "manifest_sha256": preflight["corpus"]["manifest_sha256"],
        "selection_sha256": preflight["selection_sha256"],
    }
    worker = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "validator.benchmark_worker"],
        input=json.dumps(request),
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    if worker.returncode:
        msg = f"benchmark worker exited with code {worker.returncode}"
        if diagnostic := worker.stderr.strip():
            msg = f"{msg}: {diagnostic}"
        raise OSError(msg)
    return json.loads(worker.stdout)


def benchmark_dataset(
    dataset: str | Path,
    output: str | Path,
    *,
    selection: Selection,
    samples: int = 10,
) -> BenchmarkSummary:
    if selection.limit is None:
        msg = "benchmark requires a positive limit"
        raise ValueError(msg)
    if samples <= 0:
        msg = "samples must be positive"
        raise ValueError(msg)

    with result_directory(Path(output)) as staging:
        preflight = _validate_dataset(dataset, staging, selection)
        timings: list[BenchmarkSample] = []
        exit_code = preflight["exit_code"]
        if not exit_code:
            for _ in range(samples):
                sample = _run_sample(dataset, preflight)
                timings.append(sample)
                if sample["status"] == "error":
                    exit_code = 1
                    break

        statistics: BenchmarkStatistics | None = None
        if not exit_code:
            elapsed = [
                sample["elapsed_ns"]
                for sample in timings
                if sample["status"] == "ok"
            ]
            median_ns = median(elapsed)
            statistics = {
                "median_ns": median_ns,
                "min_ns": min(elapsed),
                "max_ns": max(elapsed),
                "stdev_ns": stdev(elapsed) if len(elapsed) > 1 else None,
                "cases_per_second": (
                    preflight["selected_count"] * 1_000_000_000 / median_ns
                    if median_ns
                    else None
                ),
            }
        summary: BenchmarkSummary = {
            "schema_version": "v1",
            "purpose": "benchmark",
            "complete": exit_code == 0,
            "exit_code": exit_code,
            "preflight": preflight,
            "settings": {
                "samples": samples,
                "warmup_batches": 1,
                "regenerate_inputs": True,
                "cache": "preserved_after_warmup",
                "gc_enabled": True,
            },
            "sample_count": len(timings),
            "statistics": statistics,
        }

        (staging / "timings.json").write_text(
            json.dumps({"samples": timings}, ensure_ascii=False),
            encoding="utf-8",
        )
        (staging / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False), encoding="utf-8"
        )

    return summary

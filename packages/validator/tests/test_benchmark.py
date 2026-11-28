import json
from typing import TYPE_CHECKING

from validator import Selection, benchmark_dataset
from validator.batch import measure_batch
from validator.cli import main

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    import pytest
    from corpus.models import ScoringCase


def test_empty_selection_stops_before_worker(
    load_case: Callable[..., ScoringCase],
    save_dataset: Callable[[Path, list[ScoringCase]], Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = save_dataset(tmp_path / "corpus", [load_case()])
    output = tmp_path / "result"

    def unexpected_worker(*_args: object, **_kwargs: object) -> None:
        msg = "empty selection must not start a worker"
        raise AssertionError(msg)

    monkeypatch.setattr("validator.benchmark._run_sample", unexpected_worker)
    assert (
        main(
            [
                "benchmark",
                str(dataset),
                "--output",
                str(output),
                "--limit",
                "1",
                "--case-id",
                "missing",
            ]
        )
        == 1
    )
    assert {path.name for path in output.iterdir()} == {
        "cases.jsonl",
        "summary.json",
        "timings.json",
    }
    assert (output / "cases.jsonl").read_text(encoding="utf-8") == ""
    assert json.loads((output / "timings.json").read_bytes()) == {
        "samples": []
    }
    summary = json.loads((output / "summary.json").read_bytes())
    assert summary["exit_code"] == 1
    assert summary["complete"] is False
    assert summary["preflight"]["exit_code"] == 1
    assert summary["preflight"]["selected_count"] == 0
    assert summary["sample_count"] == 0
    assert summary["statistics"] is None


def test_benchmark_saves_samples_from_workers(
    load_case: Callable[..., ScoringCase],
    save_dataset: Callable[[Path, list[ScoringCase]], Path],
    tmp_path: Path,
) -> None:
    dataset = save_dataset(tmp_path / "corpus", [load_case()])
    output = tmp_path / "result"
    summary = benchmark_dataset(
        dataset, output, selection=Selection(limit=1), samples=2
    )
    assert summary["exit_code"] == 0
    assert summary["sample_count"] == 2
    timings = json.loads((output / "timings.json").read_text(encoding="utf-8"))
    elapsed = [sample["elapsed_ns"] for sample in timings["samples"]]
    assert summary["statistics"] is not None
    assert summary["statistics"]["median_ns"] == sum(elapsed) / 2
    assert summary["preflight"]["selected_count"] == 1


def test_measurement_encloses_all_calls_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = []
    times = iter([100, 125])

    def clock() -> int:
        events.append("clock")
        return next(times)

    monkeypatch.setattr("validator.batch.perf_counter_ns", clock)
    result = measure_batch(
        [
            (1, "first", lambda: events.append("first")),
            (2, "second", lambda: events.append("second")),
        ]
    )
    assert events == ["clock", "first", "second", "clock"]
    assert result == {"status": "ok", "elapsed_ns": 25}


def test_measurement_reports_failed_case() -> None:
    def fail() -> None:
        msg = "calculation failed"
        raise RuntimeError(msg)

    assert measure_batch([(3, "third", fail)]) == {
        "status": "error",
        "position": 3,
        "case_id": "third",
        "reason": "RuntimeError: calculation failed",
    }


def test_failed_sample_stops_run_without_statistics(
    load_case: Callable[..., ScoringCase],
    save_dataset: Callable[[Path, list[ScoringCase]], Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = save_dataset(tmp_path / "corpus", [load_case()])
    output = tmp_path / "result"
    failure = {
        "status": "error",
        "position": 1,
        "case_id": "first",
        "reason": "RuntimeError: calculation failed",
    }
    samples = [{"status": "ok", "elapsed_ns": 25}, failure]
    worker = iter(samples)
    monkeypatch.setattr(
        "validator.benchmark._run_sample", lambda *_: next(worker)
    )

    assert (
        main(
            [
                "benchmark",
                str(dataset),
                "--output",
                str(output),
                "--limit",
                "1",
                "--samples",
                "3",
            ]
        )
        == 1
    )
    assert {path.name for path in output.iterdir()} == {
        "cases.jsonl",
        "summary.json",
        "timings.json",
    }
    summary = json.loads((output / "summary.json").read_bytes())
    assert summary["exit_code"] == 1
    assert summary["complete"] is False
    assert summary["preflight"]["exit_code"] == 0
    assert summary["sample_count"] == 2
    assert summary["statistics"] is None
    timings = json.loads((output / "timings.json").read_text(encoding="utf-8"))
    assert timings["samples"] == samples

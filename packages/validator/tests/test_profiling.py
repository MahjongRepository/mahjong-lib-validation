import json
import sys
from pathlib import Path
from profiling.tracing import Profile
from pstats import Stats
from typing import TYPE_CHECKING

import pytest
from validator import sampling_profile
from validator.cli import main

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager
    from subprocess import Popen

    from corpus.models import ScoringCase


@pytest.mark.parametrize("method", ["tracing", "sampling"])
def test_empty_selection_publishes_only_preflight_diagnostics(
    load_case: Callable[..., ScoringCase],
    save_dataset: Callable[[Path, list[ScoringCase]], Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
) -> None:
    dataset = save_dataset(tmp_path / "corpus", [load_case()])
    output = tmp_path / "result"

    def unexpected_collection(*_args: object, **_kwargs: object) -> None:
        pytest.fail("empty selection must not start collection")

    monkeypatch.setattr(
        "validator.profiling._collect_tracing", unexpected_collection
    )
    monkeypatch.setattr(
        "validator.profiling.collect_sampling", unexpected_collection
    )
    assert (
        main(
            [
                "profile",
                str(dataset),
                "--limit",
                "1",
                "--method",
                method,
                "--case-id",
                "missing",
                "--output",
                str(output),
            ]
        )
        == 1
    )
    assert {path.name for path in output.iterdir()} == {
        "summary.json",
        "cases.jsonl",
    }
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert (output / "cases.jsonl").read_bytes() == b""
    assert summary["method"] == method
    assert summary["exit_code"] == 1
    assert summary["complete"] is False
    assert summary["preflight"]["exit_code"] == 1
    assert summary["preflight"]["selected_count"] == 0
    assert summary["processed_count"] == 0


def test_tracing_collects_only_the_prepared_scoring_batch(
    load_case: Callable[..., ScoringCase],
    save_dataset: Callable[[Path, list[ScoringCase]], Path],
    tmp_path: Path,
) -> None:
    dataset = save_dataset(tmp_path / "corpus", [load_case(), load_case()])
    output = tmp_path / "result"
    assert (
        main(
            [
                "profile",
                str(dataset),
                "--limit",
                "1",
                "--method",
                "tracing",
                "--output",
                str(output),
            ]
        )
        == 0
    )

    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["complete"] is True
    assert summary["case_count"] == summary["processed_count"] == 1
    assert summary["repetitions"] == 1
    assert summary["preflight"]["scanned_count"] == 2
    assert summary["elapsed_ns"] >= 0

    stats = Stats(str(output / "profile.pstats"))
    functions = stats.get_stats_profile().func_profiles
    assert functions["estimate_hand_value"].ncalls == "1"
    assert not {
        "read_dataset",
        "prepare_hand",
        "prepare_scoring_case",
        "prepare_calculation",
        "validate_case",
        "dump_stats",
        "write_text",
    }.intersection(functions)


def test_unavailable_method_is_reported_without_publication(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "result"
    assert (
        main(
            [
                "profile",
                str(tmp_path / "missing"),
                "--limit",
                "1",
                "--method",
                "unknown",
                "--output",
                str(output),
            ]
        )
        == 2
    )
    diagnostic = capsys.readouterr().err
    assert "unknown" in diagnostic
    assert "--method tracing" in diagnostic
    assert not output.exists()


def test_sampling_attach_failure_does_not_publish(
    load_case: Callable[..., ScoringCase],
    save_dataset: Callable[[Path, list[ScoringCase]], Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    dataset = save_dataset(tmp_path / "corpus", [load_case()])
    output = tmp_path / "result"
    spawn = sampling_profile._process  # noqa: SLF001 -- simulate Tachyon denial

    def fail_attach(
        command: list[str], log: Path, *, send_start: bool = False
    ) -> AbstractContextManager[Popen[str]]:
        if "profiling.sampling" in command:
            command = [
                sys.executable,
                "-c",
                "raise SystemExit('attach denied')",
            ]
        return spawn(command, log, send_start=send_start)

    monkeypatch.setattr(sampling_profile, "_process", fail_attach)
    assert (
        main(
            [
                "profile",
                str(dataset),
                "--limit",
                "1",
                "--method",
                "sampling",
                "--output",
                str(output),
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    diagnostic = captured.err
    assert "attach denied" in diagnostic
    assert "--method tracing" in diagnostic
    assert not output.exists()


def test_failed_collection_write_does_not_publish(
    load_case: Callable[..., ScoringCase],
    save_dataset: Callable[[Path, list[ScoringCase]], Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    dataset = save_dataset(tmp_path / "corpus", [load_case()])
    output = tmp_path / "result"

    def broken_dump(_profiler: Profile, filename: str) -> None:
        Path(filename).write_bytes(b"partial")
        msg = "simulated dump failure"
        raise RuntimeError(msg)

    monkeypatch.setattr(Profile, "dump_stats", broken_dump)
    assert (
        main(
            [
                "profile",
                str(dataset),
                "--limit",
                "1",
                "--method",
                "tracing",
                "--output",
                str(output),
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "simulated dump failure" in captured.err
    assert not output.exists()

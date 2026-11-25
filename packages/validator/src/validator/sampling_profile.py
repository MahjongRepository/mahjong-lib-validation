import json
import re
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

    from corpus.models import ScoringCase

    from validator.models import SamplingResult


@contextmanager
def _process(
    command: list[str], log: Path, *, send_start: bool = False
) -> Generator[subprocess.Popen[str]]:
    with (
        log.open("w", encoding="utf-8") as stream,
        subprocess.Popen(  # noqa: S603 -- fixed Python modules, no shell
            command,
            stdin=subprocess.PIPE if send_start else subprocess.DEVNULL,
            stdout=stream,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
        ) as process,
    ):
        try:
            yield process
        finally:
            try:
                if process.stdin is not None:
                    process.stdin.close()
            finally:
                if process.poll() is None:
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()


def _wait_for_log(
    process: subprocess.Popen[str], log: Path, pattern: str, timeout: float
) -> re.Match[str]:
    deadline = monotonic() + timeout
    while process.poll() is None and monotonic() < deadline:
        if match := re.search(
            pattern,
            log.read_text(encoding="utf-8", errors="replace"),
            re.MULTILINE,
        ):
            return match
        sleep(0.02)
    diagnostic = log.read_text(encoding="utf-8", errors="replace").strip()
    msg = diagnostic or "timed out waiting for profiler or worker readiness"
    raise OSError(msg)


def _check_exit(
    process: subprocess.Popen[str], log: Path, timeout: float
) -> str:
    code = process.wait(timeout=timeout)
    diagnostic = log.read_text(encoding="utf-8", errors="replace").strip()
    if code:
        msg = f"process exited with code {code}: {diagnostic}"
        raise OSError(msg)
    return diagnostic


def _sample_count(log: str, output: Path) -> int:
    match = re.search(
        r"Flamegraph data: [1-9][0-9]* root functions?, "
        r"([1-9][0-9]*) total samples?,",
        log,
    )
    if (
        not match
        or "Interrupted by user." in log
        or "sample_batches" not in output.read_text(encoding="utf-8")
    ):
        msg = "Tachyon did not save samples from the calculation batch"
        raise OSError(msg)
    return int(match[1])


def _start_worker(worker: subprocess.Popen[str]) -> None:
    if worker.stdin is None:
        msg = "sampling worker has no control pipe"
        raise OSError(msg)
    worker.stdin.write("start\n")
    worker.stdin.flush()


def collect_sampling(
    selected: list[tuple[int, ScoringCase]],
    output: Path,
    *,
    min_seconds: float,
    rate_hz: int,
) -> SamplingResult:
    python = [sys.executable, "-X", "utf8", "-u", "-m"]
    try:
        with TemporaryDirectory(
            dir=output.parent, prefix=".sampling-"
        ) as temp:
            scratch = Path(temp)
            request = scratch / "request.json"
            request.write_text(
                json.dumps({"selected": selected, "min_seconds": min_seconds}),
                encoding="utf-8",
            )
            worker_log = scratch / "worker.log"
            profiler_log = scratch / "tachyon.log"
            with _process(
                [*python, "validator.sampling_worker", str(request)],
                worker_log,
                send_start=True,
            ) as worker:
                ready = _wait_for_log(
                    worker, worker_log, r"^ready ([0-9]+)$", 120
                )
                command = [
                    *python,
                    "profiling.sampling",
                    "attach",
                    ready[1],
                    "--realtime-stats",
                    "--flamegraph",
                    "--sampling-rate",
                    str(rate_hz),
                    "--output",
                    str(output),
                ]
                with _process(command, profiler_log) as profiler:
                    _wait_for_log(
                        profiler, profiler_log, r"\bN=[1-9][0-9]*", 30
                    )
                    _start_worker(worker)
                    worker_output = _check_exit(
                        worker, worker_log, min_seconds + 30
                    )
                    profiler_output = _check_exit(profiler, profiler_log, 30)

            result: SamplingResult = json.loads(worker_output.splitlines()[-1])
            result["sample_count"] = _sample_count(profiler_output, output)
            return result
    except (
        OSError,
        subprocess.SubprocessError,
        ValueError,
        OverflowError,
    ) as e:
        msg = f"sampling collection failed: {e}. Use --method tracing."
        raise OSError(msg) from e

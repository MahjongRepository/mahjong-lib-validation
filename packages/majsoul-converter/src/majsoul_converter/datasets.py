import json
import sqlite3
from contextlib import closing, contextmanager
from importlib.metadata import version
from os import scandir
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, TypedDict

from corpus import Case, Manifest, write_dataset

from majsoul_converter.conversion import TARGETS, convert_log
from majsoul_converter.decoder import ConversionError

if TYPE_CHECKING:
    from collections.abc import Generator, Iterator

    from corpus.manifests import ConversionSummary, GeneratorInfo

    from majsoul_converter.conversion import Target


class Diagnostic(TypedDict):
    path: str
    log_id: str
    reason: str
    message: str
    event_index: int | None
    field: str | None


class Report(TypedDict):
    generator: GeneratorInfo
    input: str
    output: str
    conversion: ConversionSummary
    record_count: int
    summary_complete: bool
    dataset_published: bool
    diagnostics: list[Diagnostic]
    omitted_diagnostic_count: int
    error: str | None


def _report_file(report_path: str | Path | None, output: Path) -> Path | None:
    if report_path is None:
        return None
    path = Path(report_path)
    if path.resolve().is_relative_to(output.resolve()):
        msg = "report must be outside output"
        raise ValueError(msg)
    if path.exists() or path.is_symlink():
        raise FileExistsError(path)
    return path


def _save_report(path: Path | None, report: Report) -> None:
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")


def _find_files(directory: Path) -> Iterator[Path]:
    with scandir(directory) as entries:
        for entry in entries:
            if entry.is_dir(follow_symlinks=False) and not entry.is_junction():
                yield from _find_files(Path(entry.path))
            elif entry.name.lower().endswith(".bin") and entry.is_file():
                yield Path(entry.path)


@contextmanager
def _input_paths(
    source: Path, output: Path, log_id: str | None
) -> Generator[Iterator[Path]]:
    if not source.is_dir():
        if source.suffix.lower() != ".bin":
            msg = f"replay input must have a .bin extension: {source}"
            raise ConversionError(msg)
        yield iter((source,))
        return

    if log_id is not None:
        msg = "log ID override requires a single replay file"
        raise ValueError(msg)
    if output.resolve().is_relative_to(source.resolve()):
        msg = "output must be outside the input directory"
        raise ValueError(msg)

    with (
        TemporaryDirectory(prefix="majsoul-inputs-") as temporary,
        closing(sqlite3.connect(Path(temporary) / "inputs.db")) as index,
    ):
        index.execute(
            "CREATE TABLE inputs (path TEXT PRIMARY KEY) WITHOUT ROWID"
        )
        inserted = index.executemany(
            "INSERT INTO inputs VALUES (?)",
            (
                (path.relative_to(source).as_posix(),)
                for path in _find_files(source)
            ),
        )
        if inserted.rowcount == 0:
            msg = f"no .bin replays in {source}"
            raise ConversionError(msg)
        rows = index.execute("SELECT path FROM inputs ORDER BY path")
        yield (source / relative_path for (relative_path,) in rows)


def convert_files(  # noqa: PLR0913 -- explicit dataset options
    input_path: str | Path,
    output_directory: str | Path,
    *,
    log_id: str | None = None,
    cases_per_file: int = 100_000,
    compress: bool = True,
    report_path: str | Path | None = None,
    target: Target = "scoring",
) -> Manifest:
    """Publish a corpus from one replay or a directory of replays."""
    if target not in TARGETS:
        msg = f"unknown conversion target {target!r}"
        raise ConversionError(msg)
    source, output = Path(input_path), Path(output_directory)
    report_file = _report_file(report_path, output)
    summary: ConversionSummary = {
        "input_count": 0,
        "converted_count": 0,
        "failed_by_reason": {},
        "excluded_by_reason": {},
    }

    generator: GeneratorInfo = {
        "name": "majsoul-converter",
        "version": version("majsoul-converter"),
        "settings": {
            "target": target,
            "ruleset": "majsoul-ranked-match",
            "log_id_override": log_id,
            "cases_per_file": cases_per_file,
            "compress": compress,
        },
    }
    report: Report = {
        "generator": generator,
        "input": str(source),
        "output": str(output),
        "conversion": summary,
        "record_count": 0,
        "summary_complete": False,
        "dataset_published": False,
        "diagnostics": [],
        "omitted_diagnostic_count": 0,
        "error": None,
    }

    def cases(paths: Iterator[Path]) -> Generator[Case]:
        for path in paths:
            summary["input_count"] += 1
            try:
                records = convert_log(
                    path.read_bytes(),
                    log_id=log_id,
                    fallback_id=path.stem,
                    target=target,
                )
            except (ConversionError, OSError) as e:
                conversion_error = isinstance(e, ConversionError)
                reason = (
                    "conversion_error"
                    if conversion_error
                    else "input_io_error"
                )
                event_index = e.event_index if conversion_error else None
                summary["failed_by_reason"][reason] = 1
                report["diagnostics"].append(
                    {
                        "path": str(path),
                        "log_id": log_id if log_id is not None else path.stem,
                        "reason": reason,
                        "message": str(e),
                        "event_index": event_index,
                        "field": None,
                    }
                )
                if conversion_error:
                    msg = f"{path}: {e}"
                    raise ConversionError(msg, event_index=event_index) from e
                raise
            summary["converted_count"] += 1
            report["record_count"] += len(records)
            yield from records
        report["summary_complete"] = True

    try:
        with (
            _input_paths(source, output, log_id) as paths,
            closing(cases(paths)) as records,
        ):
            output.parent.mkdir(parents=True, exist_ok=True)
            manifest = write_dataset(
                output,
                records,
                generator=generator,
                conversion=summary,
                cases_per_file=cases_per_file,
                compress=compress,
            )
    except (ValueError, OSError, sqlite3.Error) as e:
        report["error"] = str(e)
        _save_report(report_file, report)
        raise

    report["dataset_published"] = True
    _save_report(report_file, report)
    return manifest

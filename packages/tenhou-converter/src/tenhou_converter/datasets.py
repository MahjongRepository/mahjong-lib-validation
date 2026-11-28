import sqlite3
import zlib
from contextlib import closing
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING
lazy from collections.abc import Generator

from corpus import Case, CorpusError, Manifest, write_dataset
from corpus.conversion_reports import (
    new_report,
    record_diagnostic,
    write_report,
)

from tenhou_converter.conversion import TARGETS, Target, convert_log
from tenhou_converter.errors import ConversionError, UnsupportedLogError
from tenhou_converter.sources import discover, read_xml

if TYPE_CHECKING:
    from corpus.conversion_reports import Report
    from corpus.manifests import GeneratorInfo


class BatchConversionError(ValueError):
    def __init__(self, message: str, report: Report) -> None:
        self.report = report
        super().__init__(message)


def _check_paths(source: Path, output: Path, report_file: Path | None) -> None:
    source_resolved, output_resolved = source.resolve(), output.resolve()
    if output_resolved == source_resolved or (
        source.is_dir() and source_resolved in output_resolved.parents
    ):
        msg = "output must be outside input"
        raise ValueError(msg)
    if report_file is not None:
        resolved = report_file.resolve()
        if resolved == output_resolved or output_resolved in resolved.parents:
            msg = "report must be outside output"
            raise ValueError(msg)
        if report_file.exists() or report_file.is_symlink():
            raise FileExistsError(report_file)


def _record_input_failure(
    report: Report,
    path: Path,
    log_id: str,
    error: ConversionError | OSError | EOFError | zlib.error,
) -> None:
    reason = "input_io_error"
    event_index = None
    field = None
    if isinstance(error, ConversionError):
        reason = error.reason
        event_index = error.event_index
        field = error.field

    record_diagnostic(
        report,
        {
            "path": str(path),
            "log_id": log_id,
            "reason": reason,
            "message": str(error),
            "event_index": event_index,
            "field": field,
        },
        excluded=isinstance(error, UnsupportedLogError),
    )


def _save_report(path: Path | None, report: Report) -> None:
    if path is not None:
        try:
            write_report(path, report)
        except OSError as e:
            message = f"{report['error'] or ''}; report_io_error: {e}"
            report["error"] = message
            raise BatchConversionError(message, report) from e


def convert_files(  # noqa: PLR0913 -- explicit output controls
    input_path: str | Path,
    output_directory: str | Path,
    *,
    log_id: str | None = None,
    cases_per_file: int = 100_000,
    compress: bool = True,
    report_path: str | Path | None = None,
    target: Target = "scoring",
) -> Manifest:
    """Publish a new dataset, with diagnostic reports on failure."""
    source, output = Path(input_path), Path(output_directory)
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    if cases_per_file <= 0:
        msg = "cases_per_file must be positive"
        raise ValueError(msg)
    if target not in TARGETS:
        msg = f"unknown conversion target {target!r}"
        raise ValueError(msg)

    report_file = Path(report_path) if report_path is not None else None
    _check_paths(source, output, report_file)
    generator: GeneratorInfo = {
        "name": "tenhou-converter",
        "version": version("tenhou-converter"),
        "settings": {
            "source": "mjlog",
            "target": target,
            "ruleset": "tenhou-ranked-match",
            "player_counts": [3, 4],
            "log_id": "override"
            if log_id is not None
            else "filename_without_suffix",
            "log_id_override": log_id,
            "input_order": "relative_posix_path",
            "cases_per_file": cases_per_file,
            "compress": compress,
            "reconstruction_version": "1",
        },
    }
    report = new_report(source, output, generator=generator)
    summary = report["conversion"]

    def cases() -> Generator[Case]:
        with closing(discover(source, log_id)) as inputs:
            for path, identifier in inputs:
                summary["input_count"] += 1
                try:
                    converted = convert_log(
                        read_xml(path), log_id=identifier, target=target
                    )
                except (ConversionError, OSError, EOFError, zlib.error) as e:
                    _record_input_failure(report, path, identifier, e)
                else:
                    summary["converted_count"] += 1
                    report["record_count"] += len(converted)
                    yield from converted
        report["summary_complete"] = True

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        with closing(cases()) as records:
            manifest = write_dataset(
                output,
                records,
                generator=generator,
                conversion=summary,
                cases_per_file=cases_per_file,
                compress=compress,
            )
    except (OSError, CorpusError, sqlite3.Error) as e:
        report["error"] = str(e)
        _save_report(report_file, report)
        raise BatchConversionError(str(e), report) from e

    report["dataset_published"] = True
    _save_report(report_file, report)
    return manifest

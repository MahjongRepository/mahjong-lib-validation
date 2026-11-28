import sqlite3
from contextlib import closing
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING

from corpus import Case, CorpusError, Manifest, write_dataset
from corpus.conversion_reports import (
    new_report,
    record_diagnostic,
    write_report,
)

from majsoul_converter.conversion import TARGETS, convert_log
from majsoul_converter.decoder import ConversionError
from majsoul_converter.sources import input_paths

if TYPE_CHECKING:
    from collections.abc import Generator, Iterator

    from corpus.conversion_reports import Report
    from corpus.manifests import GeneratorInfo

    from majsoul_converter.conversion import Target


class BatchConversionError(ConversionError):
    def __init__(self, message: str, report: Report) -> None:
        self.report = report
        super().__init__(message)


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
        try:
            write_report(path, report)
        except OSError as e:
            message = f"{report['error'] or ''}; report_io_error: {e}"
            report["error"] = message
            raise BatchConversionError(message, report) from e


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
    source, output = Path(input_path), Path(output_directory)
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    if cases_per_file <= 0:
        msg = "cases_per_file must be positive"
        raise ValueError(msg)
    if target not in TARGETS:
        msg = f"unknown conversion target {target!r}"
        raise ValueError(msg)

    report_file = _report_file(report_path, output)
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
    report = new_report(source, output, generator=generator)
    summary = report["conversion"]

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
                record_diagnostic(
                    report,
                    {
                        "path": str(path),
                        "log_id": log_id if log_id is not None else path.stem,
                        "reason": reason,
                        "message": str(e),
                        "event_index": event_index,
                        "field": None,
                    },
                    excluded=False,
                )
                continue
            summary["converted_count"] += 1
            report["record_count"] += len(records)
            yield from records
        report["summary_complete"] = True

    try:
        with (
            input_paths(source, output, log_id) as paths,
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
            report["dataset_published"] = True
    except (ConversionError, CorpusError, OSError, sqlite3.Error) as e:
        report["error"] = str(e)
        _save_report(report_file, report)
        raise BatchConversionError(str(e), report) from e

    _save_report(report_file, report)
    return manifest

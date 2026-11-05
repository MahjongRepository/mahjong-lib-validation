import json
import zlib
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict
lazy from collections.abc import Iterator

from corpus import CorpusError, Manifest, ScoringCase, write_dataset

from tenhou_converter.conversion import convert_log
from tenhou_converter.errors import ConversionError, UnsupportedLogError
from tenhou_converter.sources import discover, read_xml

if TYPE_CHECKING:
    from corpus.models import ConversionSummary, GeneratorInfo


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
    error: str | None


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

    summary = report["conversion"]
    if isinstance(error, UnsupportedLogError):
        counts = summary["excluded_by_reason"]
    else:
        counts = summary["failed_by_reason"]
    counts[reason] = counts.get(reason, 0) + 1

    report["diagnostics"].append(
        {
            "path": str(path),
            "log_id": log_id,
            "reason": reason,
            "message": str(error),
            "event_index": event_index,
            "field": field,
        }
    )


def convert_files(  # noqa: PLR0913 -- explicit output controls
    input_path: str | Path,
    output_directory: str | Path,
    *,
    log_id: str | None = None,
    cases_per_file: int = 100_000,
    compress: bool = True,
    report_path: str | Path | None = None,
) -> Manifest:
    """Publish a new dataset, with diagnostic reports on failure."""
    source, output = Path(input_path), Path(output_directory)
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    if (
        type(cases_per_file) is not int
        or cases_per_file <= 0
        or type(compress) is not bool
    ):
        msg = "invalid shard size or compression option"
        raise ValueError(msg)
    report_file = Path(report_path) if report_path is not None else None
    _check_paths(source, output, report_file)
    inputs = discover(source, log_id)
    summary: ConversionSummary = {
        "input_count": 0,
        "converted_count": 0,
        "failed_by_reason": {},
        "excluded_by_reason": {},
    }
    generator: GeneratorInfo = {
        "name": "tenhou-converter",
        "version": version("tenhou-converter"),
        "settings": {
            "source": "mjlog",
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
    report: Report = {
        "generator": generator,
        "input": str(source),
        "output": str(output),
        "conversion": summary,
        "record_count": 0,
        "summary_complete": False,
        "dataset_published": False,
        "diagnostics": [],
        "error": None,
    }

    def cases() -> Iterator[ScoringCase]:
        for path, identifier in inputs:
            summary["input_count"] += 1
            try:
                converted = convert_log(read_xml(path), log_id=identifier)
            except (ConversionError, OSError, EOFError, zlib.error) as e:
                _record_input_failure(report, path, identifier, e)
            else:
                summary["converted_count"] += 1
                report["record_count"] += len(converted)
                yield from converted
        report["summary_complete"] = True

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        manifest = write_dataset(
            output,
            cases(),
            generator=generator,
            conversion=summary,
            cases_per_file=cases_per_file,
            compress=compress,
        )
    except (OSError, CorpusError) as e:
        report["error"] = str(e)
        save_report(report_file, report)
        raise BatchConversionError(str(e), report) from e

    report["dataset_published"] = True
    save_report(report_file, report)
    return manifest


def save_report(path: Path | None, report: Report) -> None:
    if path is not None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x", encoding="utf-8") as stream:
                json.dump(report, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
        except OSError as e:
            message = f"{report['error'] or ''}; report_io_error: {e}"
            report["error"] = message
            raise BatchConversionError(message, report) from e

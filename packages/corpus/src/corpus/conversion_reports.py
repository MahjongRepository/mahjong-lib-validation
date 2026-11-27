"""Shared conversion counters, diagnostics, and report output."""

import json
from pathlib import Path
from typing import TypedDict

lazy from corpus.models import ConversionSummary, GeneratorInfo

MAX_DIAGNOSTICS = 100


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


def new_report(
    source: str | Path, output: str | Path, *, generator: GeneratorInfo
) -> Report:
    """Start a report with a mutable summary for write_dataset."""
    return {
        "generator": generator,
        "input": str(source),
        "output": str(output),
        "conversion": {
            "input_count": 0,
            "converted_count": 0,
            "failed_by_reason": {},
            "excluded_by_reason": {},
        },
        "record_count": 0,
        "summary_complete": False,
        "dataset_published": False,
        "diagnostics": [],
        "omitted_diagnostic_count": 0,
        "error": None,
    }


def record_diagnostic(
    report: Report, diagnostic: Diagnostic, *, excluded: bool
) -> None:
    """Count a classified input and retain up to 100 diagnostics."""
    summary = report["conversion"]
    counts = (
        summary["excluded_by_reason"]
        if excluded
        else summary["failed_by_reason"]
    )
    reason = diagnostic["reason"]
    counts[reason] = counts.get(reason, 0) + 1

    if len(report["diagnostics"]) < MAX_DIAGNOSTICS:
        report["diagnostics"].append(diagnostic)
    else:
        report["omitted_diagnostic_count"] += 1


def write_report(path: str | Path, report: Report) -> None:
    """Write a new UTF-8 JSON report with exclusive creation."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")

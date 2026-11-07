"""Manifest models and storage for scoring datasets."""

import json
from pathlib import Path
from re import fullmatch
from typing import cast

from corpus._fileio import atomic_path, decode_json
from corpus._validation import minimum, validate_json, validate_type
from corpus.errors import CorpusError
from corpus.models import ConversionSummary, DataFile, Manifest


def parse_manifest(value: object) -> Manifest:
    validate_type(value, Manifest, "")
    manifest = cast("Manifest", value)
    _files(manifest["files"])
    minimum(manifest["record_count"], 0, "record_count")
    total = sum(entry["record_count"] for entry in manifest["files"])
    if manifest["record_count"] != total:
        error_field = "record_count"
        raise CorpusError(error_field, "does not equal the file record counts")
    _conversion(manifest["conversion"])
    if manifest["record_count"] > 0:
        minimum(
            manifest["conversion"]["converted_count"],
            1,
            "conversion.converted_count",
        )
    for name in ("name", "version"):
        if not manifest["generator"][name].strip():
            raise CorpusError("generator." + name, "must not be empty")
    validate_json(manifest["generator"]["settings"], "generator.settings")
    return manifest


def read_manifest(path: str | Path) -> Manifest:
    path = Path(path)
    value = decode_json(path.read_bytes(), path)
    try:
        return parse_manifest(value)
    except CorpusError as e:
        raise CorpusError(e.field, e.message, path=path) from e


def write_manifest(path: str | Path, manifest: Manifest) -> None:
    manifest = parse_manifest(manifest)
    path = Path(path)
    with atomic_path(path) as staging:
        staging.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False)
            + "\n",
            encoding="utf-8",
        )


def _files(files: list[DataFile]) -> None:
    seen = set()
    for index, entry in enumerate(files):
        field = f"files[{index}]"
        name = entry["path"]
        if (
            any(character in name for character in ("/", "\\", ":", "\x00"))
            or not name.endswith((".jsonl", ".jsonl.gz"))
            or name.casefold() in seen
        ):
            raise CorpusError(
                field + ".path",
                "expected a unique data file name without directories",
            )
        seen.add(name.casefold())
        minimum(entry["record_count"], 1, field + ".record_count")
        if not fullmatch(r"[a-f0-9]{64}", entry["sha256"]):
            raise CorpusError(
                field + ".sha256", "expected a lowercase SHA-256 digest"
            )


def _conversion(summary: ConversionSummary) -> None:
    minimum(summary["input_count"], 0, "conversion.input_count")
    minimum(summary["converted_count"], 0, "conversion.converted_count")
    total = summary["converted_count"]
    for name in ("failed_by_reason", "excluded_by_reason"):
        for reason, count in summary[name].items():
            field = f"conversion.{name}.{reason}"
            if not reason.strip():
                raise CorpusError(field, "reason must not be empty")
            minimum(count, 1, field)
            total += count
    if summary["input_count"] != total:
        error_field = "conversion.input_count"
        raise CorpusError(
            error_field,
            "does not equal converted + failed + excluded",
        )

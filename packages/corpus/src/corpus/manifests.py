"""Manifest models and storage for scoring datasets."""

import json
from pathlib import Path
from re import fullmatch
from typing import cast

from corpus._fileio import atomic_path, decode_json
from corpus._validation import minimum, validate_json, validate_type
from corpus.errors import CorpusError
from corpus.models import ConversionSummary, Manifest

MAX_MANIFEST_BYTES = 1024 * 1024


def parse_manifest(value: object) -> Manifest:
    validate_type(value, Manifest, "")
    manifest = cast("Manifest", value)
    minimum(manifest["record_count"], 0, "record_count")
    validate_digest(manifest["files_sha256"], "files_sha256")
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
    # Preserve the universal newlines of whole-file text reads.
    with path.open("rb") as stream:
        content = stream.read(MAX_MANIFEST_BYTES + 1)
    _check_size(content, path)
    value = decode_json(
        content.replace(b"\r\n", b"\n").replace(b"\r", b"\n"), path
    )
    try:
        return parse_manifest(value)
    except CorpusError as e:
        raise CorpusError(e.field, e.message, path=path) from e


def write_manifest(path: str | Path, manifest: Manifest) -> None:
    manifest = parse_manifest(manifest)
    path = Path(path)
    content = (
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    _check_size(content, path)
    with atomic_path(path) as staging:
        staging.write_bytes(content)


def _check_size(content: bytes, path: Path) -> None:
    if len(content) > MAX_MANIFEST_BYTES:
        field = "$"
        raise CorpusError(field, "manifest exceeds 1 MiB", path=path)


def validate_digest(value: str, field: str) -> None:
    if not fullmatch(r"[a-f0-9]{64}", value):
        raise CorpusError(field, "expected a lowercase SHA-256 digest")


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

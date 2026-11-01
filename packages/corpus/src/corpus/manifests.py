"""Manifest models and storage for scoring datasets."""

import json
from pathlib import Path
from re import fullmatch
from tempfile import NamedTemporaryFile
from typing import cast

from corpus.checks import _fail, _json_value, _minimum, _shape
from corpus.errors import CorpusError
from corpus.models import ConversionSummary, DataFile, Manifest


def parse_manifest(value: object) -> Manifest:
    _shape(value, Manifest, "")
    manifest = cast("Manifest", value)
    _files(manifest["files"])
    _minimum(manifest["record_count"], 0, "record_count")
    total = sum(entry["record_count"] for entry in manifest["files"])
    if manifest["record_count"] != total:
        _fail("record_count", "does not equal the file record counts")
    _conversion(manifest["conversion"])
    if manifest["record_count"] > 0:
        _minimum(
            manifest["conversion"]["converted_count"],
            1,
            "conversion.converted_count",
        )
    for name in ("name", "version"):
        if not manifest["generator"][name].strip():
            _fail("generator." + name, "must not be empty")
    _json_value(manifest["generator"]["settings"], "generator.settings")
    return manifest


def read_manifest(path: str | Path) -> Manifest:
    path = Path(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        field = "$"
        raise CorpusError(
            field, error.msg, path=path, line=error.lineno
        ) from error
    except UnicodeDecodeError as error:
        field = "$"
        raise CorpusError(field, "invalid UTF-8", path=path) from error
    try:
        return parse_manifest(value)
    except CorpusError as error:
        raise CorpusError(error.field, error.message, path=path) from error


def write_manifest(path: str | Path, manifest: Manifest) -> None:
    manifest = parse_manifest(manifest)
    path = Path(path)
    with NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        staging = Path(temporary.name)
    try:
        staging.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False)
            + "\n",
            encoding="utf-8",
        )
        staging.replace(path)
    finally:
        staging.unlink(missing_ok=True)


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
            _fail(
                field + ".path",
                "expected a unique data file name without directories",
            )
        seen.add(name.casefold())
        _minimum(entry["record_count"], 1, field + ".record_count")
        if not fullmatch(r"[a-f0-9]{64}", entry["sha256"]):
            _fail(field + ".sha256", "expected a lowercase SHA-256 digest")


def _conversion(summary: ConversionSummary) -> None:
    _minimum(summary["input_count"], 0, "conversion.input_count")
    _minimum(summary["converted_count"], 0, "conversion.converted_count")
    total = summary["converted_count"]
    for name in ("failed_by_reason", "excluded_by_reason"):
        for reason, count in summary[name].items():
            field = f"conversion.{name}.{reason}"
            if not reason.strip():
                _fail(field, "reason must not be empty")
            _minimum(count, 1, field)
            total += count
    if summary["input_count"] != total:
        _fail(
            "conversion.input_count",
            "does not equal converted + failed + excluded",
        )

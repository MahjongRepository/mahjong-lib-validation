"""Read and publish datasets described by a manifest."""

import hashlib
import json
from contextlib import closing, contextmanager
from itertools import chain, islice
from os import scandir
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, cast

from corpus._fileio import decode_json
from corpus._validation import minimum, validate_type
from corpus.case_io import read_cases, write_cases
from corpus.errors import CorpusError
from corpus.manifests import (
    parse_manifest,
    read_manifest,
    validate_digest,
    write_manifest,
)
from corpus.models import (
    ConversionSummary,
    DataFile,
    GeneratorInfo,
    Manifest,
    ScoringCase,
)

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable, Iterator


MAX_INDEX_ROW_BYTES = 4096


def read_dataset(directory: str | Path) -> Generator[ScoringCase]:
    directory = Path(directory)
    manifest = read_manifest(directory / "manifest.json")
    yield from _read_dataset(directory, manifest)


def check_dataset(directory: str | Path) -> Manifest:
    directory = Path(directory)
    manifest = read_manifest(directory / "manifest.json")
    for _ in _read_dataset(directory, manifest):
        pass
    return manifest


def write_dataset(  # noqa: PLR0913 -- explicit metadata and output options
    directory: str | Path,
    cases: Iterable[ScoringCase],
    *,
    generator: GeneratorInfo,
    conversion: ConversionSummary,
    cases_per_file: int = 100_000,
    compress: bool = True,
) -> Manifest:
    directory = Path(directory)
    _new_directory(directory)
    validate_type(conversion, ConversionSummary, "conversion")
    _complete(conversion, directory / "manifest.json")
    if cases_per_file <= 0:
        error_field = "cases_per_file"
        raise CorpusError(error_field, "must be positive")
    with _staging_directory(directory.parent) as staging:
        record_count = _write_files(
            staging, iter(cases), cases_per_file, compress=compress
        )
        manifest = parse_manifest(
            {
                "schema_version": "v1",
                "case_type": "scoring",
                "generator": generator,
                "conversion": conversion,
                "files_sha256": file_sha256(staging / "files.jsonl"),
                "record_count": record_count,
            }
        )
        _ready(manifest, directory / "manifest.json")
        write_manifest(staging / "manifest.json", manifest)
        _new_directory(directory)
        staging.rename(directory)
    return manifest


@contextmanager
def _staging_directory(parent: Path) -> Generator[Path]:
    with TemporaryDirectory(dir=parent, prefix=".corpus-") as temporary:
        staging = Path(temporary) / "dataset"
        staging.mkdir()
        try:
            yield staging
        finally:
            if staging.exists():
                # Clean up failed shards one at a time.
                with scandir(staging) as entries:
                    for entry in entries:
                        Path(entry.path).unlink()
                staging.rmdir()


def _new_directory(directory: Path) -> None:
    if directory.exists() or directory.is_symlink():
        raise FileExistsError(directory)


def _write_files(
    directory: Path,
    cases: Iterator[ScoringCase],
    limit: int,
    *,
    compress: bool,
) -> int:
    total = 0
    suffix = ".jsonl.gz" if compress else ".jsonl"
    with (directory / "files.jsonl").open("wb") as index:
        for position, first in enumerate(cases, start=1):
            name = f"scoring-{position:06d}{suffix}"
            path = directory / name
            count = write_cases(
                path, chain((first,), islice(cases, limit - 1))
            )
            entry = {
                "path": name,
                "record_count": count,
                "sha256": file_sha256(path),
            }
            index.write((json.dumps(entry) + "\n").encode("utf-8"))
            total += count
    return total


def _read_dataset(
    directory: Path, manifest: Manifest
) -> Generator[ScoringCase]:
    _ready(manifest, directory / "manifest.json")
    path = directory / "files.jsonl"
    index_field = "files_sha256"
    if path.resolve().parent != directory.resolve() or not path.is_file():
        raise CorpusError(
            index_field, "missing or unsafe file index", path=path
        )
    if file_sha256(path) != manifest["files_sha256"]:
        raise CorpusError(index_field, "file index hash mismatch", path=path)

    total = 0
    with path.open("rb") as stream:
        lines = iter(lambda: stream.readline(MAX_INDEX_ROW_BYTES + 1), b"")
        for index, line in enumerate(lines):
            field = f"files[{index}]"
            if len(line) > MAX_INDEX_ROW_BYTES:
                raise CorpusError(
                    field, "file index row exceeds 4 KiB", path=path
                )
            value = decode_json(line, path, line=index + 1)
            validate_type(value, DataFile, field)
            entry = cast("DataFile", value)
            stem = f"scoring-{index + 1:06d}"
            if entry["path"] not in (stem + ".jsonl", stem + ".jsonl.gz"):
                raise CorpusError(
                    field + ".path",
                    "expected sequential data file name",
                    path=path,
                )
            minimum(entry["record_count"], 1, field + ".record_count")
            validate_digest(entry["sha256"], field + ".sha256")
            yield from _read_file(directory, entry, index)
            total += entry["record_count"]
    if total != manifest["record_count"]:
        field = "record_count"
        raise CorpusError(
            field, "does not equal the file record counts", path=path
        )


def _read_file(
    directory: Path, entry: DataFile, index: int
) -> Generator[ScoringCase]:
    field = f"files[{index}]"
    path = directory / entry["path"]
    if path.resolve().parent != directory.resolve():
        raise CorpusError(
            field + ".path",
            "data file leaves dataset directory",
            path=path,
        )
    if not path.is_file():
        raise CorpusError(field + ".path", "data file is missing", path=path)
    if file_sha256(path) != entry["sha256"]:
        raise CorpusError(field + ".sha256", "hash mismatch", path=path)

    count = 0
    with closing(read_cases(path)) as cases:
        for case in cases:
            count += 1
            yield case

    if count != entry["record_count"]:
        raise CorpusError(
            field + ".record_count", "record count mismatch", path=path
        )


def _complete(summary: ConversionSummary, path: Path) -> None:
    if summary["failed_by_reason"]:
        field = "conversion.failed_by_reason"
        raise CorpusError(
            field, "dataset contains failed conversions", path=path
        )


def _ready(manifest: Manifest, path: Path) -> None:
    _complete(manifest["conversion"], path)
    if manifest["record_count"] == 0:
        field = "files"
        raise CorpusError(field, "dataset contains no cases", path=path)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

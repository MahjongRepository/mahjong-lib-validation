"""Read and publish datasets described by a manifest."""

import hashlib
from collections.abc import Generator, Iterable, Iterator
from contextlib import closing
from itertools import chain, islice
from pathlib import Path
from tempfile import TemporaryDirectory

from corpus._validation import fail, validate_type
from corpus.errors import CorpusError
from corpus.manifests import (
    parse_manifest,
    read_manifest,
    write_manifest,
)
from corpus.models import (
    ConversionSummary,
    DataFile,
    GeneratorInfo,
    Manifest,
    ScoringCase,
)
from corpus.readers import read_cases
from corpus.writers import _write_cases


def read_dataset(directory: str | Path) -> Generator[ScoringCase, None, None]:
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
    if type(cases_per_file) is not int or cases_per_file <= 0:
        fail("cases_per_file", "expected a positive integer")
    with TemporaryDirectory(
        dir=directory.parent, prefix=".corpus-"
    ) as temporary:
        staging = Path(temporary) / "dataset"
        staging.mkdir()
        files = _write_files(
            staging, iter(cases), cases_per_file, compress=compress
        )
        manifest = parse_manifest(
            {
                "schema_version": "v1",
                "case_type": "scoring",
                "generator": generator,
                "conversion": conversion,
                "files": files,
                "record_count": sum(entry["record_count"] for entry in files),
            }
        )
        _ready(manifest, directory / "manifest.json")
        write_manifest(staging / "manifest.json", manifest)
        _new_directory(directory)
        staging.rename(directory)
    return manifest


def _new_directory(directory: Path) -> None:
    if directory.exists() or directory.is_symlink():
        raise FileExistsError(directory)


def _write_files(
    directory: Path,
    cases: Iterator[ScoringCase],
    limit: int,
    *,
    compress: bool,
) -> list[DataFile]:
    files: list[DataFile] = []
    while True:
        try:
            first = next(cases)
        except StopIteration:
            break
        suffix = ".jsonl.gz" if compress else ".jsonl"
        name = f"scoring-{len(files) + 1:06d}{suffix}"
        path = directory / name
        count = _write_cases(path, chain((first,), islice(cases, limit - 1)))
        files.append(
            {"path": name, "record_count": count, "sha256": _sha256(path)}
        )
    return files


def _read_dataset(
    directory: Path, manifest: Manifest
) -> Generator[ScoringCase, None, None]:
    _ready(manifest, directory / "manifest.json")
    for index, entry in enumerate(manifest["files"]):
        yield from _read_file(directory, entry, index)


def _read_file(
    directory: Path, entry: DataFile, index: int
) -> Generator[ScoringCase, None, None]:
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
    if _sha256(path) != entry["sha256"]:
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

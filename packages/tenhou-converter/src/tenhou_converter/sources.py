import gzip
import os
import sqlite3
import stat
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
lazy from collections.abc import Generator, Iterator

SUFFIXES = (".xml.gz", ".mjlog.gz", ".xml", ".mjlog")


def is_link(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def log_id_from_path(path: Path) -> str:
    for suffix in SUFFIXES:
        if path.name.lower().endswith(suffix):
            value = path.name[: -len(suffix)]
            if not value.strip():
                msg = f"empty log ID before extension: {path}"
                raise ValueError(msg)
            return value
    msg = f"unsupported extension: {path}"
    raise ValueError(msg)


def _find_files(directory: Path) -> Iterator[Path]:
    with os.scandir(directory) as entries:
        for entry in entries:
            candidate = Path(entry.path)
            if is_link(candidate):
                continue
            if entry.is_dir(follow_symlinks=False):
                yield from _find_files(candidate)
            elif entry.is_file(
                follow_symlinks=False
            ) and candidate.name.lower().endswith(SUFFIXES):
                yield candidate


def discover(path: Path, log_id: str | None) -> Generator[tuple[Path, str]]:
    if is_link(path):
        msg = "input must not be a link or junction"
        raise ValueError(msg)
    if path.is_file():
        derived = log_id_from_path(path)
        if log_id is not None and not log_id.strip():
            msg = "log_id must not be empty"
            raise ValueError(msg)
        yield path, log_id if log_id is not None else derived
        return

    if not path.is_dir():
        msg = "input must be a file or directory"
        raise ValueError(msg)
    if log_id is not None:
        msg = "log_id requires a single file"
        raise ValueError(msg)
    with (
        TemporaryDirectory(prefix="tenhou-inputs-") as temporary,
        closing(sqlite3.connect(Path(temporary) / "inputs.db")) as index,
    ):
        index.execute(
            "CREATE TABLE inputs (path TEXT PRIMARY KEY, log_id TEXT UNIQUE) "
            "WITHOUT ROWID"
        )
        try:
            index.executemany(
                "INSERT INTO inputs VALUES (?, ?)",
                (
                    (
                        candidate.relative_to(path).as_posix(),
                        log_id_from_path(candidate),
                    )
                    for candidate in _find_files(path)
                ),
            )
        except sqlite3.IntegrityError as error:
            msg = "duplicate_log_id: input contains repeated log IDs"
            raise ValueError(msg) from error

        rows = index.execute("SELECT path, log_id FROM inputs ORDER BY path")
        if (first := rows.fetchone()) is None:
            msg = "input contains no mjlog files"
            raise ValueError(msg)
        yield path / first[0], first[1]
        for relative_path, identifier in rows:
            yield path / relative_path, identifier


def read_xml(path: Path) -> bytes:
    data = path.read_bytes()
    if data.startswith(b"\x1f\x8b"):
        return gzip.decompress(data)
    if path.name.lower().endswith(".gz"):
        msg = ".gz input does not contain gzip data"
        raise gzip.BadGzipFile(msg)
    return data

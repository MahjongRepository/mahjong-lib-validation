import gzip
import os
import stat
from pathlib import Path
lazy from collections.abc import Iterator

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
            if value.strip():
                return value
    msg = f"unsupported extension or empty log ID: {path}"
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


def discover(path: Path, log_id: str | None) -> list[tuple[Path, str]]:
    if is_link(path):
        msg = "input must not be a link or junction"
        raise ValueError(msg)
    if path.is_file():
        derived = log_id_from_path(path)
        if log_id is not None and not log_id.strip():
            msg = "log_id must not be empty"
            raise ValueError(msg)
        return [(path, log_id if log_id is not None else derived)]

    if not path.is_dir():
        msg = "input must be a file or directory"
        raise ValueError(msg)
    if log_id is not None:
        msg = "log_id requires a single file"
        raise ValueError(msg)
    files = list(_find_files(path))
    files.sort(key=lambda candidate: candidate.relative_to(path).as_posix())
    inputs = [(candidate, log_id_from_path(candidate)) for candidate in files]
    ids = [identifier for _, identifier in inputs]
    if len(set(ids)) != len(ids):
        msg = "duplicate_log_id: input contains repeated log IDs"
        raise ValueError(msg)
    if not inputs:
        msg = "input contains no mjlog files"
        raise ValueError(msg)
    return inputs


def read_xml(path: Path) -> bytes:
    data = path.read_bytes()
    if data.startswith(b"\x1f\x8b"):
        return gzip.decompress(data)
    if path.name.lower().endswith(".gz"):
        msg = ".gz input does not contain gzip data"
        raise gzip.BadGzipFile(msg)
    return data

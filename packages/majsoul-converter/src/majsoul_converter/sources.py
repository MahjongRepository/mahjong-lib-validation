"""Discover replay inputs in relative POSIX path order."""

import sqlite3
from contextlib import closing, contextmanager
from os import scandir
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from majsoul_converter.decoder import ConversionError

if TYPE_CHECKING:
    from collections.abc import Generator, Iterator


def _find_files(directory: Path) -> Iterator[Path]:
    with scandir(directory) as entries:
        for entry in entries:
            if entry.is_dir(follow_symlinks=False) and not entry.is_junction():
                yield from _find_files(Path(entry.path))
            elif entry.name.lower().endswith(".bin") and entry.is_file():
                yield Path(entry.path)


@contextmanager
def input_paths(
    source: Path, output: Path, log_id: str | None
) -> Generator[Iterator[Path]]:
    if not source.is_dir():
        if source.suffix.lower() != ".bin":
            msg = f"replay input must have a .bin extension: {source}"
            raise ConversionError(msg)
        yield iter((source,))
        return

    if log_id is not None:
        msg = "log ID override requires a single replay file"
        raise ValueError(msg)
    if output.resolve().is_relative_to(source.resolve()):
        msg = "output must be outside the input directory"
        raise ValueError(msg)

    with (
        TemporaryDirectory(prefix="majsoul-inputs-") as temporary,
        closing(sqlite3.connect(Path(temporary) / "inputs.db")) as index,
    ):
        index.execute(
            "CREATE TABLE inputs (path TEXT PRIMARY KEY) WITHOUT ROWID"
        )
        inserted = index.executemany(
            "INSERT INTO inputs VALUES (?)",
            (
                (path.relative_to(source).as_posix(),)
                for path in _find_files(source)
            ),
        )
        if inserted.rowcount == 0:
            msg = f"no .bin replays in {source}"
            raise ConversionError(msg)
        with closing(
            index.execute("SELECT path FROM inputs ORDER BY path")
        ) as rows:
            yield (source / relative_path for (relative_path,) in rows)

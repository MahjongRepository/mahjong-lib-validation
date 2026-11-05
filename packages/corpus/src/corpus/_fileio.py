"""Shared JSON decoding and atomic file replacement."""

import json
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
lazy from collections.abc import Generator

from corpus.errors import CorpusError


def decode_json(
    content: bytes, path: Path, *, line: int | None = None
) -> object:
    field = "$"
    try:
        text = content.decode("utf-8")
        if line is None:
            # Match the universal newlines of whole-file text reads.
            text = text.replace("\r\n", "\n").replace("\r", "\n")
        return json.loads(text)
    except json.JSONDecodeError as error:
        number = error.lineno if line is None else line
        raise CorpusError(field, error.msg, path=path, line=number) from error
    except UnicodeDecodeError as error:
        raise CorpusError(
            field, "invalid UTF-8", path=path, line=line
        ) from error


@contextmanager
def atomic_path(path: Path) -> Generator[Path]:
    with NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        staging = Path(temporary.name)
    try:
        yield staging
        staging.replace(path)
    finally:
        staging.unlink(missing_ok=True)

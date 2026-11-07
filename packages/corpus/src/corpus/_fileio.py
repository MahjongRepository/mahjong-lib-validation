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
        return json.loads(text)
    except json.JSONDecodeError as e:
        number = e.lineno if line is None else line
        raise CorpusError(field, e.msg, path=path, line=number) from e
    except UnicodeDecodeError as e:
        raise CorpusError(field, "invalid UTF-8", path=path, line=line) from e


@contextmanager
def atomic_path(path: Path) -> Generator[Path]:
    with NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        staging = Path(temporary.name)

    try:
        yield staging
        staging.replace(path)
    finally:
        staging.unlink(missing_ok=True)

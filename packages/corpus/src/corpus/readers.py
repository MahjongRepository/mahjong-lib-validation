"""Stream scoring cases from UTF-8 JSON Lines."""

import gzip
import json
from collections.abc import Iterator
from pathlib import Path

from corpus.checks import parse_case
from corpus.errors import CorpusError
from corpus.models import ScoringCase


def read_cases(path: str | Path) -> Iterator[ScoringCase]:
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as stream:
        for number, line in enumerate(stream, 1):
            try:
                case = parse_case(json.loads(line.decode("utf-8")))
            except json.JSONDecodeError as error:
                field = "$"
                raise CorpusError(
                    field, error.msg, path=path, line=number
                ) from error
            except CorpusError as error:
                raise CorpusError(
                    error.field, error.message, path=path, line=number
                ) from error
            except UnicodeDecodeError as error:
                field = "$"
                raise CorpusError(
                    field, "invalid UTF-8", path=path, line=number
                ) from error
            yield case

"""Stream scoring cases from UTF-8 JSON Lines."""

import gzip
from pathlib import Path
lazy from collections.abc import Generator

from corpus._fileio import decode_json
from corpus.checks import parse_case
from corpus.errors import CorpusError
lazy from corpus.models import ScoringCase


def read_cases(path: str | Path) -> Generator[ScoringCase]:
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as stream:
        for number, line in enumerate(stream, 1):
            value = decode_json(line, path, line=number)
            try:
                case = parse_case(value)
            except CorpusError as error:
                raise CorpusError(
                    error.field, error.message, path=path, line=number
                ) from error
            yield case

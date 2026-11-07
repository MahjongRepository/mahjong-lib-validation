"""Read and write scoring cases as UTF-8 JSON Lines."""

import gzip
import json
from pathlib import Path
lazy from collections.abc import Generator, Iterable

from corpus._fileio import atomic_path, decode_json
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
            except CorpusError as e:
                raise CorpusError(
                    e.field, e.message, path=path, line=number
                ) from e
            yield case


def write_cases(path: str | Path, cases: Iterable[ScoringCase]) -> int:
    path = Path(path)
    count = 0
    with atomic_path(path) as staging:
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(staging, "wt", encoding="utf-8", newline="\n") as stream:
            for case in cases:
                stream.write(json.dumps(parse_case(case), ensure_ascii=False))
                stream.write("\n")
                count += 1
    return count

"""Write scoring cases as UTF-8 JSON Lines."""

import gzip
import json
from collections.abc import Iterable
from pathlib import Path

from corpus._fileio import atomic_path
from corpus.checks import parse_case
from corpus.models import ScoringCase


def write_cases(path: str | Path, cases: Iterable[ScoringCase]) -> None:
    _write_cases(Path(path), cases)


def _write_cases(path: Path, cases: Iterable[ScoringCase]) -> int:
    count = 0
    with atomic_path(path) as staging:
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(staging, "wt", encoding="utf-8", newline="\n") as stream:
            for case in cases:
                stream.write(json.dumps(parse_case(case), ensure_ascii=False))
                stream.write("\n")
                count += 1
    return count

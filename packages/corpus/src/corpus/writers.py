"""Write scoring cases as UTF-8 JSON Lines."""

import gzip
import json
from collections.abc import Iterable
from pathlib import Path
from tempfile import NamedTemporaryFile

from corpus.checks import parse_case
from corpus.models import ScoringCase


def write_cases(path: str | Path, cases: Iterable[ScoringCase]) -> None:
    path = Path(path)
    with NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        staging = Path(temporary.name)
    try:
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(staging, "wt", encoding="utf-8", newline="\n") as stream:
            for case in cases:
                stream.write(json.dumps(parse_case(case), ensure_ascii=False))
                stream.write("\n")
        staging.replace(path)
    finally:
        staging.unlink(missing_ok=True)

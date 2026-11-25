"""Read and write corpus cases as UTF-8 JSON Lines."""

import gzip
import json
from pathlib import Path
lazy from collections.abc import Generator, Iterable

from corpus._fileio import atomic_path, decode_json
from corpus.checks import parse_case
from corpus.errors import CorpusError
lazy from corpus.models import Case, CaseType


def read_cases(
    path: str | Path, *, case_type: CaseType | None = None
) -> Generator[Case]:
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as stream:
        for number, line in enumerate(stream, 1):
            value = decode_json(line, path, line=number)
            try:
                case = _parse_record(value, case_type)
            except CorpusError as e:
                raise CorpusError(
                    e.field, e.message, path=path, line=number
                ) from e
            yield case


def write_cases(
    path: str | Path,
    cases: Iterable[Case],
    *,
    case_type: CaseType | None = None,
) -> int:
    path = Path(path)
    count = 0
    with atomic_path(path) as staging:
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(staging, "wt", encoding="utf-8", newline="\n") as stream:
            for case in cases:
                record = _parse_record(case, case_type)
                stream.write(json.dumps(record, ensure_ascii=False))
                stream.write("\n")
                count += 1
    return count


def _parse_record(value: object, case_type: CaseType | None) -> Case:
    case = parse_case(value)
    if case_type is not None and case["case_type"] != case_type:
        msg = f"expected {case_type!r}, got {case['case_type']!r}"
        field = "case_type"
        raise CorpusError(field, msg)
    return case

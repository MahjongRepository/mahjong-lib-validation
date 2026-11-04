import json
from pathlib import Path

from corpus import parse_case, write_dataset
lazy from corpus.models import ScoringCase


def load_case(name: str = "tenhou-scoring") -> ScoringCase:
    fixture = (
        Path(__file__).parents[2] / "corpus/tests/fixtures" / f"{name}.json"
    )
    return parse_case(json.loads(fixture.read_text(encoding="utf-8")))


def save_dataset(directory: Path, cases: list[ScoringCase]) -> Path:
    write_dataset(
        directory,
        cases,
        generator={"name": "test", "version": "1", "settings": {}},
        conversion={
            "input_count": len(cases),
            "converted_count": len(cases),
            "failed_by_reason": {},
            "excluded_by_reason": {},
        },
        cases_per_file=1,
    )
    return directory

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from corpus import parse_case, write_dataset

if TYPE_CHECKING:
    from collections.abc import Callable

    from corpus.models import ScoringCase


@pytest.fixture
def load_case() -> Callable[..., ScoringCase]:
    def load(name: str = "tenhou-scoring") -> ScoringCase:
        fixture = (
            Path(__file__).parents[2]
            / "corpus/tests/fixtures"
            / f"{name}.json"
        )
        return parse_case(json.loads(fixture.read_text(encoding="utf-8")))

    return load


@pytest.fixture
def save_dataset() -> Callable[[Path, list[ScoringCase]], Path]:
    def save(directory: Path, cases: list[ScoringCase]) -> Path:
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

    return save

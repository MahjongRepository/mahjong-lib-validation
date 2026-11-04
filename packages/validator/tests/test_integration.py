import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from tenhou_converter import convert_log

from validator import validate_dataset

if TYPE_CHECKING:
    from collections.abc import Callable

    from corpus.models import ScoringCase


@pytest.mark.parametrize(
    "fixture",
    [
        "four-ron",
        "four-melds",
        "four-kokushi",
        "sanma-tsumo",
        "sanma-three-nuki",
    ],
)
def test_xml_to_corpus_to_library(
    save_dataset: Callable[[Path, list[ScoringCase]], Path],
    tmp_path: Path,
    fixture: str,
) -> None:
    source = (
        Path(__file__).parents[2]
        / "tenhou-converter/tests/fixtures"
        / f"{fixture}.xml"
    )
    cases = convert_log(source.read_bytes(), log_id=f"masked-{fixture}")
    dataset = save_dataset(tmp_path / "corpus", cases)
    output = tmp_path / "result"
    summary = validate_dataset(dataset, output)
    results = [
        json.loads(line)
        for line in (output / "cases.jsonl").read_text().splitlines()
    ]
    assert summary["exit_code"] == 0, results
    assert summary["counts"]["passed"] == len(cases)

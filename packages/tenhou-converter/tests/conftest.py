import json
from pathlib import Path

import pytest

_SHAPE_TARGETS = (
    Path(__file__).resolve().parents[2] / "test-data" / "shape-targets.json"
)


@pytest.fixture(
    params=json.loads(_SHAPE_TARGETS.read_text(encoding="utf-8")),
    ids=lambda row: row[0],
)
def shape_target(
    request: pytest.FixtureRequest,
) -> tuple[str, str, bool, dict[str, bool | int]]:
    target, case_type, complete, expected = request.param
    return target, case_type, complete, expected

import json
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def example() -> dict[str, Any]:
    path = (
        Path(__file__).resolve().parents[3]
        / "docs/examples/corpus/tenhou-scoring.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))

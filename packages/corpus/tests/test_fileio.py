from pathlib import Path

import pytest
from corpus._fileio import decode_json
from corpus.errors import CorpusError


@pytest.mark.parametrize("line", [None, 7])
def test_decode_json_keeps_original_newlines(line: int | None) -> None:
    with pytest.raises(CorpusError) as error:
        decode_json(b'{\r"key":', Path("input.json"), line=line)
    assert error.value.line == (1 if line is None else line)

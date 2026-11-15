from pathlib import Path
from re import escape

import pytest
from tenhou_converter.sources import log_id_from_path


@pytest.mark.parametrize(
    "name", ["game", "game.txt", "game.gz", "game.xml.zip"]
)
def test_log_id_rejects_unsupported_extension(name: str) -> None:
    path = Path(name)
    with pytest.raises(ValueError, match=escape(str(path))):
        log_id_from_path(path)


@pytest.mark.parametrize("suffix", [".xml", ".mjlog", ".xml.gz", ".mjlog.gz"])
@pytest.mark.parametrize("prefix", ["", " \t"], ids=["empty", "whitespace"])
def test_log_id_rejects_empty_name_before_extension(
    prefix: str, suffix: str
) -> None:
    path = Path(prefix + suffix)
    with pytest.raises(ValueError, match=escape(str(path))):
        log_id_from_path(path)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("game.xml", "game"),
        ("game.mjlog", "game"),
        ("game.xml.gz", "game"),
        ("game.MJLOG.GZ", "game"),
        (" game .xml", " game "),
        ("game.xml.mjlog.gz", "game.xml"),
    ],
)
def test_log_id_preserves_name_and_removes_supported_extension(
    name: str, expected: str
) -> None:
    assert log_id_from_path(Path("logs") / name) == expected

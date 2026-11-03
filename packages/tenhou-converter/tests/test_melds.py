import pytest
from tenhou_converter.errors import ConversionError
from tenhou_converter.melds import decode_meld, tile
from tenhou_converter.parser import Event


@pytest.mark.parametrize(
    ("code", "kind", "tiles", "called", "source"),
    [
        (7, "chii", [0, 4, 8], 0, 3),
        (32775, "chii", [48, 52, 56], 2, 3),
        (41514, "pon", [108, 110, 111], 0, 2),
        (41522, "kakan", [108, 110, 111, 109], 0, 2),
        (27648, "ankan", [108, 109, 110, 111], None, None),
        (28161, "daiminkan", [108, 109, 110, 111], 2, 1),
        (31264, "nuki", [122], None, None),
    ],
)
def test_meld_wire_slots(
    code: int,
    kind: str,
    tiles: list[int],
    called: int | None,
    source: int | None,
) -> None:
    meld = decode_meld(code, 0, Event(9, "N", {}))
    assert (meld.kind, meld.tiles, meld.called, meld.source) == (
        kind,
        tiles,
        called,
        source,
    )


@pytest.mark.parametrize(
    "code", [-1, 65536, 127 << 9 | 8 | 1, 63 << 10 | 7, 10 << 8 | 32]
)
def test_unknown_meld_codes_have_event_location(code: int) -> None:
    with pytest.raises(ConversionError) as caught:
        decode_meld(code, 0, Event(9, "N", {}))
    assert caught.value.reason == "unknown_meld_code"
    assert caught.value.event_index == 9


def test_red_and_regular_fives_remain_distinct() -> None:
    assert [tile(value) for value in (16, 17, 52, 53, 88, 89)] == [
        "0m",
        "5m",
        "0p",
        "5p",
        "0s",
        "5s",
    ]

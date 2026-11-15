import pytest
from tenhou_converter.errors import ConversionError
from tenhou_converter.melds import decode_meld, tile
from tenhou_converter.parser import Event


@pytest.mark.parametrize(
    ("code", "kind", "tiles", "called", "source"),
    [
        (7, "chii", [0, 4, 8], 0, 3),
        (7 | 0x18, "chii", [3, 4, 8], 0, 3),
        (32775, "chii", [48, 52, 56], 2, 3),
        (62 << 10 | 7, "chii", [96, 100, 104], 2, 3),
        (41514, "pon", [108, 110, 111], 0, 2),
        (41522, "kakan", [108, 110, 111, 109], 0, 2),
        (101 << 9 | 0x69, "pon", [132, 133, 134], 2, 1),
        (101 << 9 | 0x71, "kakan", [132, 133, 134, 135], 2, 1),
        (27648, "ankan", [108, 109, 110, 111], None, None),
        (28161, "daiminkan", [108, 109, 110, 111], 2, 1),
        (0, "ankan", [0, 1, 2, 3], None, None),
        (1, "daiminkan", [0, 1, 2, 3], 0, 1),
        (135 << 8, "ankan", [132, 133, 134, 135], None, None),
        (135 << 8 | 3, "daiminkan", [132, 133, 134, 135], 3, 3),
        (31264, "nuki", [122], None, None),
        (120 << 8 | 0x20, "nuki", [120], None, None),
        (121 << 8 | 0x20, "nuki", [121], None, None),
        (123 << 8 | 0x20, "nuki", [123], None, None),
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


@pytest.mark.parametrize(
    "code",
    [63 << 10 | 7, 6, 7 | 0x0200],
    ids=["pattern-limit", "not-previous-seat", "unused-bit"],
)
def test_invalid_chii_preserves_error_details(code: int) -> None:
    with pytest.raises(ConversionError) as caught:
        decode_meld(code, 0, Event(9, "N", {}))

    assert caught.value.reason == "unknown_meld_code"
    assert caught.value.field == "m"
    assert caught.value.event_index == 9


@pytest.mark.parametrize("flag", [0x08, 0x10], ids=["pon", "kakan"])
@pytest.mark.parametrize(
    "layout",
    [102 << 9 | 1, 0, 0x81, 0x101, 0x19],
    ids=[
        "pattern-limit",
        "self-source",
        "unused-bit-7",
        "unused-bit-8",
        "both-flags",
    ],
)
def test_invalid_pon_or_kakan_preserves_error_details(
    flag: int, layout: int
) -> None:
    with pytest.raises(ConversionError) as caught:
        decode_meld(flag | layout, 0, Event(9, "N", {}))

    assert caught.value.reason == "unknown_meld_code"
    assert caught.value.field == "m"
    assert caught.value.event_index == 9


@pytest.mark.parametrize(
    "code",
    [120 << 8 | 0x21, 120 << 8 | 0xA0, 119 << 8 | 0x20, 124 << 8 | 0x20],
    ids=["source-bits", "unused-bit", "below-north", "above-north"],
)
def test_invalid_north_extraction_preserves_error_details(code: int) -> None:
    with pytest.raises(ConversionError) as caught:
        decode_meld(code, 0, Event(9, "N", {}))

    assert caught.value.reason == "unknown_meld_code"
    assert caught.value.field == "m"
    assert caught.value.event_index == 9


@pytest.mark.parametrize("relative", [0, 1], ids=["ankan", "daiminkan"])
@pytest.mark.parametrize(
    "layout",
    [136 << 8, 0x40, 0x80],
    ids=["tile-limit", "unused-bit-6", "unused-bit-7"],
)
def test_invalid_kan_preserves_error_details(
    relative: int, layout: int
) -> None:
    with pytest.raises(ConversionError) as caught:
        decode_meld(layout | relative, 0, Event(9, "N", {}))

    assert caught.value.reason == "unknown_meld_code"
    assert caught.value.field == "m"
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

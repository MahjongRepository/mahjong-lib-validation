# XML inputs below are trusted local fixtures.
# ruff: noqa: S314
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from tenhou_converter import convert_log
from tenhou_converter.errors import ConversionError
from tenhou_converter.parser import Event
from tenhou_converter.reconstruction import RoundState

FIXTURES = Path(__file__).parent / "fixtures"


def test_log_id_is_preserved_and_only_case_id_is_percent_encoded() -> None:
    (case,) = convert_log(
        (FIXTURES / "four-ron.xml").read_bytes(), log_id="example:game%/1"
    )
    assert case["source"]["log_id"] == "example:game%/1"
    assert case["case_id"] == "tenhou:example%3Agame%25%2F1:east:1:0:1"


@pytest.mark.parametrize(
    ("tag", "field", "value", "reason"),
    [
        ("GO", "type", "x", "invalid_attribute"),
        ("INIT", "seed", "0", "invalid_attribute"),
        ("INIT", "seed", "12,0,0,0,1,31", "invalid_attribute"),
        ("INIT", "seed", "-1,0,0,0,1,31", "invalid_attribute"),
        ("INIT", "seed", "0,-1,0,0,1,31", "invalid_attribute"),
        ("INIT", "seed", "0,0,-1,0,1,31", "invalid_attribute"),
        ("AGARI", "yaku", "999,1", "unknown_yaku_id"),
        ("AGARI", "who", "4", "invalid_attribute"),
        ("AGARI", "hai", "102", "inconsistent_events"),
    ],
)
def test_invalid_records_are_positioned_errors(
    tag: str, field: str, value: str, reason: str
) -> None:
    root = ET.parse(FIXTURES / "four-ron.xml").getroot()
    event = root.find(tag)
    assert event is not None
    event.set(field, value)
    with pytest.raises(ConversionError) as caught:
        convert_log(ET.tostring(root), log_id="synthetic-invalid")
    assert caught.value.reason == reason
    assert caught.value.event_index is not None


def test_sanma_rejects_round_without_matching_seat() -> None:
    root = ET.parse(FIXTURES / "sanma-tsumo.xml").getroot()
    init = root.find("INIT")
    assert init is not None
    seed = init.get("seed", "").split(",")
    seed[0] = "3"
    init.set("seed", ",".join(seed))

    with pytest.raises(ConversionError) as caught:
        convert_log(ET.tostring(root), log_id="synthetic-invalid-round")

    assert caught.value.reason == "invalid_attribute"
    assert caught.value.field == "seed"


@pytest.mark.parametrize("index", [3, 4])
@pytest.mark.parametrize("value", [-1, 6])
def test_round_state_rejects_invalid_dice(index: int, value: int) -> None:
    root = ET.parse(FIXTURES / "four-ron.xml").getroot()
    init = root.find("INIT")
    assert init is not None
    seed = init.attrib["seed"].split(",")
    seed[index] = str(value)
    init.set("seed", ",".join(seed))

    with pytest.raises(ConversionError) as caught:
        RoundState.start(Event(0, "INIT", dict(init.attrib)), 4)

    assert caught.value.reason == "invalid_attribute"
    assert caught.value.field == "seed"


@pytest.mark.parametrize("value", [-1, 136])
def test_round_state_rejects_invalid_initial_indicator(value: int) -> None:
    root = ET.parse(FIXTURES / "four-ron.xml").getroot()
    init = root.find("INIT")
    assert init is not None
    seed = init.attrib["seed"].split(",")
    seed[5] = str(value)
    init.set("seed", ",".join(seed))

    with pytest.raises(ConversionError) as caught:
        RoundState.start(Event(0, "INIT", dict(init.attrib)), 4)

    assert caught.value.reason == "invalid_attribute"
    assert caught.value.field == "seed"


@pytest.mark.parametrize(("first_die", "second_die"), [(0, 5), (5, 0)])
@pytest.mark.parametrize("indicator", [0, 135])
def test_round_state_accepts_dice_and_indicator_boundaries(
    first_die: int, second_die: int, indicator: int
) -> None:
    root = ET.parse(FIXTURES / "four-ron.xml").getroot()
    init = root.find("INIT")
    assert init is not None
    init.set("seed", f"0,0,0,{first_die},{second_die},{indicator}")
    # Keep both possible indicators out of the initial hands.
    hand = init.attrib["hai0"].split(",")
    hand[hand.index("135")] = "2"
    init.set("hai0", ",".join(hand))

    state = RoundState.start(Event(0, "INIT", dict(init.attrib)), 4)

    assert state.indicators == [indicator]


@pytest.mark.parametrize(
    ("player_count", "field", "value"),
    [
        (4, "ten", "250,250,250"),
        (4, "ten", "250,-1,250,250"),
        (3, "ten", "350,350,350,1"),
        (3, "hai3", "0"),
    ],
)
def test_round_state_rejects_invalid_scores_or_extra_seat(
    player_count: int, field: str, value: str
) -> None:
    fixture = "sanma-tsumo.xml" if player_count == 3 else "four-ron.xml"
    root = ET.parse(FIXTURES / fixture).getroot()
    init = root.find("INIT")
    assert init is not None
    init.set(field, value)

    with pytest.raises(ConversionError) as caught:
        RoundState.start(Event(0, "INIT", dict(init.attrib)), player_count)

    assert caught.value.reason == "invalid_attribute"
    assert caught.value.field == "ten"


def test_round_state_accepts_west_four() -> None:
    root = ET.parse(FIXTURES / "four-ron.xml").getroot()
    init = root.find("INIT")
    assert init is not None
    init.set("seed", "11,0,0,0,1,31")
    init.set("oya", "3")

    state = RoundState.start(Event(0, "INIT", dict(init.attrib)), 4)

    assert state.dealer == 3


def test_four_player_ron_matches_independently_checked_case() -> None:
    expected = json.loads(
        (FIXTURES / "four-ron.json").read_text(encoding="utf-8")
    )
    cases = convert_log(
        (FIXTURES / "four-ron.xml").read_bytes(), log_id="masked-four"
    )
    assert cases == [expected]


def test_sanma_north_extraction_and_actual_tsumo_payments() -> None:
    (case,) = convert_log(
        (FIXTURES / "sanma-tsumo.xml").read_bytes(), log_id="masked-sanma"
    )
    assert case["player_count"] == 3
    assert case["input"]["nuki_count"] == 1
    assert case["input"]["melds"] == []
    assert case["expected"]["base_points"] == 2000
    assert case["expected"]["payments_by_seat"] == [700, 1300, 0]
    assert case["expected"]["riichi_stick_points"] == 1000


def test_open_hand_preserves_decoded_melds() -> None:
    (case,) = convert_log(
        (FIXTURES / "four-melds.xml").read_bytes(), log_id="masked-open"
    )
    assert case["input"]["melds"] == [
        {
            "type": "pon",
            "tiles": ["7p", "7p", "7p"],
            "called_tile_index": 2,
            "from_seat": 2,
        },
        {
            "type": "pon",
            "tiles": ["3z", "3z", "3z"],
            "called_tile_index": 0,
            "from_seat": 0,
        },
    ]
    assert case["expected"]["han"] == 3


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("machi", "91", "win does not match tile provider"),
        ("hai", "16,19,25,31,32,92,99", "AGARI hand differs"),
        ("m", "24105", "AGARI calls differ"),
        ("doraHai", "96", "AGARI dora differs"),
    ],
)
def test_agari_tile_mismatches_keep_positioned_errors(
    field: str, value: str, message: str
) -> None:
    root = ET.parse(FIXTURES / "four-melds.xml").getroot()
    root[-1].set(field, value)

    with pytest.raises(ConversionError) as caught:
        convert_log(ET.tostring(root), log_id="synthetic-mismatch")

    assert caught.value.reason == "inconsistent_events"
    assert caught.value.message.startswith(message)
    assert caught.value.event_index == len(root) - 1
    assert caught.value.field is None


def test_kokushi_preserves_recorded_zero_fu_and_excludes_comparison() -> None:
    (case,) = convert_log(
        (FIXTURES / "four-kokushi.xml").read_bytes(), log_id="masked-kokushi"
    )
    assert case["expected"]["fu"] == 0
    assert case["expected"]["han"] is None
    assert case["expected"]["title"] == "yakuman"
    assert case["expected"]["yakuman_multiplier"] == 1
    assert case["comparison"]["excluded_fields"] == [
        {"field": "fu", "reason": "kokushi_fu_not_comparable"}
    ]


def test_log_ending_in_live_round_is_not_returned_as_success() -> None:
    root = ET.parse(FIXTURES / "four-ron.xml").getroot()
    root.remove(root[-1])
    with pytest.raises(ConversionError, match="incomplete_log"):
        convert_log(ET.tostring(root), log_id="masked-truncated")


def test_missing_draw_is_a_broken_progression_not_a_false_situation() -> None:
    root = ET.parse(FIXTURES / "four-ron.xml").getroot()
    root.remove(root[-3])
    with pytest.raises(ConversionError, match="inconsistent_events"):
        convert_log(ET.tostring(root), log_id="masked-gap")


def test_agari_after_drawn_round_is_rejected() -> None:
    root = ET.parse(FIXTURES / "four-ron.xml").getroot()
    root.insert(len(root) - 1, ET.Element("RYUUKYOKU"))
    with pytest.raises(ConversionError, match="inconsistent_events"):
        convert_log(ET.tostring(root), log_id="synthetic-after-draw")


def test_score_components_must_match_the_available_riichi_sticks() -> None:
    root = ET.parse(FIXTURES / "four-ron.xml").getroot()
    root[-1].set("sc", "250,-26,250,0,240,46,250,0")
    with pytest.raises(ConversionError, match="sticks"):
        convert_log(ET.tostring(root), log_id="synthetic-extra-sticks")


def test_kazoe_title_requires_recorded_thirteen_han() -> None:
    root = ET.parse(FIXTURES / "four-ron.xml").getroot()
    root[-1].set("ten", "40,2600,5")
    with pytest.raises(ConversionError, match="invalid_attribute"):
        convert_log(ET.tostring(root), log_id="synthetic-false-kazoe")


def test_exhaustive_draw_cannot_end_with_live_tiles_remaining() -> None:
    root = ET.parse(FIXTURES / "four-ron.xml").getroot()
    root[-1].tag = "RYUUKYOKU"
    with pytest.raises(ConversionError, match="inconsistent_events"):
        convert_log(ET.tostring(root), log_id="synthetic-early-draw")

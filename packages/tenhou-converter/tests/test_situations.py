from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from tenhou_converter import ConversionError, convert_log

FIXTURES = Path(__file__).parent / "fixtures"


def test_added_kan_requires_a_draw_after_the_pon() -> None:
    root = ET.parse(FIXTURES / "synthetic-chankan-ippatsu.xml").getroot()  # noqa: S314 -- trusted fixture
    init = root.find("INIT")
    assert init is not None
    init.set("hai1", init.attrib["hai1"].replace("112", "127"))
    retained = [*list(root)[:5], root[-2], root[-1]]
    root[:] = retained
    root[-1].set("ba", "0,0")
    root[-1].set("sc", "250,0,250,-320,250,320,250,0")
    with pytest.raises(ConversionError, match="inconsistent_events"):
        convert_log(ET.tostring(root), log_id="synthetic-immediate-kakan")


@pytest.mark.parametrize("name", ["haitei", "houtei"])
def test_last_live_draw_and_discard(name: str) -> None:
    (case,) = convert_log(
        (FIXTURES / f"synthetic-sanma-{name}.xml").read_bytes(),
        log_id="synthetic-last-tile",
    )
    assert case["input"]["situation"]["haitei"] is (name == "haitei")
    assert case["input"]["situation"]["houtei"] is (name == "houtei")
    assert case["input"]["situation"]["rinshan"] is False


def test_ankan_rinshan_and_additional_indicator() -> None:
    (case,) = convert_log(
        (FIXTURES / "synthetic-ankan-rinshan.xml").read_bytes(),
        log_id="synthetic-ankan",
    )
    assert case["input"]["situation"]["rinshan"] is True
    assert case["input"]["melds"] == [
        {
            "type": "ankan",
            "tiles": ["5z"] * 4,
            "called_tile_index": None,
            "from_seat": None,
        }
    ]
    assert case["input"]["dora_indicators"] == ["7z", "8s"]


def test_chankan_preserves_ippatsu_even_for_yakuman() -> None:
    (case,) = convert_log(
        (FIXTURES / "synthetic-chankan-ippatsu.xml").read_bytes(),
        log_id="synthetic-chankan",
    )
    assert case["input"]["situation"]["chankan"] is True
    assert case["input"]["situation"]["ippatsu"] is True
    assert case["input"]["situation"]["riichi"] == "riichi"
    assert case["expected"]["yaku"] == [
        {"id": "kokushi_musou", "han": None, "yakuman_multiplier": 1}
    ]


def test_dealer_first_draw_tenhou_is_reconstructed() -> None:
    (case,) = convert_log(
        (FIXTURES / "synthetic-tenhou.xml").read_bytes(),
        log_id="synthetic-tenhou",
    )
    assert case["input"]["situation"]["tenhou"] is True
    assert case["input"]["situation"]["chiihou"] is False


def test_nuki_supplemental_tsumo_is_rinshan_and_interrupts_first_draw() -> (
    None
):
    (case,) = convert_log(
        (FIXTURES / "synthetic-nuki-rinshan.xml").read_bytes(),
        log_id="synthetic-nuki",
    )
    assert case["input"]["nuki_count"] == 1
    assert case["input"]["melds"] == []
    assert case["input"]["situation"]["rinshan"] is True
    assert case["input"]["situation"]["tenhou"] is False
    assert case["input"]["situation"]["haitei"] is False


def test_double_ron_uses_source_order_and_each_recorded_allocation() -> None:
    cases = convert_log(
        (FIXTURES / "synthetic-double-ron.xml").read_bytes(),
        log_id="synthetic-double",
    )
    assert [case["win_number"] for case in cases] == [1, 2]
    assert [case["source"]["winner_index"] for case in cases] == [0, 0]
    assert [case["input"]["winner_seat"] for case in cases] == [1, 2]
    assert [case["expected"]["honba_points"] for case in cases] == [300, 0]
    assert [case["expected"]["riichi_stick_points"] for case in cases] == [
        1000,
        0,
    ]
    assert [case["round"]["riichi_sticks"] for case in cases] == [1, 1]


def test_shared_double_ron_deltas_do_not_become_individual_payments() -> None:
    root = ET.parse(FIXTURES / "synthetic-double-ron.xml").getroot()  # noqa: S314 -- trusted fixture
    for event in root.findall("AGARI"):
        event.set("sc", "250,-29,250,26,250,13,250,0")
    cases = convert_log(ET.tostring(root), log_id="synthetic-shared-double")
    for case in cases:
        assert case["expected"]["base_points"] == 1300
        assert case["expected"]["payments_by_seat"] is None
        assert case["expected"]["honba_points"] is None
        assert case["expected"]["event_score_deltas"] == [-2900, 2600, 1300, 0]
        assert {
            item["field"] for item in case["comparison"]["excluded_fields"]
        } == {"payments_by_seat", "honba_points", "riichi_stick_points"}


@pytest.mark.parametrize("gain", [16, 36])
def test_shared_double_ron_must_account_for_available_sticks(
    gain: int,
) -> None:
    root = ET.parse(FIXTURES / "synthetic-double-ron.xml").getroot()  # noqa: S314 -- trusted fixture
    for event in root.findall("AGARI"):
        event.set("sc", f"250,-29,250,{gain},250,13,250,0")

    with pytest.raises(ConversionError, match="riichi sticks"):
        convert_log(ET.tostring(root), log_id="synthetic-shared-bad-sticks")


def test_missing_riichi_confirmation_cannot_advance_to_next_draw() -> None:
    root = ET.parse(FIXTURES / "four-ron.xml").getroot()  # noqa: S314 -- trusted fixture
    for event in list(root):
        if event.tag == "REACH" and event.get("step") == "2":
            root.remove(event)
    agari = root.find("AGARI")
    assert agari is not None
    # Keep settlement consistent so it cannot hide the progression gap.
    agari.set("ba", "0,0")
    agari.set("sc", "250,-26,250,0,250,26,250,0")

    with pytest.raises(ConversionError, match="riichi confirmation") as caught:
        convert_log(ET.tostring(root), log_id="synthetic-missing-reach")

    assert caught.value.event_index == next(
        index for index, event in enumerate(root) if event.tag == "W61"
    )


def test_missing_riichi_confirmation_cannot_advance_to_call() -> None:
    root = ET.parse(FIXTURES / "synthetic-chankan-ippatsu.xml").getroot()  # noqa: S314 -- trusted fixture
    root.insert(3, ET.Element("REACH", who="0", step="1"))

    with pytest.raises(ConversionError, match="riichi confirmation") as caught:
        convert_log(ET.tostring(root), log_id="synthetic-missing-reach-call")

    assert caught.value.event_index == 5


def test_ron_on_riichi_declaration_discard_does_not_require_confirmation() -> (
    None
):
    root = ET.parse(FIXTURES / "synthetic-double-ron.xml").getroot()  # noqa: S314 -- trusted fixture
    root.insert(3, ET.Element("REACH", who="0", step="1"))

    cases = convert_log(ET.tostring(root), log_id="synthetic-declaration-ron")

    assert len(cases) == 2
    assert [case["round"]["riichi_sticks"] for case in cases] == [1, 1]
    assert [case["expected"]["riichi_stick_points"] for case in cases] == [
        1000,
        0,
    ]


def test_riichi_declaration_cannot_be_followed_by_tsumo() -> None:
    root = ET.parse(FIXTURES / "synthetic-tenhou.xml").getroot()  # noqa: S314 -- trusted fixture
    root.insert(len(root) - 1, ET.Element("REACH", who="0", step="1"))

    with pytest.raises(ConversionError, match="riichi confirmation"):
        convert_log(ET.tostring(root), log_id="synthetic-declaration-tsumo")


@pytest.mark.parametrize("reason", ["reach4", "ron3"])
def test_pending_riichi_at_drawn_round_requires_ron_on_declaration(
    reason: str,
) -> None:
    root = ET.parse(FIXTURES / "synthetic-double-ron.xml").getroot()  # noqa: S314 -- trusted fixture
    root.insert(3, ET.Element("REACH", who="0", step="1"))
    for event in root.findall("AGARI"):
        root.remove(event)
    root.append(
        ET.Element(
            "RYUUKYOKU",
            type=reason,
            ba="1,1",
            sc="250,0,250,0,250,0,250,0",
        )
    )

    if reason == "ron3":
        assert (
            convert_log(ET.tostring(root), log_id="synthetic-reach-ron3") == []
        )
    else:
        with pytest.raises(ConversionError, match="riichi confirmation"):
            convert_log(ET.tostring(root), log_id="synthetic-unconfirmed-draw")

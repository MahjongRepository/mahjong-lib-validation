# XML inputs below are trusted local fixtures.
# ruff: noqa: S314
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from tenhou_converter import ConversionError, convert_log

FIXTURES = Path(__file__).parent / "fixtures"


def test_individual_pao_ron_continues_from_negative_balance() -> None:
    cases = convert_log(
        (FIXTURES / "synthetic-sanma-pao-double-ron.xml").read_bytes(),
        log_id="synthetic-individual-pao",
    )

    assert [case["win_number"] for case in cases] == [1, 2]
    assert [case["input"]["discarder_seat"] for case in cases] == [2, 2]
    assert [case["input"]["winning_tile"] for case in cases] == ["1z", "1z"]
    assert [case["source"]["event_index"] for case in cases] == [20, 21]
    assert cases[0]["expected"]["payments_by_seat"] == [0, 24000, 24000]
    assert cases[1]["expected"]["winner_gain"] == 3200
    assert cases[1]["expected"]["payments_by_seat"] == [0, 0, 3200]
    assert cases[1]["source"]["scoring_values"]["sc"] == (
        "980,0,-140,32,210,-32,0,0"
    )


def test_shared_pao_ron_does_not_treat_net_loss_as_own_payment() -> None:
    root = ET.parse(FIXTURES / "synthetic-sanma-pao-double-ron.xml").getroot()
    for event in root.findall("AGARI"):
        event.set("sc", "500,480,100,-208,450,-272,0,0")

    cases = convert_log(ET.tostring(root), log_id="synthetic-shared-pao")

    assert [case["input"]["winner_seat"] for case in cases] == [0, 1]
    for case in cases:
        assert case["expected"]["event_score_deltas"] == [
            48000,
            -20800,
            -27200,
        ]
        for field in (
            "winner_gain",
            "payments_by_seat",
            "honba_points",
            "riichi_stick_points",
        ):
            assert case["expected"][field] is None
        assert {
            item["field"] for item in case["comparison"]["excluded_fields"]
        } == {
            "winner_gain",
            "payments_by_seat",
            "honba_points",
            "riichi_stick_points",
        }


def test_individual_pao_ron_rejects_inconsistent_intermediate_balance() -> (
    None
):
    root = ET.parse(FIXTURES / "synthetic-sanma-pao-double-ron.xml").getroot()
    root.findall("AGARI")[1].set("sc", "980,0,-139,32,210,-32,0,0")

    with pytest.raises(ConversionError, match="balance") as caught:
        convert_log(ET.tostring(root), log_id="synthetic-bad-balance")

    assert caught.value.event_index == 21
    assert caught.value.field == "sc"


def test_shared_ron_checks_group_honba_without_individual_allocation() -> None:
    root = ET.parse(FIXTURES / "synthetic-double-ron.xml").getroot()
    for event in root.findall("AGARI"):
        event.set("sc", "250,-26,250,23,250,13,250,0")

    with pytest.raises(ConversionError, match="honba"):
        convert_log(ET.tostring(root), log_id="synthetic-missing-group-honba")


@pytest.mark.parametrize("shared", [False, True])
def test_next_round_checks_final_balances_once(*, shared: bool) -> None:
    root = ET.parse(FIXTURES / "synthetic-double-ron.xml").getroot()
    if shared:
        for event in root.findall("AGARI"):
            event.set("sc", "250,-29,250,26,250,13,250,0")
    init = root.find("INIT")
    assert init is not None
    following = deepcopy(init)
    following.set("seed", "1,0,0,0,0,135")
    following.set("oya", "1")
    following.set("ten", "221,276,263,250")
    root.append(following)
    root.append(
        ET.Element(
            "RYUUKYOKU",
            type="yao9",
            ba="0,0",
            sc="221,0,276,0,263,0,250,0",
        )
    )
    cases = convert_log(ET.tostring(root), log_id="synthetic-next-round")
    assert len(cases) == 2
    if shared:
        for case in cases:
            assert case["expected"]["honba_points"] is None
            assert case["expected"]["riichi_stick_points"] is None
            assert {
                item["field"]: item["reason"]
                for item in case["comparison"]["excluded_fields"]
            } == dict.fromkeys(
                (
                    "honba_points",
                    "riichi_stick_points",
                    "winner_gain",
                    "payments_by_seat",
                ),
                "multiple_ron_allocation_unknown",
            )
    else:
        assert [case["expected"]["honba_points"] for case in cases] == [300, 0]
        assert [case["expected"]["riichi_stick_points"] for case in cases] == [
            1000,
            0,
        ]

    following.set("ten", "222,276,263,250")
    with pytest.raises(ConversionError, match="balance") as caught:
        convert_log(ET.tostring(root), log_id="synthetic-next-round-bad")
    assert caught.value.field == "ten"


def test_repeated_shared_deltas_require_the_same_starting_balance() -> None:
    root = ET.parse(FIXTURES / "synthetic-sanma-pao-double-ron.xml").getroot()
    first, second = root.findall("AGARI")
    first.set("sc", "500,480,100,-208,450,-272,0,0")
    second.set("sc", "980,480,-140,-208,210,-272,0,0")

    with pytest.raises(ConversionError, match="starting balances") as caught:
        convert_log(ET.tostring(root), log_id="synthetic-inconsistent-shared")
    assert caught.value.field == "sc"

from typing import TYPE_CHECKING, Literal
from unittest.mock import patch

import pytest
from mahjong.hand_calculating.hand_response import HandResponse
from mahjong.hand_calculating.scores import ScoresResult
from mahjong.hand_calculating.yaku_config import YakuConfig
from mahjong.meld import Meld
from validator.adapter import calculate, normalize_result, prepare_hand
from validator.validation import validate_case

if TYPE_CHECKING:
    from collections.abc import Callable

    from corpus.models import ScoringCase, Tile


@pytest.mark.parametrize("kazoe", [False, True])
def test_normalize_composite_yakuman_and_kazoe(
    load_case: Callable[..., ScoringCase], *, kazoe: bool
) -> None:
    case = load_case()
    hand = prepare_hand(case["input"], case["round"], 4, case["ruleset"])
    config = YakuConfig()
    config.dora.han_closed = 6
    yaku = (
        [config.chinitsu, config.tsumo, config.dora]
        if kazoe
        else [config.daisangen, config.tsuisou]
    )
    raw = HandResponse(
        cost=ScoresResult(
            main=32000 if kazoe else 64000,
            additional=0,
            main_bonus=0,
            additional_bonus=0,
            kyoutaku_bonus=1000,
            total=33000 if kazoe else 65000,
            yaku_level="yakuman" if kazoe else "2x yakuman",
        ),
        han=13 if kazoe else 26,
        fu=40,
        yaku=yaku,
    )
    actual = normalize_result(hand, raw)
    assert actual["title"] == ("kazoe_yakuman" if kazoe else "yakuman")
    assert actual["han"] == (13 if kazoe else None)
    assert actual["yakuman_multiplier"] == (0 if kazoe else 2)


def test_dealer_tsumo_payments_and_honba(
    load_case: Callable[..., ScoringCase],
) -> None:
    case = load_case()
    case["input"].update(winner_seat=0, discarder_seat=None)
    case["input"]["situation"]["tsumo"] = True
    hand = prepare_hand(case["input"], case["round"], 4, case["ruleset"])
    raw = HandResponse(
        cost=ScoresResult(
            main=4000,
            additional=4000,
            main_bonus=200,
            additional_bonus=200,
            kyoutaku_bonus=1000,
            total=13600,
            yaku_level="mangan",
        ),
        han=5,
        fu=30,
        yaku=[YakuConfig().riichi],
    )
    actual = normalize_result(hand, raw)
    assert actual["base_points"] == 12000
    assert actual["honba_points"] == 600
    assert actual["payments_by_seat"] == [0, 4200, 4200, 4200]


def test_inputs_do_not_depend_on_expected_values(
    load_case: Callable[..., ScoringCase],
) -> None:
    case = load_case()
    before = prepare_hand(case["input"], case["round"], 4, case["ruleset"])
    case["expected"].update(han=100, fu=100, yaku=[])
    case["source"]["scoring_values"] = {"untrusted": "anything"}
    after = prepare_hand(case["input"], case["round"], 4, case["ruleset"])
    assert before.tiles == after.tiles
    assert before.config.is_riichi == after.config.is_riichi
    assert before.config.is_ippatsu == after.config.is_ippatsu
    assert before.config.tsumi_number == after.config.tsumi_number


@pytest.mark.parametrize("kind", ["unknown", "duplicate"])
def test_uninterpretable_yaku_result_is_an_error(
    load_case: Callable[..., ScoringCase], kind: str
) -> None:
    case = load_case()
    hand = prepare_hand(case["input"], case["round"], 4, case["ruleset"])
    raw = calculate(hand)
    assert raw.yaku is not None
    raw.yaku.append(
        YakuConfig().open_riichi if kind == "unknown" else raw.yaku[0]
    )
    with patch("validator.validation.calculate", return_value=raw):
        result = validate_case(case)
    assert result["status"] == "error"


@pytest.mark.parametrize(
    "flag",
    ["rinshan", "chankan", "haitei", "houtei", "tenhou", "chiihou", "renhou"],
)
def test_situation_flags_are_forwarded(
    load_case: Callable[..., ScoringCase],
    flag: Literal[
        "rinshan", "chankan", "haitei", "houtei", "tenhou", "chiihou", "renhou"
    ],
) -> None:
    case = load_case()
    case["input"]["situation"][flag] = True
    prepared = prepare_hand(case["input"], case["round"], 4, case["ruleset"])
    assert getattr(prepared.config, f"is_{flag}") is True


@pytest.mark.parametrize(
    ("kind", "tiles", "expected_type", "opened"),
    [
        ("chii", ["4p", "0p", "6p"], Meld.CHI, True),
        ("pon", ["0p", "5p", "5p"], Meld.PON, True),
        ("daiminkan", ["0p", "5p", "5p", "5p"], Meld.KAN, True),
        ("ankan", ["0p", "5p", "5p", "5p"], Meld.KAN, False),
        ("kakan", ["0p", "5p", "5p", "5p"], Meld.SHOUMINKAN, True),
    ],
)
def test_meld_tiles_and_call_metadata(
    load_case: Callable[..., ScoringCase],
    kind: Literal["chii", "pon", "daiminkan", "ankan", "kakan"],
    tiles: list[Tile],
    expected_type: str,
    *,
    opened: bool,
) -> None:
    case = load_case()
    hand = case["input"]
    hand["concealed_tiles"] = [
        "1m",
        "1m",
        "2m",
        "3m",
        "4m",
        "2s",
        "3s",
        "4s",
        "6s",
        "7s",
    ]
    hand["situation"]["riichi"] = "none"
    hand["situation"]["ippatsu"] = False
    hand["melds"] = [
        {
            "type": kind,
            "tiles": tiles,
            "called_tile_index": 1 if opened else None,
            "from_seat": 3 if opened else None,
        }
    ]
    prepared = prepare_hand(hand, case["round"], 4, case["ruleset"])
    meld = prepared.melds[0]
    assert meld.type == expected_type
    assert meld.opened is opened
    assert meld.called_tile == (meld.tiles[1] if opened else None)
    assert meld.from_who == (3 if opened else None)
    assert meld.who == 2
    assert set(meld.tiles).issubset(prepared.tiles)
    assert len(set(prepared.tiles)) == len(prepared.tiles)
    assert 52 in meld.tiles  # red 5p

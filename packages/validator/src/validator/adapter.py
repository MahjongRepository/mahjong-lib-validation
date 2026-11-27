from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING

from mahjong.constants import EAST, NORTH, SOUTH, WEST
from mahjong.hand_calculating.hand import HandCalculator
from mahjong.hand_calculating.hand_config import HandConfig, OptionalRules
from mahjong.meld import Meld
lazy from mahjong.agari import Agari
lazy from mahjong.hand_calculating.hand_response import HandResponse
lazy from mahjong.hand_calculating.scores import ScoresResult
lazy from mahjong.shanten import Shanten

from validator.yaku import YAKU_IDS

if TYPE_CHECKING:
    from collections.abc import Callable

    from corpus.models import (
        AgariCase,
        Expected,
        Round,
        ScoringCase,
        ScoringInput,
        ShantenCase,
        Tile,
        Title,
        Yaku,
    )

WINDS = {"east": EAST, "south": SOUTH, "west": WEST, "north": NORTH}
FIVE = 5
SANMA_PLAYERS = 3
YAKUMAN_HAN = 13
MELD_KINDS = {
    "chii": Meld.CHI,
    "pon": Meld.PON,
    "daiminkan": Meld.KAN,
    "ankan": Meld.KAN,
    "kakan": Meld.SHOUMINKAN,
}
_MAJSOUL_TITLES: dict[str, Title] = {
    "": "below_mangan",
    "mangan": "mangan",
    "haneman": "haneman",
    "baiman": "baiman",
    "sanbaiman": "sanbaiman",
    "yakuman": "yakuman",
    "2x yakuman": "double_yakuman",
    "3x yakuman": "triple_yakuman",
    "4x yakuman": "quadruple_yakuman",
    "5x yakuman": "quintuple_yakuman",
    "6x yakuman": "sextuple_yakuman",
}

_TENHOU_TITLES: dict[str, Title] = {
    label: "yakuman" if label.endswith("x yakuman") else title
    for label, title in _MAJSOUL_TITLES.items()
}


class UnsupportedInputError(ValueError):
    pass


class MissingInputError(ValueError):
    pass


@dataclass
class PreparedHand:
    tiles: list[int]
    win_tile: int
    melds: list[Meld]
    dora: list[int]
    ura: list[int]
    config: HandConfig
    player_count: int
    winner: int
    dealer: int
    discarder: int | None
    ruleset: str


def _tile_index(tile: str) -> int:
    number = int(tile[0])
    return "mpsz".index(tile[1]) * 9 + (number or FIVE) - 1


def _indicator_to_136(tile: str) -> int:
    return _tile_index(tile) * 4


def _tile_counts(tiles: list[Tile]) -> list[int]:
    counts = [0] * 34
    for tile in tiles:
        counts[_tile_index(tile)] += 1
    return counts


def prepare_agari_call(case: AgariCase) -> Callable[[], bool]:
    hand = case["input"]
    counts = _tile_counts(hand["concealed_tiles"])
    melds = [
        [_tile_index(tile) for tile in meld["tiles"]] for meld in hand["melds"]
    ]
    for meld in melds:
        for index in meld:
            counts[index] += 1
    return partial(Agari.is_agari, counts, melds or None)


def prepare_shanten_call(case: ShantenCase) -> Callable[[], int]:
    counts = _tile_counts(case["input"]["concealed_tiles"])
    return partial(
        Shanten.calculate_shanten,
        counts,
        is_three_player=case["player_count"] == SANMA_PLAYERS,
    )


def _ranked_rules(
    *, is_three_player: bool, double_yakuman: bool, renhou_as_yakuman: bool
) -> OptionalRules:
    return OptionalRules(
        has_open_tanyao=True,
        has_aka_dora=True,
        has_double_yakuman=double_yakuman,
        kazoe_limit=HandConfig.KAZOE_LIMITED,
        kiriage=False,
        fu_for_open_pinfu=True,
        fu_for_pinfu_tsumo=False,
        renhou_as_yakuman=renhou_as_yakuman,
        has_daisharin=False,
        has_daisharin_other_suits=False,
        has_sashikomi_yakuman=False,
        limit_to_sextuple_yakuman=True,
        paarenchan_needs_yaku=True,
        has_daichisei=False,
        is_three_player=is_three_player,
    )


def _tenhou_ranked_rules(*, is_three_player: bool) -> OptionalRules:
    return _ranked_rules(
        is_three_player=is_three_player,
        double_yakuman=False,
        renhou_as_yakuman=False,
    )


def _majsoul_ranked_rules(*, is_three_player: bool) -> OptionalRules:
    return _ranked_rules(
        is_three_player=is_three_player,
        double_yakuman=True,
        renhou_as_yakuman=True,
    )


def prepare_hand(
    hand: ScoringInput, round_: Round, player_count: int, ruleset: str
) -> PreparedHand:
    if ruleset not in {"tenhou-ranked-match", "majsoul-ranked-match"}:
        raise UnsupportedInputError(ruleset)
    unknown = [
        key for key, value in hand["situation"].items() if value is None
    ]
    if unknown:
        raise MissingInputError(", ".join(unknown))

    used: set[int] = set()

    def allocate(tile: str) -> int:
        number = int(tile[0])
        base = _tile_index(tile) * 4
        copies = (
            [0]
            if number == 0
            else range(1 if number == FIVE and tile[1] != "z" else 0, 4)
        )
        result = next(
            (base + copy for copy in copies if base + copy not in used), None
        )
        if result is None:
            msg = f"cannot allocate {tile} under one-red-five-per-suit rules"
            raise ValueError(msg)
        used.add(result)
        return result

    tiles = [allocate(tile) for tile in hand["concealed_tiles"]]
    win_tile = allocate(hand["winning_tile"])
    tiles.append(win_tile)
    melds = []
    for value in hand["melds"]:
        meld_tiles = [allocate(tile) for tile in value["tiles"]]
        tiles.extend(meld_tiles)
        called = value["called_tile_index"]
        melds.append(
            Meld(
                meld_type=MELD_KINDS[value["type"]],
                tiles=meld_tiles,
                opened=value["type"] != "ankan",
                called_tile=None if called is None else meld_tiles[called],
                who=hand["winner_seat"],
                from_who=value["from_seat"],
            )
        )
    situation = hand["situation"]
    ranked_rules = (
        _majsoul_ranked_rules
        if ruleset == "majsoul-ranked-match"
        else _tenhou_ranked_rules
    )
    config = HandConfig(
        is_tsumo=situation["tsumo"],
        is_riichi=situation["riichi"] == "riichi",
        is_daburu_riichi=situation["riichi"] == "double_riichi",
        is_ippatsu=bool(situation["ippatsu"]),
        is_rinshan=bool(situation["rinshan"]),
        is_chankan=bool(situation["chankan"]),
        is_haitei=bool(situation["haitei"]),
        is_houtei=bool(situation["houtei"]),
        is_tenhou=bool(situation["tenhou"]),
        is_chiihou=bool(situation["chiihou"]),
        is_renhou=bool(situation["renhou"]),
        is_nagashi_mangan=False,
        is_open_riichi=False,
        paarenchan=0,
        player_wind=EAST
        + (hand["winner_seat"] - round_["dealer_seat"]) % player_count,
        round_wind=WINDS[round_["wind"]],
        tsumi_number=round_["honba"],
        kyoutaku_number=round_["riichi_sticks"],
        num_nuki_dora=hand["nuki_count"],
        options=ranked_rules(is_three_player=player_count == SANMA_PLAYERS),
    )

    return PreparedHand(
        tiles,
        win_tile,
        melds,
        [_indicator_to_136(tile) for tile in hand["dora_indicators"]],
        [_indicator_to_136(tile) for tile in hand["ura_dora_indicators"]],
        config,
        player_count,
        hand["winner_seat"],
        round_["dealer_seat"],
        hand["discarder_seat"],
        ruleset,
    )


def prepare_scoring_case(case: ScoringCase) -> PreparedHand:
    return prepare_hand(
        case["input"], case["round"], case["player_count"], case["ruleset"]
    )


def prepare_calculation(hand: PreparedHand) -> partial[HandResponse]:
    return partial(
        HandCalculator.estimate_hand_value,
        hand.tiles,
        hand.win_tile,
        melds=hand.melds,
        dora_indicators=hand.dora,
        ura_dora_indicators=hand.ura,
        config=hand.config,
    )


def calculate(hand: PreparedHand) -> HandResponse:
    return prepare_calculation(hand)()


def _payments(hand: PreparedHand, cost: ScoresResult) -> list[int]:
    payments = [0] * hand.player_count
    for seat in range(hand.player_count):
        if seat == hand.winner:
            continue
        if hand.config.is_tsumo:
            main = hand.config.is_dealer or seat == hand.dealer
            payments[seat] = (
                cost["main"] + cost["main_bonus"]
                if main
                else cost["additional"] + cost["additional_bonus"]
            )
        elif seat == hand.discarder:
            payments[seat] = cost["main"] + cost["main_bonus"]
    return payments


def _scoring_title(ruleset: str, level: str, *, is_kazoe: bool) -> Title:
    if is_kazoe:
        return "kazoe_yakuman"
    if ruleset == "tenhou-ranked-match":
        return _TENHOU_TITLES[level]
    return _MAJSOUL_TITLES[level]


def normalize_result(hand: PreparedHand, raw: HandResponse) -> Expected:
    if raw.error:
        raise ValueError(raw.error)
    if raw.cost is None:
        msg = "library result is missing cost"
        raise ValueError(msg)
    if raw.han is None:
        msg = "library result is missing han"
        raise ValueError(msg)
    if raw.fu is None:
        msg = "library result is missing fu"
        raise ValueError(msg)
    if raw.yaku is None:
        msg = "library result is missing yaku"
        raise ValueError(msg)

    yaku: list[Yaku] = []
    seen: set[int] = set()
    for value in raw.yaku:
        if value.yaku_id in seen:
            msg = f"duplicate library yaku: {value.yaku_id}"
            raise ValueError(msg)
        seen.add(value.yaku_id)
        key = YAKU_IDS.get(value.yaku_id)
        if key is None:
            msg = f"unknown library yaku: {value.yaku_id}"
            raise ValueError(msg)
        han = value.han_open if raw.is_open_hand else value.han_closed
        if han <= 0:
            msg = f"yaku han must be positive: {key}"
            raise ValueError(msg)
        yaku.append(
            {
                "id": key,
                "han": None if value.is_yakuman else han,
                "yakuman_multiplier": han // YAKUMAN_HAN
                if value.is_yakuman
                else 0,
            }
        )

    multiplier = sum(item["yakuman_multiplier"] for item in yaku)
    cost = raw.cost
    title = _scoring_title(
        hand.ruleset,
        cost["yaku_level"],
        is_kazoe=raw.han >= YAKUMAN_HAN and not multiplier,
    )
    additional_count = hand.player_count - 2 if hand.config.is_tsumo else 0
    base_points = cost["main"] + additional_count * cost["additional"]
    honba = cost["main_bonus"] + additional_count * cost["additional_bonus"]
    return {
        "title": title,
        "yaku": yaku,
        "han": None if multiplier else raw.han,
        "fu": raw.fu,
        "yakuman_multiplier": multiplier,
        "base_points": base_points,
        "honba_points": honba,
        "riichi_stick_points": cost["kyoutaku_bonus"],
        "winner_gain": cost["total"],
        "payments_by_seat": _payments(hand, cost),
        "event_score_deltas": None,
    }

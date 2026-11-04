from dataclasses import dataclass
from typing import TYPE_CHECKING

from mahjong.constants import EAST, NORTH, SOUTH, WEST
from mahjong.hand_calculating.hand import HandCalculator
from mahjong.hand_calculating.hand_config import HandConfig, OptionalRules
from mahjong.meld import Meld
lazy from mahjong.hand_calculating.hand_response import HandResponse
lazy from mahjong.hand_calculating.scores import ScoresResult

from validator.yaku import YAKU_IDS

if TYPE_CHECKING:
    from corpus.models import Expected, Round, ScoringInput, Title, Yaku

WINDS = {"east": EAST, "south": SOUTH, "west": WEST, "north": NORTH}
FIVE = 5
SANMA_PLAYERS = 3
YAKUMAN_HAN = 13


class UnsupportedInputError(ValueError):
    pass


class MissingInputError(ValueError):
    pass


@dataclass
class PreparedHand:
    tiles: list[int]
    win_tile: int
    dora: list[int]
    ura: list[int]
    config: HandConfig
    player_count: int
    winner: int
    dealer: int
    discarder: int | None
    melds: list[Meld]


def prepare_hand(
    hand: ScoringInput, round_: Round, player_count: int, ruleset: str
) -> PreparedHand:
    if ruleset != "tenhou-ranked-match":
        raise UnsupportedInputError(ruleset)
    unknown = [
        key for key, value in hand["situation"].items() if value is None
    ]
    if unknown:
        raise MissingInputError(", ".join(unknown))
    used: set[int] = set()

    def allocate(tile: str) -> int:
        number = int(tile[0])
        base = ("mpsz".index(tile[1]) * 9 + (number or FIVE) - 1) * 4
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
    kinds = {
        "chii": Meld.CHI,
        "pon": Meld.PON,
        "daiminkan": Meld.KAN,
        "ankan": Meld.KAN,
        "kakan": Meld.SHOUMINKAN,
    }
    for value in hand["melds"]:
        meld_tiles = [allocate(tile) for tile in value["tiles"]]
        tiles.extend(meld_tiles)
        called = value["called_tile_index"]
        melds.append(
            Meld(
                meld_type=kinds[value["type"]],
                tiles=meld_tiles,
                opened=value["type"] != "ankan",
                called_tile=None if called is None else meld_tiles[called],
                who=hand["winner_seat"],
                from_who=value["from_seat"],
            )
        )
    situation = hand["situation"]
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
        options=OptionalRules(
            has_open_tanyao=True,
            has_aka_dora=True,
            has_double_yakuman=False,
            kazoe_limit=HandConfig.KAZOE_LIMITED,
            kiriage=False,
            fu_for_open_pinfu=True,
            fu_for_pinfu_tsumo=False,
            renhou_as_yakuman=False,
            has_daisharin=False,
            has_daisharin_other_suits=False,
            has_sashikomi_yakuman=False,
            limit_to_sextuple_yakuman=True,
            paarenchan_needs_yaku=True,
            has_daichisei=False,
            is_three_player=player_count == SANMA_PLAYERS,
        ),
    )

    def indicator(tile: str) -> int:
        number = int(tile[0])
        return ("mpsz".index(tile[1]) * 9 + (number or FIVE) - 1) * 4

    return PreparedHand(
        tiles,
        win_tile,
        [indicator(tile) for tile in hand["dora_indicators"]],
        [indicator(tile) for tile in hand["ura_dora_indicators"]],
        config,
        player_count,
        hand["winner_seat"],
        round_["dealer_seat"],
        hand["discarder_seat"],
        melds,
    )


def calculate(hand: PreparedHand) -> HandResponse:
    return HandCalculator.estimate_hand_value(
        hand.tiles,
        hand.win_tile,
        melds=hand.melds,
        dora_indicators=hand.dora,
        ura_dora_indicators=hand.ura,
        config=hand.config,
    )


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


def normalize_result(hand: PreparedHand, raw: HandResponse) -> Expected:
    if raw.error:
        raise ValueError(raw.error)
    if (
        raw.cost is None
        or raw.han is None
        or raw.fu is None
        or raw.yaku is None
    ):
        msg = "incomplete library result"
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
        if han is None or han <= 0:
            msg = f"invalid yaku han: {key}"
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
    titles: dict[str, Title] = {
        "": "below_mangan",
        "mangan": "mangan",
        "haneman": "haneman",
        "baiman": "baiman",
        "sanbaiman": "sanbaiman",
        "yakuman": "yakuman",
        "2x yakuman": "yakuman",
        "3x yakuman": "yakuman",
        "4x yakuman": "yakuman",
        "5x yakuman": "yakuman",
        "6x yakuman": "yakuman",
    }
    title = (
        "kazoe_yakuman"
        if raw.han >= YAKUMAN_HAN and not multiplier
        else titles[cost["yaku_level"]]
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

"""Validate scoring records without calculating expected scores."""

from collections import Counter
from typing import cast

from corpus._validation import minimum, validate_json, validate_type
from corpus.errors import CorpusError
from corpus.models import Expected, Meld, ScoringCase, Yaku

MAX_MELDS = 4
MAX_TILE_COPIES = 4


def parse_case(value: object) -> ScoringCase:
    validate_type(value, ScoringCase, "")
    case = cast("ScoringCase", value)
    _tiles(case)
    _seats(case)
    _bounds(case)
    _situation(case)
    _expected(case)
    validate_json(case["source"]["scoring_values"], "source.scoring_values")
    return case


def _situation(case: ScoringCase) -> None:
    situation = case["input"]["situation"]
    reasons = case["situation_provenance"]["unknown_fields"]
    for name, reason in reasons.items():
        field = "situation_provenance.unknown_fields." + name
        if name not in situation:
            raise CorpusError(field, "unknown situation field")
        if situation.get(name) is not None:
            raise CorpusError(
                field, "a known value must not have an unknown reason"
            )
        if not reason.strip():
            raise CorpusError(field, "reason must not be empty")
    for name, value in situation.items():
        if value is None and name not in reasons:
            raise CorpusError(
                "situation_provenance.unknown_fields." + name,
                "unknown value needs a reason",
            )


def _bounds(case: ScoringCase) -> None:
    minimum(case["win_number"], 1, "win_number")
    minimum(case["round"]["number"], 1, "round.number")
    for name in ("honba", "riichi_sticks"):
        minimum(case["round"][name], 0, "round." + name)
    for name in ("event_index", "winner_index"):
        minimum(case["source"][name], 0, "source." + name)
    minimum(case["input"]["nuki_count"], 0, "input.nuki_count")
    for index, event in enumerate(
        case["situation_provenance"]["event_indices"]
    ):
        minimum(event, 0, f"situation_provenance.event_indices[{index}]")
    for name in (
        "han",
        "fu",
        "yakuman_multiplier",
        "base_points",
        "honba_points",
        "riichi_stick_points",
        "winner_gain",
    ):
        minimum(case["expected"][name], 0, "expected." + name)
    for index, payment in enumerate(
        case["expected"]["payments_by_seat"] or []
    ):
        minimum(payment, 0, f"expected.payments_by_seat[{index}]")


def _exclusions(case: ScoringCase) -> None:
    expected = case["expected"]
    excluded = set()
    for index, exclusion in enumerate(case["comparison"]["excluded_fields"]):
        field = f"comparison.excluded_fields[{index}]"
        if exclusion["field"] not in expected:
            raise CorpusError(field + ".field", "unknown expected field")
        if not exclusion["reason"].strip():
            raise CorpusError(field + ".reason", "reason must not be empty")
        excluded.add(exclusion["field"])
    for field, value in expected.items():
        if value is None and field not in excluded:
            if field == "han" and (expected["yakuman_multiplier"] or 0) > 0:
                continue
            raise CorpusError(
                "expected." + field, "missing value needs an exclusion"
            )


def _expected(case: ScoringCase) -> None:
    _exclusions(case)
    expected = case["expected"]
    _yaku(expected)
    _points(expected)
    for name in ("payments_by_seat", "event_score_deltas"):
        values = expected[name]
        if values is not None and len(values) != case["player_count"]:
            raise CorpusError(
                "expected." + name, "one entry per seat is required"
            )
    payments = expected["payments_by_seat"]
    winner = case["input"]["winner_seat"]
    if payments is not None and payments[winner] != 0:
        error_field = f"expected.payments_by_seat[{winner}]"
        raise CorpusError(
            error_field,
            "winner must not pay their own win",
        )


def _yaku_ids(yaku: list[Yaku]) -> None:
    seen: set[str] = set()
    for index, item in enumerate(yaku):
        if item["id"] in seen:
            error_field = f"expected.yaku[{index}].id"
            raise CorpusError(error_field, "duplicate yaku ID")
        seen.add(item["id"])


def _yaku(expected: Expected) -> None:
    if expected["yaku"] is None:
        return
    _yaku_ids(expected["yaku"])
    for index, yaku in enumerate(expected["yaku"]):
        field = f"expected.yaku[{index}]"
        multiplier = yaku["yakuman_multiplier"]
        han = yaku["han"]
        if multiplier < 0:
            raise CorpusError(
                field + ".yakuman_multiplier", "must not be negative"
            )
        if multiplier > 0:
            if han is not None:
                raise CorpusError(field + ".han", "yakuman has no han value")
        elif han is None or han <= 0:
            raise CorpusError(
                field + ".han", "regular yaku needs positive han"
            )
    total = sum(yaku["yakuman_multiplier"] for yaku in expected["yaku"])
    if (
        expected["yakuman_multiplier"] is not None
        and expected["yakuman_multiplier"] != total
    ):
        error_field = "expected.yakuman_multiplier"
        raise CorpusError(
            error_field,
            "does not equal the yaku multiplier sum",
        )
    if total == 0 and expected["han"] is not None:
        han = sum(yaku["han"] or 0 for yaku in expected["yaku"])
        if expected["han"] != han:
            error_field = "expected.han"
            raise CorpusError(error_field, "does not equal the yaku han sum")


def _points(expected: Expected) -> None:
    base = expected["base_points"]
    honba = expected["honba_points"]
    sticks = expected["riichi_stick_points"]
    gain = expected["winner_gain"]
    if base is not None and honba is not None:
        if (
            sticks is not None
            and gain is not None
            and gain != base + honba + sticks
        ):
            error_field = "expected.winner_gain"
            raise CorpusError(error_field, "does not equal point components")
        payments = expected["payments_by_seat"]
        if payments is not None and sum(payments) != base + honba:
            error_field = "expected.payments_by_seat"
            raise CorpusError(error_field, "does not equal base + honba")


def _seats(case: ScoringCase) -> None:
    hand = case["input"]
    seats = {
        "round.dealer_seat": case["round"]["dealer_seat"],
        "input.winner_seat": hand["winner_seat"],
        "input.discarder_seat": hand["discarder_seat"],
    }
    for index, meld in enumerate(hand["melds"]):
        seats[f"input.melds[{index}].from_seat"] = meld["from_seat"]
        if meld["from_seat"] == hand["winner_seat"]:
            error_field = f"input.melds[{index}].from_seat"
            raise CorpusError(
                error_field,
                "open meld needs another player's seat",
            )
    for field, seat in seats.items():
        if seat is not None and not 0 <= seat < case["player_count"]:
            raise CorpusError(field, "seat outside player count")
    discarder = hand["discarder_seat"]
    if hand["situation"]["tsumo"]:
        if discarder is not None:
            error_field = "input.discarder_seat"
            raise CorpusError(error_field, "tsumo has no discarder")
    elif discarder is None or discarder == hand["winner_seat"]:
        error_field = "input.discarder_seat"
        raise CorpusError(error_field, "ron needs another player's seat")


def _kind(tile: str) -> str:
    return tile.replace("0", "5")


def _meld(meld: Meld, field: str) -> None:
    _meld_origin(meld, field)
    tiles = meld["tiles"]
    size = 3 if meld["type"] in ("chii", "pon") else 4
    if len(tiles) != size:
        raise CorpusError(field + ".tiles", f"expected {size} tiles")
    called = meld["called_tile_index"]
    if called is not None and not 0 <= called < size:
        raise CorpusError(field + ".called_tile_index", "index outside tiles")
    kinds = [_kind(tile) for tile in tiles]
    if meld["type"] == "chii":
        ranks = sorted(int(tile[0]) for tile in kinds)
        if (
            len({tile[1] for tile in kinds}) != 1
            or kinds[0][1] == "z"
            or ranks != list(range(ranks[0], ranks[0] + 3))
        ):
            raise CorpusError(
                field + ".tiles", "chii needs three consecutive tiles"
            )
    elif len(set(kinds)) != 1:
        raise CorpusError(
            field + ".tiles", "pon/kan needs matching tile kinds"
        )


def _meld_origin(meld: Meld, field: str) -> None:
    for name in ("called_tile_index", "from_seat"):
        value = meld[name]
        if meld["type"] == "ankan":
            if value is not None:
                raise CorpusError(
                    field + "." + name,
                    "ankan has no called tile or source seat",
                )
        elif value is None:
            raise CorpusError(
                field + "." + name,
                "open meld needs called tile and source seat",
            )


def _tiles(case: ScoringCase) -> None:
    hand = case["input"]
    if hand["nuki_count"] > MAX_TILE_COPIES:
        error_field = "input.nuki_count"
        raise CorpusError(
            error_field, "at most four extracted norths are allowed"
        )
    if len(hand["melds"]) > MAX_MELDS:
        error_field = "input.melds"
        raise CorpusError(error_field, "at most four melds are allowed")
    if len(hand["concealed_tiles"]) != 13 - 3 * len(hand["melds"]):
        error_field = "input.concealed_tiles"
        raise CorpusError(error_field, "wrong count excluding win/melds")
    for index, meld in enumerate(hand["melds"]):
        _meld(meld, f"input.melds[{index}]")
    tiles = [*hand["concealed_tiles"], hand["winning_tile"]]
    for meld in hand["melds"]:
        tiles.extend(meld["tiles"])
    counts = Counter(_kind(tile) for tile in tiles)
    counts["4z"] += hand["nuki_count"]
    if any(count > MAX_TILE_COPIES for count in counts.values()):
        error_field = "input"
        raise CorpusError(error_field, "a tile kind has more than four copies")

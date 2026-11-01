"""Validate scoring records without calculating expected scores."""

from collections import Counter
from functools import cache
from math import isfinite
from re import fullmatch
from types import UnionType
from typing import (
    Literal,
    NoReturn,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)

from corpus.errors import CorpusError
from corpus.models import Expected, Meld, ScoringCase

MAX_MELDS = 4
MAX_TILE_COPIES = 4


def parse_case(value: object) -> ScoringCase:
    _shape(value, ScoringCase, "")
    case = cast("ScoringCase", value)
    _tiles(case)
    _seats(case)
    _bounds(case)
    _expected(case)
    _json_value(case["source"]["scoring_values"], "source.scoring_values")
    return case


def _json_value(value: object, field: str) -> None:
    if value is None or type(value) in (str, int, bool):
        return
    if isinstance(value, float) and isfinite(value):
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _json_value(child, f"{field}[{index}]")
        return
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                _fail(field, "JSON object keys must be strings")
            _json_value(child, f"{field}.{key}")
        return
    _fail(field, "expected finite JSON data")


def _minimum(value: int | None, minimum: int, field: str) -> None:
    if value is not None and value < minimum:
        _fail(field, f"expected at least {minimum}")


def _bounds(case: ScoringCase) -> None:
    _minimum(case["win_number"], 1, "win_number")
    _minimum(case["round"]["number"], 1, "round.number")
    for name in ("honba", "riichi_sticks"):
        _minimum(case["round"][name], 0, "round." + name)
    for name in ("event_index", "winner_index"):
        _minimum(case["source"][name], 0, "source." + name)
    _minimum(case["input"]["nuki_count"], 0, "input.nuki_count")
    for index, event in enumerate(
        case["situation_provenance"]["event_indices"]
    ):
        _minimum(event, 0, f"situation_provenance.event_indices[{index}]")
    for name in (
        "han",
        "fu",
        "yakuman_multiplier",
        "base_points",
        "honba_points",
        "riichi_stick_points",
        "winner_gain",
    ):
        _minimum(case["expected"][name], 0, "expected." + name)
    for index, payment in enumerate(
        case["expected"]["payments_by_seat"] or []
    ):
        _minimum(payment, 0, f"expected.payments_by_seat[{index}]")


def _exclusions(case: ScoringCase) -> None:
    expected = case["expected"]
    excluded = set()
    for index, exclusion in enumerate(case["comparison"]["excluded_fields"]):
        field = f"comparison.excluded_fields[{index}]"
        if exclusion["field"] not in expected:
            _fail(field + ".field", "unknown expected field")
        if not exclusion["reason"].strip():
            _fail(field + ".reason", "reason must not be empty")
        excluded.add(exclusion["field"])
    for field, value in expected.items():
        if value is None and field not in excluded:
            if field == "han" and expected["yakuman_multiplier"] > 0:
                continue
            _fail("expected." + field, "missing value needs an exclusion")


def _expected(case: ScoringCase) -> None:
    _exclusions(case)
    expected = case["expected"]
    _yaku(expected)
    if expected["han"] is not None and expected["yakuman_multiplier"] == 0:
        total = sum(yaku["han"] or 0 for yaku in expected["yaku"])
        if expected["han"] != total:
            _fail("expected.han", "does not equal the yaku han sum")
    _points(expected)
    for name in ("payments_by_seat", "event_score_deltas"):
        values = expected[name]
        if values is not None and len(values) != case["player_count"]:
            _fail("expected." + name, "one entry per seat is required")


def _yaku(expected: Expected) -> None:
    for index, yaku in enumerate(expected["yaku"]):
        field = f"expected.yaku[{index}]"
        multiplier = yaku["yakuman_multiplier"]
        han = yaku["han"]
        if multiplier < 0:
            _fail(field + ".yakuman_multiplier", "must not be negative")
        if multiplier > 0:
            if han is not None:
                _fail(field + ".han", "yakuman has no han value")
        elif han is None or han <= 0:
            _fail(field + ".han", "regular yaku needs positive han")
    total = sum(yaku["yakuman_multiplier"] for yaku in expected["yaku"])
    if expected["yakuman_multiplier"] != total:
        _fail(
            "expected.yakuman_multiplier",
            "does not equal the yaku multiplier sum",
        )


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
            _fail("expected.winner_gain", "does not equal point components")
        payments = expected["payments_by_seat"]
        if payments is not None and sum(payments) != base + honba:
            _fail("expected.payments_by_seat", "does not equal base + honba")


def _seats(case: ScoringCase) -> None:
    hand = case["input"]
    seats = {
        "round.dealer_seat": case["round"]["dealer_seat"],
        "input.winner_seat": hand["winner_seat"],
        "input.discarder_seat": hand["discarder_seat"],
    }
    for index, meld in enumerate(hand["melds"]):
        seats[f"input.melds[{index}].from_seat"] = meld["from_seat"]
    for field, seat in seats.items():
        if seat is not None and not 0 <= seat < case["player_count"]:
            _fail(field, "seat outside player count")
    discarder = hand["discarder_seat"]
    if hand["situation"]["tsumo"]:
        if discarder is not None:
            _fail("input.discarder_seat", "tsumo has no discarder")
    elif discarder is None or discarder == hand["winner_seat"]:
        _fail("input.discarder_seat", "ron needs another player's seat")


def _tile(value: str, field: str) -> None:
    if not fullmatch(r"(?:[0-9][mps]|[1-7]z)", value):
        _fail(field, "expected an mpsz tile (red five is 0m/0p/0s)")


def _kind(tile: str) -> str:
    return tile.replace("0", "5")


def _meld(meld: Meld, field: str) -> None:
    tiles = meld["tiles"]
    size = 3 if meld["type"] in ("chii", "pon") else 4
    if len(tiles) != size:
        _fail(field + ".tiles", f"expected {size} tiles")
    called = meld["called_tile_index"]
    if called is not None and not 0 <= called < size:
        _fail(field + ".called_tile_index", "index outside tiles")
    kinds = [_kind(tile) for tile in tiles]
    if meld["type"] == "chii":
        ranks = sorted(int(tile[0]) for tile in kinds)
        if (
            len({tile[1] for tile in kinds}) != 1
            or kinds[0][1] == "z"
            or ranks != list(range(ranks[0], ranks[0] + 3))
        ):
            _fail(field + ".tiles", "chii needs three consecutive tiles")
    elif len(set(kinds)) != 1:
        _fail(field + ".tiles", "pon/kan needs matching tile kinds")


def _tiles(case: ScoringCase) -> None:
    hand = case["input"]
    if len(hand["melds"]) > MAX_MELDS:
        _fail("input.melds", "at most four melds are allowed")
    if len(hand["concealed_tiles"]) != 13 - 3 * len(hand["melds"]):
        _fail("input.concealed_tiles", "wrong count excluding win/melds")
    _tile(hand["winning_tile"], "input.winning_tile")
    for name in ("concealed_tiles", "dora_indicators", "ura_dora_indicators"):
        for index, value in enumerate(hand[name]):
            _tile(value, f"input.{name}[{index}]")
    for index, meld in enumerate(hand["melds"]):
        for position, value in enumerate(meld["tiles"]):
            _tile(value, f"input.melds[{index}].tiles[{position}]")
        _meld(meld, f"input.melds[{index}]")
    tiles = [*hand["concealed_tiles"], hand["winning_tile"]]
    for meld in hand["melds"]:
        tiles.extend(meld["tiles"])
    if any(
        count > MAX_TILE_COPIES
        for count in Counter(_kind(tile) for tile in tiles).values()
    ):
        _fail("input", "a tile kind has more than four copies")


@cache
def _fields(model: type) -> dict[str, object]:
    return get_type_hints(model)


def _shape(value: object, annotation: object, field: str) -> None:
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is Literal:
        if not any(type(value) is type(v) and value == v for v in args):
            _fail(field, f"expected one of {args}")
    elif origin in (Union, UnionType):
        _union(value, args, field)
    elif origin in (list, dict):
        _container(value, origin, args, field)
    elif isinstance(annotation, type) and hasattr(
        annotation, "__required_keys__"
    ):
        _record(value, annotation, field)
    elif annotation is not object and type(value) is not annotation:
        _fail(field, f"expected {annotation}")


def _container(
    value: object, origin: type, args: tuple[object, ...], field: str
) -> None:
    if origin is list:
        if not isinstance(value, list):
            _fail(field, "expected array")
        for index, item in enumerate(value):
            _shape(item, args[0], f"{field}[{index}]")
    else:
        if not isinstance(value, dict):
            _fail(field, "expected object")
        for key, item in value.items():
            _shape(key, args[0], field)
            _shape(item, args[1], f"{field}.{key}")


def _union(value: object, choices: tuple[object, ...], field: str) -> None:
    non_null = tuple(item for item in choices if item is not type(None))
    if type(None) in choices and len(non_null) == 1:
        if value is None:
            return
        _shape(value, non_null[0], field)
        return
    for choice in choices:
        try:
            _shape(value, choice, field)
        except CorpusError:
            continue
        return
    _fail(field, "value does not match allowed types")


def _record(value: object, model: type, field: str) -> None:
    if not isinstance(value, dict):
        _fail(field, "expected object")
    fields = _fields(model)
    for name, annotation in fields.items():
        child = f"{field}.{name}" if field else name
        if name not in value:
            _fail(child, "required field is missing")
        _shape(value[name], annotation, child)
    for name in value:
        if name not in fields:
            child = f"{field}.{name}" if field else str(name)
            _fail(child, "unknown field")


def _fail(field: str, message: str) -> NoReturn:
    raise CorpusError(field, message)

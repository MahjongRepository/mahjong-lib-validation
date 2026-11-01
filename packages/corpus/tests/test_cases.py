import json
from pathlib import Path
from typing import Any

import pytest
from corpus import CorpusError, parse_case


def test_parse_scoring_example(example: dict[str, Any]) -> None:
    case = parse_case(example)

    assert case["schema_version"] == "v1"
    assert case["input"]["winning_tile"] == "8s"
    assert len(case["input"]["concealed_tiles"]) == 13
    assert case["input"]["situation"]["ippatsu"] is True
    assert case["input"]["situation"]["renhou"] is False
    assert case["expected"]["fu"] == 40
    assert case["expected"]["base_points"] == 2600
    assert case["expected"]["winner_gain"] == 3600


def test_title_below_mangan(example: dict[str, Any]) -> None:
    example["expected"]["title"] = "below_mangan"
    assert parse_case(example)["expected"]["title"] == "below_mangan"


@pytest.mark.parametrize("title", ["mangan", "haneman", "baiman", "sanbaiman"])
def test_title_is_preserved_without_recalculating_points(
    example: dict[str, Any], title: str
) -> None:
    example["expected"]["title"] = title
    assert parse_case(example)["expected"]["title"] == title


def test_compound_yakuman_title_and_multiplier(
    example: dict[str, Any],
) -> None:
    example["expected"].update(
        {
            "title": "yakuman",
            "han": None,
            "yakuman_multiplier": 2,
            "yaku": [
                {"id": "daisangen", "han": None, "yakuman_multiplier": 1},
                {"id": "tsuuiisou", "han": None, "yakuman_multiplier": 1},
            ],
            "base_points": 64000,
            "winner_gain": 65000,
            "payments_by_seat": [64000, 0, 0, 0],
            "event_score_deltas": [-64000, 0, 65000, 0],
        }
    )
    case = parse_case(example)
    assert case["expected"]["title"] == "yakuman"
    assert case["expected"]["yakuman_multiplier"] == 2


def test_counted_yakuman_has_no_true_yakuman_multiplier(
    example: dict[str, Any],
) -> None:
    example["expected"].update(
        {
            "title": "kazoe_yakuman",
            "han": 13,
            "yaku": [{"id": "dora", "han": 13, "yakuman_multiplier": 0}],
            "base_points": 32000,
            "winner_gain": 33000,
            "payments_by_seat": [32000, 0, 0, 0],
            "event_score_deltas": [-32000, 0, 33000, 0],
        }
    )
    case = parse_case(example)
    assert case["expected"]["title"] == "kazoe_yakuman"
    assert case["expected"]["yakuman_multiplier"] == 0
    assert case["expected"]["han"] == 13


@pytest.mark.parametrize("title", ["double_yakuman", "", 5])
def test_invalid_title(example: dict[str, Any], title: object) -> None:
    example["expected"]["title"] = title
    with pytest.raises(CorpusError) as error:
        parse_case(example)
    assert error.value.field == "expected.title"


def test_unknown_title_requires_reason(example: dict[str, Any]) -> None:
    example["expected"]["title"] = None
    with pytest.raises(CorpusError, match=r"expected\.title"):
        parse_case(example)
    example["comparison"]["excluded_fields"] = [
        {"field": "title", "reason": "not_recorded"}
    ]
    assert parse_case(example)["expected"]["title"] is None


def test_reject_unsupported_version(example: dict[str, Any]) -> None:
    example["schema_version"] = "v2"

    with pytest.raises(CorpusError) as error:
        parse_case(example)

    assert error.value.field == "schema_version"


def test_majsoul_example_preserves_red_tile() -> None:
    path = Path(__file__).parent / "fixtures/majsoul-scoring.json"
    case = parse_case(json.loads(path.read_text(encoding="utf-8")))

    assert "0s" in case["input"]["concealed_tiles"]
    assert case["input"]["situation"]["ippatsu"] is False
    assert case["expected"]["winner_gain"] == 4600
    assert case["source"]["scoring_values"]["point_sum"] == 2600


@pytest.mark.parametrize(
    ("field", "value"),
    [("player_count", True), ("win_number", "1"), ("unknown", 1)],
)
def test_reject_wrong_shape(
    example: dict[str, Any], field: str, value: object
) -> None:
    example[field] = value
    with pytest.raises(CorpusError) as error:
        parse_case(example)
    assert error.value.field == field


def test_missing_required_field(example: dict[str, Any]) -> None:
    del example["input"]["situation"]["renhou"]
    with pytest.raises(CorpusError) as error:
        parse_case(example)
    assert error.value.field == "input.situation.renhou"


@pytest.mark.parametrize("tile", ["0z", "8z", "10m", "1x", "", " 1m"])
def test_reject_invalid_tile(example: dict[str, Any], tile: str) -> None:
    example["input"]["winning_tile"] = tile
    with pytest.raises(CorpusError) as error:
        parse_case(example)
    assert error.value.field == "input.winning_tile"


def test_chii_keeps_source_order(example: dict[str, Any]) -> None:
    example["input"]["concealed_tiles"] = example["input"]["concealed_tiles"][
        3:
    ]
    example["input"]["melds"] = [
        {
            "type": "chii",
            "tiles": ["2m", "1m", "3m"],
            "called_tile_index": 2,
            "from_seat": 1,
        }
    ]

    case = parse_case(example)

    assert case["input"]["melds"][0]["tiles"] == ["2m", "1m", "3m"]


def test_reject_wrong_concealed_count(example: dict[str, Any]) -> None:
    example["input"]["concealed_tiles"].pop()
    with pytest.raises(CorpusError) as error:
        parse_case(example)
    assert error.value.field == "input.concealed_tiles"


@pytest.mark.parametrize(
    ("tiles", "called"),
    [
        (["1m", "2m"], 0),
        (["1m", "2m", "4m"], 0),
        (["1m", "2p", "3m"], 0),
        (["1m", "2m", "3m"], 3),
    ],
)
def test_reject_malformed_chii(
    example: dict[str, Any], tiles: list[str], called: int
) -> None:
    example["input"]["concealed_tiles"] = example["input"]["concealed_tiles"][
        3:
    ]
    example["input"]["melds"] = [
        {
            "type": "chii",
            "tiles": tiles,
            "called_tile_index": called,
            "from_seat": 1,
        }
    ]
    with pytest.raises(CorpusError, match=r"input.melds\[0\]"):
        parse_case(example)


def test_red_and_regular_five_share_four_tile_limit(
    example: dict[str, Any],
) -> None:
    example["input"]["concealed_tiles"][:5] = ["0m", "5m", "5m", "5m", "5m"]
    with pytest.raises(CorpusError, match="four copies"):
        parse_case(example)


@pytest.mark.parametrize("seat", [-1, 4])
def test_reject_seat_outside_players(
    example: dict[str, Any], seat: int
) -> None:
    example["input"]["winner_seat"] = seat
    with pytest.raises(CorpusError) as error:
        parse_case(example)
    assert error.value.field == "input.winner_seat"


def test_three_player_case(example: dict[str, Any]) -> None:
    example["player_count"] = 3
    example["expected"]["payments_by_seat"].pop()
    example["expected"]["event_score_deltas"].pop()
    assert parse_case(example)["player_count"] == 3


def test_three_player_rejects_fourth_seat(example: dict[str, Any]) -> None:
    example["player_count"] = 3
    example["input"]["discarder_seat"] = 3
    with pytest.raises(CorpusError) as error:
        parse_case(example)
    assert error.value.field == "input.discarder_seat"


@pytest.mark.parametrize(
    ("tsumo", "discarder"), [(True, 0), (False, None), (False, 2)]
)
def test_reject_inconsistent_win_method(
    example: dict[str, Any], *, tsumo: bool, discarder: int | None
) -> None:
    example["input"]["situation"]["tsumo"] = tsumo
    example["input"]["discarder_seat"] = discarder
    with pytest.raises(CorpusError) as error:
        parse_case(example)
    assert error.value.field == "input.discarder_seat"


def test_yakuman_keeps_ippatsu_and_recorded_fu(
    example: dict[str, Any],
) -> None:
    expected = example["expected"]
    expected.update(
        {
            "yaku": [{"id": "suuankou", "han": None, "yakuman_multiplier": 1}],
            "title": "yakuman",
            "han": None,
            "yakuman_multiplier": 1,
            "base_points": 32000,
            "winner_gain": 33000,
            "payments_by_seat": [32000, 0, 0, 0],
            "event_score_deltas": [-32000, 0, 33000, 0],
        }
    )
    case = parse_case(example)
    assert case["input"]["situation"]["ippatsu"] is True
    assert case["expected"]["yaku"] == expected["yaku"]
    assert case["expected"]["fu"] == 40


def test_unknown_situation_and_missing_fu(example: dict[str, Any]) -> None:
    example["input"]["situation"]["ippatsu"] = None
    example["situation_provenance"]["unknown_fields"] = {
        "ippatsu": "missing_events"
    }
    example["expected"]["fu"] = None
    example["comparison"]["excluded_fields"] = [
        {"field": "fu", "reason": "not_recorded"}
    ]
    case = parse_case(example)
    assert case["input"]["situation"]["ippatsu"] is None
    assert case["expected"]["fu"] is None
    assert case["comparison"]["excluded_fields"][0]["reason"] == "not_recorded"


def test_missing_expectation_needs_exclusion_reason(
    example: dict[str, Any],
) -> None:
    example["expected"]["fu"] = None
    with pytest.raises(CorpusError) as error:
        parse_case(example)
    assert error.value.field == "expected.fu"


@pytest.mark.parametrize("field", ["han", "winner_gain", "payments_by_seat"])
def test_reject_inconsistent_expectation(
    example: dict[str, Any], field: str
) -> None:
    example["expected"][field] = (
        [100, 0, 0, 0] if field == "payments_by_seat" else 99
    )
    with pytest.raises(CorpusError) as error:
        parse_case(example)
    assert error.value.field == "expected." + field


def test_multi_ron_event_delta_is_not_single_winner_gain(
    example: dict[str, Any],
) -> None:
    example["expected"]["event_score_deltas"] = [-5200, 2600, 3600, 0]
    assert parse_case(example)["expected"]["event_score_deltas"] == [
        -5200,
        2600,
        3600,
        0,
    ]


def test_liability_payments_can_be_unknown(example: dict[str, Any]) -> None:
    example["expected"]["payments_by_seat"] = None
    example["comparison"]["excluded_fields"] = [
        {"field": "payments_by_seat", "reason": "liability_payment"}
    ]
    assert parse_case(example)["expected"]["payments_by_seat"] is None


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("round", "number", 0),
        ("round", "honba", -1),
        ("input", "nuki_count", -1),
        ("source", "event_index", -1),
        ("expected", "fu", -1),
    ],
)
def test_reject_invalid_numeric_bounds(
    example: dict[str, Any], section: str, field: str, value: int
) -> None:
    example[section][field] = value
    with pytest.raises(CorpusError) as error:
        parse_case(example)
    assert error.value.field == f"{section}.{field}"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), object()])
def test_source_values_must_be_json_data(
    example: dict[str, Any], value: object
) -> None:
    example["source"]["scoring_values"]["invalid"] = value
    with pytest.raises(CorpusError, match=r"source\.scoring_values\.invalid"):
        parse_case(example)


def test_nullable_array_error_identifies_element(
    example: dict[str, Any],
) -> None:
    example["expected"]["payments_by_seat"][0] = "2600"
    with pytest.raises(CorpusError) as error:
        parse_case(example)
    assert error.value.field == "expected.payments_by_seat[0]"


@pytest.mark.parametrize(
    ("han", "multiplier"), [(0, 0), (-1, 0), (1, 1), (None, 0)]
)
def test_yaku_distinguishes_han_and_yakuman(
    example: dict[str, Any], han: int | None, multiplier: int
) -> None:
    example["expected"]["yaku"][0].update(
        han=han, yakuman_multiplier=multiplier
    )
    with pytest.raises(CorpusError, match=r"expected\.yaku\[0\]"):
        parse_case(example)


def test_yakuman_total_matches_yaku_multipliers(
    example: dict[str, Any],
) -> None:
    example["expected"]["yakuman_multiplier"] = 1
    with pytest.raises(CorpusError) as error:
        parse_case(example)
    assert error.value.field == "expected.yakuman_multiplier"


def test_tsumo_and_ankan_keep_nullable_meld_metadata(
    example: dict[str, Any],
) -> None:
    hand = example["input"]
    hand["concealed_tiles"] = hand["concealed_tiles"][3:]
    hand["melds"] = [
        {
            "type": "ankan",
            "tiles": ["1m"] * 4,
            "called_tile_index": None,
            "from_seat": None,
        }
    ]
    hand["situation"]["tsumo"] = True
    hand["discarder_seat"] = None
    case = parse_case(example)
    assert case["input"]["melds"][0]["from_seat"] is None
    assert case["input"]["discarder_seat"] is None


def test_recorded_kokushi_fu_is_kept_when_excluded(
    example: dict[str, Any],
) -> None:
    example["expected"]["fu"] = 0
    example["comparison"]["excluded_fields"] = [
        {"field": "fu", "reason": "kokushi_fu_not_comparable"}
    ]
    assert parse_case(example)["expected"]["fu"] == 0

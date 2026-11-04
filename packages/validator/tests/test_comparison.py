from copy import deepcopy
from typing import TYPE_CHECKING, cast

import pytest

from validator.validation import compare_result, validate_case

if TYPE_CHECKING:
    from collections.abc import Callable

    from corpus.models import ScoringCase


def test_later_ron_bonus_allocation_is_not_inferred_from_expectations(
    load_case: Callable[..., ScoringCase],
) -> None:
    case = load_case()
    case["win_number"] = 2
    case["expected"].update(
        honba_points=0, riichi_stick_points=0, winner_gain=2600
    )
    result = validate_case(case)
    assert result["status"] == "passed"
    for field in (
        "honba_points",
        "riichi_stick_points",
        "winner_gain",
        "payments_by_seat",
    ):
        assert result["fields"][field]["status"] == "unsupported"
    assert result["fields"]["base_points"]["status"] == "matched"


def test_liability_and_shared_event_exclusions_keep_original_reasons(
    load_case: Callable[..., ScoringCase],
) -> None:
    case = load_case("synthetic-liability")
    result = validate_case(case)
    assert result["fields"]["payments_by_seat"]["status"] == "excluded"
    assert (
        result["fields"]["payments_by_seat"]["reason"] == "liability_payment"
    )
    case = load_case()
    case["comparison"]["excluded_fields"] = [
        {"field": "honba_points", "reason": "multiple_ron_allocation_unknown"},
    ]
    result = validate_case(case)
    assert result["fields"]["honba_points"]["status"] == "excluded"
    assert result["fields"]["winner_gain"]["status"] == "unsupported"


@pytest.mark.parametrize(
    "field",
    [
        "title",
        "han",
        "fu",
        "yakuman_multiplier",
        "base_points",
        "honba_points",
        "riichi_stick_points",
        "winner_gain",
        "payments_by_seat",
    ],
)
def test_each_score_field_is_compared_independently(
    load_case: Callable[..., ScoringCase], field: str
) -> None:
    case = load_case()
    actual = deepcopy(case["expected"])
    values = cast("dict[str, object]", actual)
    values[field] = "wrong" if field == "title" else -1
    result = compare_result(case, actual)
    assert result[field]["status"] == "mismatched"
    assert sum(item["status"] == "mismatched" for item in result.values()) == 1


def test_yaku_order_and_compensating_han_errors(
    load_case: Callable[..., ScoringCase],
) -> None:
    case = load_case("synthetic-sanma-tsumo")
    actual = deepcopy(case["expected"])
    yaku = actual["yaku"]
    assert yaku is not None
    yaku.reverse()
    assert compare_result(case, actual)["yaku"]["status"] == "matched"
    yaku[0]["han"] = 1  # nuki: 2 -> 1
    yaku[1]["han"] = 2  # red: 1 -> 2; total unchanged
    assert compare_result(case, actual)["yaku"]["status"] == "mismatched"


def test_real_yakuman_and_kazoe_are_distinct(
    load_case: Callable[..., ScoringCase],
) -> None:
    case = load_case()
    actual = deepcopy(case["expected"])
    actual["yaku"] = [
        {"id": "daisangen", "han": None, "yakuman_multiplier": 1},
        {"id": "suuankou", "han": None, "yakuman_multiplier": 1},
    ]
    actual.update(title="yakuman", han=None, yakuman_multiplier=2)
    case["expected"] = deepcopy(actual)
    assert (
        compare_result(case, actual)["yakuman_multiplier"]["status"]
        == "matched"
    )
    actual["yakuman_multiplier"] = 1
    assert (
        compare_result(case, actual)["yakuman_multiplier"]["status"]
        == "mismatched"
    )
    actual.update(title="kazoe_yakuman", han=26, yakuman_multiplier=0)
    assert compare_result(case, actual)["title"]["status"] == "mismatched"


def test_all_expectations_excluded_is_skipped(
    load_case: Callable[..., ScoringCase],
) -> None:
    case = load_case()
    case["comparison"]["excluded_fields"] = [
        {"field": field, "reason": "test exclusion"}
        for field in case["expected"]
    ]
    result = validate_case(case)
    assert result["status"] == "skipped"
    assert all(
        item["status"] == "excluded" for item in result["fields"].values()
    )


def test_unknown_expected_yaku_is_not_inferred_from_total(
    load_case: Callable[..., ScoringCase],
) -> None:
    case = load_case()
    case["expected"]["yaku"] = None
    case["comparison"]["excluded_fields"] = [
        {"field": "yaku", "reason": "unrecorded"}
    ]
    result = validate_case(case)
    assert result["status"] == "passed"
    assert result["fields"]["yaku"]["status"] == "excluded"
    assert result["fields"]["han"]["status"] == "matched"

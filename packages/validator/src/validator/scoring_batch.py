from typing import TYPE_CHECKING

from validator.adapter import prepare_calculation, prepare_hand

if TYPE_CHECKING:
    from collections.abc import Callable

    from corpus.models import ScoringCase


type ScoringCall = tuple[int, str, Callable[[], object]]


def run_batch(calls: list[ScoringCall]) -> None:
    for _, _, calculate in calls:
        calculate()


def prepare_calls(
    selected: list[tuple[int, ScoringCase]],
) -> list[ScoringCall]:
    return [
        (
            position,
            case["case_id"],
            prepare_calculation(
                prepare_hand(
                    case["input"],
                    case["round"],
                    case["player_count"],
                    case["ruleset"],
                )
            ),
        )
        for position, case in selected
    ]

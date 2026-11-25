from typing import TYPE_CHECKING

from validator.adapter import prepare_calculation, prepare_scoring_case

if TYPE_CHECKING:
    from validator.batch import PreparedCall
    from validator.selection import SelectedScoringCase


def prepare_calls(selected: list[SelectedScoringCase]) -> list[PreparedCall]:
    return [
        (
            position,
            case["case_id"],
            prepare_calculation(prepare_scoring_case(case)),
        )
        for position, case in selected
    ]

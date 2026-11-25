from typing import TYPE_CHECKING

from validator.adapter import (
    prepare_calculation,
    prepare_scoring_case,
    prepare_shape_call,
)

if TYPE_CHECKING:
    from validator.batch import PreparedCall
    from validator.selection import SelectedCase


def prepare_calls(selected: list[SelectedCase]) -> list[PreparedCall]:
    calls: list[PreparedCall] = []
    for position, case in selected:
        if case["case_type"] == "scoring":
            calculate = prepare_calculation(prepare_scoring_case(case))
        else:
            calculate = prepare_shape_call(case)
        calls.append((position, case["case_id"], calculate))
    return calls

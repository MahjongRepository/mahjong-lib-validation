from typing import TYPE_CHECKING, assert_never

from validator.adapter import (
    prepare_agari_call,
    prepare_calculation,
    prepare_scoring_case,
    prepare_shanten_call,
)

if TYPE_CHECKING:
    from validator.batch import PreparedCall
    from validator.selection import SelectedCase


def prepare_calls(selected: list[SelectedCase]) -> list[PreparedCall]:
    calls: list[PreparedCall] = []
    for position, case in selected:
        match case["case_type"]:
            case "scoring":
                calculate = prepare_calculation(prepare_scoring_case(case))
            case "agari":
                calculate = prepare_agari_call(case)
            case "shanten":
                calculate = prepare_shanten_call(case)
            case _ as case_type:
                assert_never(case_type)
        calls.append((position, case["case_id"], calculate))
    return calls

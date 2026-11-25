from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from validator.preparation import prepare_calls
from validator.sampling_worker import sample_batches, warm_and_check_inputs

if TYPE_CHECKING:
    from collections.abc import Callable

    from corpus.models import ScoringCase
    from validator.batch import PreparedCall


@pytest.mark.parametrize(
    "fixture",
    [
        "tenhou-scoring",
        "tenhou-kokushi",
        "synthetic-sanma-tsumo",
        "synthetic-ankan",
    ],
)
def test_warmed_inputs_are_stable(
    fixture: str, load_case: Callable[..., ScoringCase]
) -> None:
    calls = prepare_calls([(1, load_case(fixture))])
    warm_and_check_inputs(calls)


@dataclass
class ChangingInput:
    count: int = 0

    def __call__(self) -> None:
        self.count += 1


def test_unstable_inputs_cannot_be_reused() -> None:
    with pytest.raises(ValueError, match="prepared input changed at case 2"):
        warm_and_check_inputs([(2, "unstable", ChangingInput())])


def test_sampling_stops_at_the_end_of_a_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    times = iter([0, 600_000_000, 1_200_000_000])
    monkeypatch.setattr(
        "validator.sampling_worker.perf_counter_ns", lambda: next(times)
    )
    first = ChangingInput()
    second = ChangingInput()
    calls: list[PreparedCall] = [(1, "first", first), (2, "second", second)]
    assert sample_batches(calls, 1.0) == (2, 1_200_000_000)
    assert first.count == second.count == 2

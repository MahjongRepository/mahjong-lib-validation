import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from corpus import CorpusError
lazy from corpus.models import Case, CaseType

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

MAX_CASE_IDS = 100


def selection_digest_entry(position: int, case_id: str) -> bytes:
    return (json.dumps([position, case_id], ensure_ascii=False) + "\n").encode(
        "utf-8"
    )


type SelectedCase = tuple[int, Case]


@dataclass(frozen=True)
class Selection:
    player_count: int | None = None
    case_ids: tuple[str, ...] = ()
    limit: int | None = None

    def __post_init__(self) -> None:
        if len(self.case_ids) > MAX_CASE_IDS:
            msg = f"at most {MAX_CASE_IDS} case IDs may be selected"
            raise ValueError(msg)
        if self.limit is not None and self.limit <= 0:
            msg = "limit must be positive"
            raise ValueError(msg)
        if self.player_count is not None and self.player_count not in (3, 4):
            msg = "player_count must be 3 or 4"
            raise ValueError(msg)
        if "" in self.case_ids:
            msg = "case_ids must not contain empty strings"
            raise ValueError(msg)

    def matches(self, case: Case, selected: int) -> bool:
        return (
            (
                self.player_count is None
                or self.player_count == case["player_count"]
            )
            and (not self.case_ids or case["case_id"] in self.case_ids)
            and (self.limit is None or selected < self.limit)
        )


class SelectionScan:
    """Track one full scan and hash the selected cases."""

    def __init__(self, selection: Selection, case_type: CaseType) -> None:
        self.selection = selection
        self.case_type = case_type
        self.scanned_count = 0
        self.selected_count = 0
        self._digest = hashlib.sha256()

    @property
    def selection_sha256(self) -> str:
        return self._digest.hexdigest()

    def select(self, cases: Iterable[Case]) -> Iterator[SelectedCase]:
        for self.scanned_count, case in enumerate(cases, start=1):
            if case["case_type"] != self.case_type:
                msg = f"expected {self.case_type!r}, got {case['case_type']!r}"
                field = "case_type"
                raise CorpusError(field, msg)
            if self.selection.matches(case, self.selected_count):
                self.selected_count += 1
                self._digest.update(
                    selection_digest_entry(self.scanned_count, case["case_id"])
                )
                yield self.scanned_count, case

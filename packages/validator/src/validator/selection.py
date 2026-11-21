from dataclasses import dataclass

lazy from corpus.models import ScoringCase


@dataclass(frozen=True)
class Selection:
    player_count: int | None = None
    case_ids: tuple[str, ...] = ()
    limit: int | None = None

    def __post_init__(self) -> None:
        if self.limit is not None and self.limit <= 0:
            msg = "limit must be positive"
            raise ValueError(msg)
        if self.player_count is not None and self.player_count not in (3, 4):
            msg = "player_count must be 3 or 4"
            raise ValueError(msg)
        if "" in self.case_ids:
            msg = "case_ids must not contain empty strings"
            raise ValueError(msg)

    def matches(self, case: ScoringCase, selected: int) -> bool:
        return (
            (
                self.player_count is None
                or self.player_count == case["player_count"]
            )
            and (not self.case_ids or case["case_id"] in self.case_ids)
            and (self.limit is None or selected < self.limit)
        )

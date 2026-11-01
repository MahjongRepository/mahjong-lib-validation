"""JSON-native models for v1 scoring records."""

from typing import Literal, TypedDict


class Source(TypedDict):
    platform: Literal["tenhou", "majsoul"]
    log_id: str
    event_index: int
    winner_index: int
    scoring_values: dict[str, object]


class Round(TypedDict):
    wind: Literal["east", "south", "west", "north"]
    number: int
    honba: int
    riichi_sticks: int
    dealer_seat: int


class Meld(TypedDict):
    type: Literal["chii", "pon", "daiminkan", "ankan", "kakan"]
    tiles: list[str]
    called_tile_index: int | None
    from_seat: int | None


class Situation(TypedDict):
    tsumo: bool
    riichi: Literal["none", "riichi", "double_riichi"] | None
    ippatsu: bool | None
    rinshan: bool | None
    chankan: bool | None
    haitei: bool | None
    houtei: bool | None
    tenhou: bool | None
    chiihou: bool | None
    renhou: bool | None


class ScoringInput(TypedDict):
    winner_seat: int
    discarder_seat: int | None
    concealed_tiles: list[str]
    winning_tile: str
    melds: list[Meld]
    nuki_count: int
    dora_indicators: list[str]
    ura_dora_indicators: list[str]
    situation: Situation


class SituationProvenance(TypedDict):
    method: Literal["event_reconstruction"]
    event_indices: list[int]


class Yaku(TypedDict):
    id: str
    han: int | None
    yakuman_multiplier: int


class Expected(TypedDict):
    yaku: list[Yaku]
    han: int | None
    fu: int | None
    yakuman_multiplier: int
    base_points: int | None
    honba_points: int | None
    riichi_stick_points: int | None
    winner_gain: int | None
    payments_by_seat: list[int] | None
    event_score_deltas: list[int] | None


class ExcludedField(TypedDict):
    field: str
    reason: str


class Comparison(TypedDict):
    excluded_fields: list[ExcludedField]


class ScoringCase(TypedDict):
    schema_version: Literal["v1"]
    case_type: Literal["scoring"]
    case_id: str
    source: Source
    ruleset: Literal["tenhou-ranked-match", "majsoul-ranked-match"]
    player_count: Literal[3, 4]
    round: Round
    win_number: int
    input: ScoringInput
    situation_provenance: SituationProvenance
    expected: Expected
    comparison: Comparison

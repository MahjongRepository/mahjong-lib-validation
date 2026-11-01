"""JSON-native models for v1 scoring records."""

from typing import Literal, TypedDict

Tile = Literal[
    "0m", "1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m",
    "0p", "1p", "2p", "3p", "4p", "5p", "6p", "7p", "8p", "9p",
    "0s", "1s", "2s", "3s", "4s", "5s", "6s", "7s", "8s", "9s",
    "1z", "2z", "3z", "4z", "5z", "6z", "7z",
]  # fmt: skip


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
    tiles: list[Tile]
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
    concealed_tiles: list[Tile]
    winning_tile: Tile
    melds: list[Meld]
    nuki_count: int
    dora_indicators: list[Tile]
    ura_dora_indicators: list[Tile]
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

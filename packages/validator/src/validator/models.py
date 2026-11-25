from typing import Literal, NotRequired, TypedDict

type CaseStatus = Literal[
    "passed", "mismatch", "error", "unsupported", "skipped"
]
type FieldStatus = Literal[
    "matched", "mismatched", "excluded", "unavailable", "unsupported"
]


class FieldResult(TypedDict):
    status: FieldStatus
    expected: object
    actual: object
    reason: NotRequired[str]


class CaseResult(TypedDict):
    case_id: str
    status: CaseStatus
    fields: dict[str, FieldResult]
    reason: NotRequired[str]
    position: NotRequired[int]


class ValidationSummary(TypedDict):
    counts: dict[CaseStatus, int]
    exit_code: int
    scanned_count: int
    selected_count: int
    schema_version: Literal["v1"]
    purpose: Literal["validate"]
    complete: bool
    field_counts: dict[str, dict[str, int]]
    selection_sha256: str
    selection: dict[str, object]
    corpus: CorpusIdentity
    environment: Environment
    comparison_policy: str


class SuccessfulSample(TypedDict):
    status: Literal["ok"]
    elapsed_ns: int


class FailedSample(TypedDict):
    status: Literal["error"]
    position: int
    case_id: str
    reason: str


type BenchmarkSample = SuccessfulSample | FailedSample


class BenchmarkSettings(TypedDict):
    samples: int
    warmup_batches: int
    regenerate_inputs: bool
    cache: str
    gc_enabled: bool


class BenchmarkStatistics(TypedDict):
    median_ns: int | float
    min_ns: int
    max_ns: int
    stdev_ns: float | None
    cases_per_second: float | None


class BenchmarkSummary(TypedDict):
    schema_version: Literal["v1"]
    purpose: Literal["benchmark"]
    complete: bool
    exit_code: int
    preflight: ValidationSummary
    settings: BenchmarkSettings
    sample_count: int
    statistics: BenchmarkStatistics | None


class ProfileSettings(TypedDict):
    warmup_batches: int
    reuse_inputs: bool
    cache: str
    gc_enabled: bool
    min_seconds: NotRequired[float]
    sampling_rate_hz: NotRequired[int]
    synchronization_frames: NotRequired[list[str]]


class SamplingResult(TypedDict):
    repetitions: int
    elapsed_ns: int
    gc_enabled: bool
    sample_count: int


class ProfileSummary(TypedDict):
    schema_version: Literal["v1"]
    purpose: Literal["profile"]
    complete: bool
    exit_code: int
    method: Literal["tracing", "sampling"]
    scope: Literal["scoring_batch"]
    preflight: ValidationSummary
    settings: ProfileSettings
    case_count: int
    repetitions: int
    processed_count: int
    elapsed_ns: int | None
    sample_count: NotRequired[int]


class CorpusIdentity(TypedDict):
    manifest_sha256: str


class Environment(TypedDict):
    validator_version: str
    corpus_version: str
    mahjong_version: str
    mahjong_path: str
    python: str
    python_executable: str
    python_implementation: str
    python_build: list[str]
    platform: str
    free_threaded: bool
    rules_version: str

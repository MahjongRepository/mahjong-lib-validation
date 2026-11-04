from typing import Literal, NotRequired, TypedDict

lazy from corpus.models import Manifest

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
    field_reasons: dict[str, dict[str, int]]
    selection_sha256: str
    selection: dict[str, object]
    corpus: CorpusIdentity
    environment: Environment
    comparison_policy: str


class CorpusIdentity(TypedDict):
    manifest: Manifest
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

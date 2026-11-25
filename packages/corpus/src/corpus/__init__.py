"""Shared corpus models and I/O for mahjong library validation."""

from corpus.case_io import read_cases, write_cases
from corpus.checks import parse_case, parse_scoring_case
from corpus.datasets import (
    check_dataset,
    file_sha256,
    read_dataset,
    write_dataset,
)
from corpus.errors import CorpusError
from corpus.manifests import parse_manifest, read_manifest, write_manifest
from corpus.models import (
    AgariCase,
    Case,
    CaseType,
    Manifest,
    ScoringCase,
    ShantenCase,
)

__all__ = [
    "AgariCase",
    "Case",
    "CaseType",
    "CorpusError",
    "Manifest",
    "ScoringCase",
    "ShantenCase",
    "check_dataset",
    "file_sha256",
    "parse_case",
    "parse_manifest",
    "parse_scoring_case",
    "read_cases",
    "read_dataset",
    "read_manifest",
    "write_cases",
    "write_dataset",
    "write_manifest",
]

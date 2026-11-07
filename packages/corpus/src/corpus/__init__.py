"""Shared corpus models and I/O for mahjong library validation."""

from corpus.case_io import read_cases, write_cases
from corpus.checks import parse_case
from corpus.datasets import check_dataset, read_dataset, write_dataset
from corpus.errors import CorpusError
from corpus.manifests import parse_manifest, read_manifest, write_manifest
from corpus.models import Manifest, ScoringCase

__all__ = [
    "CorpusError",
    "Manifest",
    "ScoringCase",
    "check_dataset",
    "parse_case",
    "parse_manifest",
    "read_cases",
    "read_dataset",
    "read_manifest",
    "write_cases",
    "write_dataset",
    "write_manifest",
]

"""Convert Mahjong Soul replay data to validation corpora."""

from majsoul_converter.conversion import convert_log
from majsoul_converter.datasets import convert_files
from majsoul_converter.decoder import ConversionError

__all__ = ["ConversionError", "convert_files", "convert_log"]

import argparse
import json
import sys
from importlib.metadata import version
from typing import TYPE_CHECKING

from corpus import CorpusError

from majsoul_converter.conversion import TARGETS
from majsoul_converter.datasets import convert_files

if TYPE_CHECKING:
    from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="majsoul-converter",
        description="Convert Mahjong Soul replay data to a v1 corpus.",
    )
    parser.add_argument(
        "--version", action="version", version=version("majsoul-converter")
    )
    parser.add_argument("input")
    parser.add_argument("--output", required=True)
    parser.add_argument("--target", choices=TARGETS, default="scoring")
    parser.add_argument("--log-id")
    parser.add_argument("--cases-per-file", type=int, default=100_000)
    parser.add_argument("--no-compress", action="store_true")

    args = parser.parse_args(argv)

    try:
        manifest = convert_files(
            args.input,
            args.output,
            log_id=args.log_id,
            target=args.target,
            cases_per_file=args.cases_per_file,
            compress=not args.no_compress,
        )
    except (CorpusError, OSError, ValueError) as e:
        sys.stderr.write(f"{e}\n")
        return 1

    sys.stderr.write(json.dumps(manifest) + "\n")
    return 0

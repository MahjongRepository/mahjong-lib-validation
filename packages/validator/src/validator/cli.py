import argparse
import json
import sys
from importlib.metadata import version
lazy from collections.abc import Sequence

from validator import Selection, validate_dataset


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mahjong-validator",
        description="Validate mahjong against scoring corpus v1.",
    )
    parser.add_argument(
        "--version", action="version", version=version("mahjong-validator")
    )
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("dataset")
    validate.add_argument("--output", required=True)
    validate.add_argument("--player-count", type=int, choices=(3, 4))
    validate.add_argument("--case-id", action="append", default=[])
    validate.add_argument("--limit", type=int)
    args = parser.parse_args(argv)
    try:
        summary = validate_dataset(
            args.dataset,
            args.output,
            selection=Selection(
                args.player_count, tuple(args.case_id), args.limit
            ),
        )
    except (ValueError, OSError) as error:
        sys.stderr.write(f"{error}\n")
        return 2
    sys.stdout.write(json.dumps(summary, ensure_ascii=False) + "\n")
    return summary["exit_code"]

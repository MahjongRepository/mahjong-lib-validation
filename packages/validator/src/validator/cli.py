import argparse
import json
import sys
from importlib.metadata import version
lazy from collections.abc import Sequence

from validator import (
    Selection,
    benchmark_dataset,
    profile_dataset,
    validate_dataset,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mahjong-validator",
        description="Validate mahjong against scoring corpus v1.",
    )
    parser.add_argument(
        "--version", action="version", version=version("mahjong-validator")
    )
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate")
    _add_dataset_arguments(validate)
    validate.add_argument("--limit", type=int)
    validate.set_defaults(handler=_run_validate)

    benchmark = commands.add_parser("benchmark")
    _add_dataset_arguments(benchmark)
    benchmark.add_argument("--limit", type=int, required=True)
    benchmark.add_argument("--samples", type=int, default=10)
    benchmark.set_defaults(handler=_run_benchmark)

    profile = commands.add_parser("profile")
    _add_dataset_arguments(profile)
    profile.add_argument("--limit", type=int, required=True)
    profile.add_argument(
        "--method",
        required=True,
        help="collection method: tracing or sampling",
    )
    profile.add_argument(
        "--min-seconds",
        type=float,
        help="sampling batch duration (default: 3 seconds)",
    )
    profile.add_argument(
        "--sampling-rate",
        type=int,
        help="sampling frequency in Hz (default: 1000)",
    )
    profile.set_defaults(handler=_run_profile)

    return parser


def _add_dataset_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("dataset")
    parser.add_argument("--output", required=True)
    parser.add_argument("--player-count", type=int, choices=(3, 4))
    parser.add_argument("--case-id", action="append", default=[])


def _run_validate(args: argparse.Namespace) -> int:
    summary = validate_dataset(
        args.dataset,
        args.output,
        selection=Selection(
            args.player_count, tuple(args.case_id), args.limit
        ),
    )
    sys.stdout.write(json.dumps(summary, ensure_ascii=False) + "\n")
    return summary["exit_code"]


def _run_benchmark(args: argparse.Namespace) -> int:
    summary = benchmark_dataset(
        args.dataset,
        args.output,
        selection=Selection(
            args.player_count, tuple(args.case_id), args.limit
        ),
        samples=args.samples,
    )
    sys.stdout.write(json.dumps(summary, ensure_ascii=False) + "\n")
    return summary["exit_code"]


def _run_profile(args: argparse.Namespace) -> int:
    summary = profile_dataset(
        args.dataset,
        args.output,
        selection=Selection(
            args.player_count, tuple(args.case_id), args.limit
        ),
        method=args.method,
        min_seconds=args.min_seconds,
        sampling_rate_hz=args.sampling_rate,
    )
    sys.stdout.write(json.dumps(summary, ensure_ascii=False) + "\n")
    return summary["exit_code"]


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except (ValueError, OSError) as e:
        sys.stderr.write(f"{e}\n")
        return 2

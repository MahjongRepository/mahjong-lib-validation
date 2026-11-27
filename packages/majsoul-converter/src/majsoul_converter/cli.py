import argparse
import json
import sys
from importlib.metadata import version
from typing import TYPE_CHECKING

from majsoul_converter.conversion import TARGETS
from majsoul_converter.datasets import BatchConversionError, convert_files

if TYPE_CHECKING:
    from collections.abc import Sequence


def positive(value: str) -> int:
    number = int(value)
    if number <= 0:
        msg = "must be a positive integer"
        raise argparse.ArgumentTypeError(msg)
    return number


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
    parser.add_argument("--cases-per-file", type=positive, default=100_000)
    parser.add_argument("--no-compress", action="store_true")
    parser.add_argument("--report")

    args = parser.parse_args(argv)

    try:
        manifest = convert_files(
            args.input,
            args.output,
            log_id=args.log_id,
            cases_per_file=args.cases_per_file,
            compress=not args.no_compress,
            report_path=args.report,
            target=args.target,
        )
    except BatchConversionError as e:
        sys.stderr.write(json.dumps(e.report, ensure_ascii=False) + "\n")
        return 1
    except OSError as e:
        sys.stderr.write(f"{e}\n")
        return 1
    except ValueError as e:
        parser.error(str(e))
    else:
        sys.stderr.write(
            json.dumps(
                {
                    "dataset_published": True,
                    "conversion": manifest["conversion"],
                    "record_count": manifest["record_count"],
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        return 0

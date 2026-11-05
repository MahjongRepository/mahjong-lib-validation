import argparse
import json
import sys
from importlib.metadata import version
lazy from collections.abc import Sequence

from tenhou_converter.datasets import BatchConversionError, convert_files


def positive(value: str) -> int:
    number = int(value)
    if number <= 0:
        msg = "must be a positive integer"
        raise argparse.ArgumentTypeError(msg)
    return number


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tenhou-converter",
        description="Convert Tenhou mjlog to scoring corpus v1.",
    )
    parser.add_argument(
        "--version", action="version", version=version("tenhou-converter")
    )
    commands = parser.add_subparsers(dest="command", required=True)
    mjlog = commands.add_parser("mjlog")
    mjlog.add_argument("input")
    mjlog.add_argument("--output", required=True)
    mjlog.add_argument("--log-id")
    mjlog.add_argument("--cases-per-file", type=positive, default=100_000)
    mjlog.add_argument("--no-compress", action="store_true")
    mjlog.add_argument("--report")
    args = parser.parse_args(argv)
    try:
        manifest = convert_files(
            args.input,
            args.output,
            log_id=args.log_id,
            cases_per_file=args.cases_per_file,
            compress=not args.no_compress,
            report_path=args.report,
        )
    except BatchConversionError as error:
        sys.stderr.write(json.dumps(error.report, ensure_ascii=False) + "\n")
        return 1
    except OSError as error:
        sys.stderr.write(str(error) + "\n")
        return 1
    except ValueError as error:
        parser.error(str(error))
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
    return 2

from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING

from corpus import Manifest, ScoringCase, write_dataset

from majsoul_converter.conversion import convert_log
from majsoul_converter.decoder import ConversionError

if TYPE_CHECKING:
    from collections.abc import Iterator

    from corpus.models import ConversionSummary


def convert_files(
    input_path: str | Path,
    output_directory: str | Path,
    *,
    log_id: str | None = None,
    cases_per_file: int = 100_000,
    compress: bool = True,
) -> Manifest:
    """Publish a corpus from one replay or a directory of replays."""
    source, output = Path(input_path), Path(output_directory)
    if source.is_dir():
        if log_id is not None:
            msg = "log ID override requires a single replay file"
            raise ValueError(msg)
        if output.resolve().is_relative_to(source.resolve()):
            msg = "output must be outside the input directory"
            raise ValueError(msg)
        paths = sorted(
            (
                path
                for path in source.rglob("*")
                if path.is_file() and path.suffix.lower() == ".bin"
            ),
            key=lambda path: path.relative_to(source).as_posix(),
        )
    elif source.suffix.lower() == ".bin":
        paths = [source]
    else:
        msg = f"replay input must have a .bin extension: {source}"
        raise ConversionError(msg)
    if not paths:
        msg = f"no .bin replays in {source}"
        raise ConversionError(msg)

    summary: ConversionSummary = {
        "input_count": len(paths),
        "converted_count": 0,
        "failed_by_reason": {},
        "excluded_by_reason": {},
    }

    def cases() -> Iterator[ScoringCase]:
        for path in paths:
            try:
                records = convert_log(
                    path.read_bytes(), log_id=log_id, fallback_id=path.stem
                )
            except ConversionError as e:
                msg = f"{path}: {e}"
                raise ConversionError(msg) from e
            summary["converted_count"] += 1
            yield from records

    output.parent.mkdir(parents=True, exist_ok=True)
    return write_dataset(
        output,
        cases(),
        generator={
            "name": "majsoul-converter",
            "version": version("majsoul-converter"),
            "settings": {
                "ruleset": "majsoul-ranked-match",
                "log_id_override": log_id,
                "cases_per_file": cases_per_file,
                "compress": compress,
            },
        },
        conversion=summary,
        cases_per_file=cases_per_file,
        compress=compress,
    )

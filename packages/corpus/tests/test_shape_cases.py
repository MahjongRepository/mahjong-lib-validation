import json
from typing import TYPE_CHECKING

import pytest
from corpus import (
    CorpusError,
    check_dataset,
    file_sha256,
    parse_case,
    read_dataset,
    write_cases,
    write_dataset,
    write_manifest,
)

if TYPE_CHECKING:
    from pathlib import Path

    from corpus.models import ConversionSummary, GeneratorInfo


GENERATOR: GeneratorInfo = {"name": "test", "version": "1", "settings": {}}
CONVERSION: ConversionSummary = {
    "input_count": 2,
    "converted_count": 2,
    "failed_by_reason": {},
    "excluded_by_reason": {},
}


def _agari_record() -> dict[str, object]:
    return {
        "schema_version": "v1",
        "case_type": "agari",
        "case_id": "tenhou:example:1:agari:complete",
        "source": {
            "platform": "tenhou",
            "log_id": "example",
            "event_index": 1,
        },
        "player_count": 4,
        "input": {
            "concealed_tiles": ["1m"] * 3
            + ["2m"] * 3
            + ["3m"] * 3
            + ["4m"] * 3
            + ["5z"] * 2,
            "melds": [],
        },
        "expected": {"is_agari": True},
    }


def test_parse_completed_agari_case() -> None:
    record = _agari_record()
    assert parse_case(record) == record


@pytest.mark.parametrize("case_type", ["agari", "shanten"])
def test_shape_dataset_round_trip(tmp_path: Path, case_type: str) -> None:
    record = _agari_record()
    if case_type == "shanten":
        record.update(case_type="shanten", expected={"shanten": -1})
    case = parse_case(record)
    output = tmp_path / "dataset"
    manifest = write_dataset(
        output,
        iter([case, case]),
        generator=GENERATOR,
        conversion=CONVERSION,
        cases_per_file=1,
    )

    assert manifest["case_type"] == case_type
    assert (output / f"{case_type}-000002.jsonl.gz").is_file()
    assert check_dataset(output) == manifest
    assert list(read_dataset(output)) == [case, case]


@pytest.mark.parametrize("expected", [-1, 0, 2])
def test_valid_shanten_value(expected: int) -> None:
    record = _agari_record()
    record.update(case_type="shanten", expected={"shanten": expected})
    assert parse_case(record) == record


@pytest.mark.parametrize("expected", [-2, False])
def test_invalid_shanten_value(expected: object) -> None:
    record = _agari_record()
    record.update(case_type="shanten", expected={"shanten": expected})
    with pytest.raises(CorpusError, match=r"expected\.shanten"):
        parse_case(record)


def test_agari_checks_kan_and_effective_tile_count() -> None:
    case = parse_case(_agari_record())
    assert case["case_type"] == "agari"
    case["input"]["concealed_tiles"] = ["2p", "3p", "4p"] * 3 + ["5z"]
    case["input"]["melds"] = [
        {
            "type": "ankan",
            "tiles": ["1m"] * 4,
            "called_tile_index": None,
            "from_seat": None,
        }
    ]
    case["expected"]["is_agari"] = False
    assert parse_case(case) == case

    case["input"]["concealed_tiles"].append("1m")
    with pytest.raises(CorpusError, match="more than four copies"):
        parse_case(case)
    case["input"]["concealed_tiles"] = ["2p"] * 9
    with pytest.raises(CorpusError, match="13 or 14"):
        parse_case(case)


def test_three_player_shape_rejects_unavailable_tiles() -> None:
    record = _agari_record()
    record["player_count"] = 3
    with pytest.raises(CorpusError, match="unavailable"):
        parse_case(record)


def test_mixed_case_types_are_rejected_without_publishing(
    tmp_path: Path,
) -> None:
    agari = parse_case(_agari_record())
    record = _agari_record()
    record.update(case_type="shanten", expected={"shanten": -1})
    shanten = parse_case(record)
    output = tmp_path / "dataset"
    with pytest.raises(CorpusError, match="case_type"):
        write_dataset(
            output,
            [agari, shanten],
            generator=GENERATOR,
            conversion=CONVERSION,
            cases_per_file=1,
        )
    assert list(tmp_path.iterdir()) == []


def test_read_rejects_shard_with_different_case_type(tmp_path: Path) -> None:
    record = _agari_record()
    output = tmp_path / "dataset"
    manifest = write_dataset(
        output,
        [parse_case(record)],
        generator=GENERATOR,
        conversion=CONVERSION,
        compress=False,
    )
    record.update(case_type="shanten", expected={"shanten": -1})
    shard = output / "agari-000001.jsonl"
    write_cases(shard, [parse_case(record)])
    index = output / "files.jsonl"
    entry = {
        "path": shard.name,
        "record_count": 1,
        "sha256": file_sha256(shard),
    }
    index.write_bytes((json.dumps(entry) + "\n").encode("utf-8"))
    manifest["files_sha256"] = file_sha256(index)
    write_manifest(output / "manifest.json", manifest)

    with pytest.raises(CorpusError, match="case_type") as error:
        check_dataset(output)
    assert error.value.path == shard
    assert error.value.line == 1

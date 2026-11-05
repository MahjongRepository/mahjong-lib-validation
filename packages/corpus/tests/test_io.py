import gzip
import json
from typing import Any, cast
lazy from collections.abc import Iterator
lazy from pathlib import Path

import pytest
from corpus import (
    CorpusError,
    ScoringCase,
    parse_case,
    read_cases,
    write_cases,
)


def test_read_jsonl_preserves_order_and_real_ids(
    tmp_path: Path, example: dict[str, Any]
) -> None:
    example["source"]["log_id"] = "synthetic-unmasked-id"
    example["case_id"] = "tenhou:synthetic-unmasked-id:east:1:0:1"
    first = json.dumps(example)
    example["case_id"] = "tenhou:synthetic-unmasked-id:east:1:0:2"
    example["win_number"] = 2
    path = tmp_path / "scoring.jsonl"
    path.write_text(
        first + "\n" + json.dumps(example) + "\n", encoding="utf-8"
    )

    cases = list(read_cases(path))

    assert [case["win_number"] for case in cases] == [1, 2]
    assert cases[0]["source"]["log_id"] == "synthetic-unmasked-id"
    assert cases[0]["case_id"] == "tenhou:synthetic-unmasked-id:east:1:0:1"
    assert cases[0]["expected"]["fu"] == 40


@pytest.mark.parametrize("bad_line", ["not json", "", "{}"])
def test_read_is_lazy_and_errors_identify_line(
    tmp_path: Path, example: dict[str, Any], bad_line: str
) -> None:
    path = tmp_path / "broken.jsonl"
    path.write_text(
        json.dumps(example) + "\n" + bad_line + "\n", encoding="utf-8"
    )
    cases = read_cases(path)
    assert next(cases)["case_id"] == example["case_id"]
    with pytest.raises(CorpusError) as error:
        next(cases)
    assert error.value.path == path
    assert error.value.line == 2
    assert str(path) in str(error.value)


def test_iterable_failure_leaves_no_partial_output(
    tmp_path: Path, example: dict[str, Any]
) -> None:
    def failing_cases() -> Iterator[ScoringCase]:
        yield parse_case(example)
        message = "source failed"
        raise RuntimeError(message)

    path = tmp_path / "new.jsonl.gz"
    with pytest.raises(RuntimeError, match="source failed"):
        write_cases(path, failing_cases())
    assert not path.exists()
    assert list(tmp_path.iterdir()) == []


def test_write_matches_explicit_json(
    tmp_path: Path, example: dict[str, Any]
) -> None:
    example["source"]["log_id"] = "合成牌譜ID"
    path = tmp_path / "written.jsonl"
    write_cases(path, [parse_case(example)])

    raw = path.read_bytes()
    assert raw.endswith(b"\n")
    assert len(raw.splitlines()) == 1
    assert "合成牌譜ID" in raw.decode("utf-8")
    assert json.loads(raw) == example


def test_invalid_later_case_does_not_replace_existing_file(
    tmp_path: Path, example: dict[str, Any]
) -> None:
    path = tmp_path / "existing.jsonl"
    path.write_bytes(b"previous complete corpus\n")
    valid = parse_case(example)
    with pytest.raises(CorpusError):
        write_cases(path, [valid, cast("ScoringCase", {})])
    assert path.read_bytes() == b"previous complete corpus\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["existing.jsonl"]


def test_gzip_reads_and_writes_explicit_json(
    tmp_path: Path, example: dict[str, Any]
) -> None:
    input_path = tmp_path / "input.jsonl.gz"
    input_path.write_bytes(
        gzip.compress((json.dumps(example) + "\n").encode())
    )
    assert list(read_cases(input_path)) == [example]

    output_path = tmp_path / "output.jsonl.gz"
    write_cases(output_path, [parse_case(example)])
    assert output_path.read_bytes().startswith(b"\x1f\x8b")
    assert json.loads(gzip.decompress(output_path.read_bytes())) == example


@pytest.mark.parametrize("suffix", [".jsonl", ".jsonl.gz"])
def test_title_survives_jsonl_round_trip(
    tmp_path: Path, example: dict[str, Any], suffix: str
) -> None:
    example["expected"]["title"] = "mangan"
    path = tmp_path / ("titles" + suffix)
    write_cases(path, [parse_case(example)])
    cases = list(read_cases(path))
    assert cases[0]["expected"]["title"] == "mangan"


def test_invalid_utf8_reports_the_line(
    tmp_path: Path, example: dict[str, Any]
) -> None:
    path = tmp_path / "encoding.jsonl"
    path.write_bytes(json.dumps(example).encode() + b"\n\xff\n")
    cases = read_cases(path)
    assert next(cases)["expected"]["fu"] == 40
    with pytest.raises(CorpusError) as error:
        next(cases)
    assert error.value.path == path
    assert error.value.line == 2

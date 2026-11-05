import gzip
import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
lazy from collections.abc import Iterator

import pytest
from corpus import (
    CorpusError,
    check_dataset,
    parse_case,
    read_dataset,
    write_dataset,
)

if TYPE_CHECKING:
    from corpus.models import ConversionSummary, ScoringCase


@pytest.fixture
def dataset(tmp_path: Path) -> Path:
    fixtures = Path(__file__).parent / "fixtures"
    files = []
    for fixture, name in [
        ("tenhou-scoring.json", "z.jsonl"),
        ("majsoul-scoring.json", "a.jsonl.gz"),
    ]:
        value = json.loads((fixtures / fixture).read_text(encoding="utf-8"))
        content = (json.dumps(value) + "\n").encode("utf-8")
        if name.endswith(".gz"):
            content = gzip.compress(content)
        (tmp_path / name).write_bytes(content)
        files.append(
            {
                "path": name,
                "record_count": 1,
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    manifest = {
        "schema_version": "v1",
        "case_type": "scoring",
        "generator": {"name": "test", "version": "1", "settings": {}},
        "conversion": {
            "input_count": 2,
            "converted_count": 2,
            "failed_by_reason": {},
            "excluded_by_reason": {},
        },
        "record_count": 2,
        "files": files,
    }
    _save_manifest(tmp_path, manifest)
    return tmp_path


def _load_manifest(directory: Path) -> dict[str, Any]:
    return json.loads(
        (directory / "manifest.json").read_text(encoding="utf-8")
    )


def _save_manifest(directory: Path, value: dict[str, Any]) -> None:
    (directory / "manifest.json").write_text(
        json.dumps(value), encoding="utf-8"
    )


def test_read_dataset_uses_manifest_order(dataset: Path) -> None:
    cases = list(read_dataset(dataset))
    assert [case["source"]["platform"] for case in cases] == [
        "tenhou",
        "majsoul",
    ]
    assert [case["expected"]["winner_gain"] for case in cases] == [3600, 4600]


def test_check_dataset_consumes_every_file(dataset: Path) -> None:
    manifest = check_dataset(dataset)
    assert manifest["record_count"] == 2
    (dataset / "a.jsonl.gz").write_bytes(b"corrupted")
    with pytest.raises(CorpusError) as error:
        check_dataset(dataset)
    assert error.value.field == "files[1].sha256"


def test_hash_is_checked_before_yielding_file_cases(dataset: Path) -> None:
    path = dataset / "z.jsonl"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(CorpusError) as error:
        next(read_dataset(dataset))
    assert error.value.field == "files[0].sha256"


def test_missing_data_file_is_reported(dataset: Path) -> None:
    (dataset / "z.jsonl").unlink()
    with pytest.raises(CorpusError) as error:
        list(read_dataset(dataset))
    assert error.value.field == "files[0].path"


def test_record_count_is_checked_at_file_end(dataset: Path) -> None:
    manifest = _load_manifest(dataset)
    manifest["files"][0]["record_count"] = 2
    manifest["record_count"] = 3
    _save_manifest(dataset, manifest)
    cases = read_dataset(dataset)
    assert next(cases)["source"]["platform"] == "tenhou"
    with pytest.raises(CorpusError) as error:
        next(cases)
    assert error.value.field == "files[0].record_count"


def test_failed_conversion_is_not_a_complete_dataset(dataset: Path) -> None:
    manifest = _load_manifest(dataset)
    manifest["conversion"]["input_count"] = 3
    manifest["conversion"]["failed_by_reason"] = {"invalid_log": 1}
    _save_manifest(dataset, manifest)
    with pytest.raises(CorpusError) as error:
        next(read_dataset(dataset))
    assert error.value.field == "conversion.failed_by_reason"


def test_data_symlink_must_not_leave_dataset(dataset: Path) -> None:
    path = dataset / "z.jsonl"
    external = dataset.parent / "external.jsonl"
    external.write_bytes(path.read_bytes())
    path.unlink()
    try:
        path.symlink_to(external)
    except OSError as error:
        pytest.skip(f"file symlinks are unavailable: {error}")
    with pytest.raises(CorpusError) as error:
        list(read_dataset(dataset))
    assert error.value.field == "files[0].path"


def test_resolved_file_target_must_stay_in_dataset(
    dataset: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_resolve = Path.resolve

    def resolved(path: Path, *, strict: bool = False) -> Path:
        if path == dataset / "z.jsonl":
            return dataset.parent / "external.jsonl"
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", resolved)
    with pytest.raises(CorpusError) as error:
        next(read_dataset(dataset))
    assert error.value.field == "files[0].path"


def test_bad_case_is_detected_even_with_matching_hash(dataset: Path) -> None:
    path = dataset / "z.jsonl"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["input"]["winning_tile"] = "0z"
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")
    manifest = _load_manifest(dataset)
    manifest["files"][0]["sha256"] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    _save_manifest(dataset, manifest)
    with pytest.raises(CorpusError) as error:
        list(read_dataset(dataset))
    assert error.value.field == "input.winning_tile"
    assert error.value.path == path
    assert error.value.line == 1


def test_write_dataset_shards_and_hashes_saved_bytes(
    tmp_path: Path, example: dict[str, Any]
) -> None:
    path = tmp_path / "corpus"
    case = parse_case(example)
    manifest = write_dataset(
        path,
        iter([case, case, case]),
        generator={"name": "test", "version": "1", "settings": {}},
        conversion={
            "input_count": 1,
            "converted_count": 1,
            "failed_by_reason": {},
            "excluded_by_reason": {},
        },
        cases_per_file=2,
        compress=False,
    )
    assert [entry["record_count"] for entry in manifest["files"]] == [2, 1]
    assert [entry["path"] for entry in manifest["files"]] == [
        "scoring-000001.jsonl",
        "scoring-000002.jsonl",
    ]
    assert manifest["record_count"] == 3
    for entry in manifest["files"]:
        assert (
            entry["sha256"]
            == hashlib.sha256((path / entry["path"]).read_bytes()).hexdigest()
        )
    assert check_dataset(path) == manifest
    assert list(read_dataset(path)) == [case, case, case]


def test_existing_dataset_is_rejected_without_consuming_input(
    dataset: Path, example: dict[str, Any]
) -> None:
    consumed = False

    def cases() -> Iterator[ScoringCase]:
        nonlocal consumed
        consumed = True
        yield parse_case(example)

    previous = (dataset / "manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        write_dataset(
            dataset,
            cases(),
            generator={"name": "test", "version": "1", "settings": {}},
            conversion={
                "input_count": 1,
                "converted_count": 1,
                "failed_by_reason": {},
                "excluded_by_reason": {},
            },
        )
    assert consumed is False
    assert (dataset / "manifest.json").read_bytes() == previous


def test_empty_input_is_not_published(tmp_path: Path) -> None:
    path = tmp_path / "empty"
    with pytest.raises(CorpusError, match="files"):
        write_dataset(
            path,
            [],
            generator={"name": "test", "version": "1", "settings": {}},
            conversion={
                "input_count": 1,
                "converted_count": 1,
                "failed_by_reason": {},
                "excluded_by_reason": {},
            },
        )
    assert list(tmp_path.iterdir()) == []


def test_input_failure_does_not_publish_partial_dataset(
    tmp_path: Path, example: dict[str, Any]
) -> None:
    def cases() -> Iterator[ScoringCase]:
        yield parse_case(example)
        message = "conversion interrupted"
        raise RuntimeError(message)

    with pytest.raises(RuntimeError, match="conversion interrupted"):
        write_dataset(
            tmp_path / "partial",
            cases(),
            cases_per_file=1,
            generator={"name": "test", "version": "1", "settings": {}},
            conversion={
                "input_count": 1,
                "converted_count": 1,
                "failed_by_reason": {},
                "excluded_by_reason": {},
            },
        )
    assert list(tmp_path.iterdir()) == []


def test_compressed_dataset_hashes_gzip_bytes(
    tmp_path: Path, example: dict[str, Any]
) -> None:
    path = tmp_path / "gzip"
    manifest = write_dataset(
        path,
        [parse_case(example), parse_case(example)],
        cases_per_file=2,
        generator={"name": "test", "version": "1", "settings": {}},
        conversion={
            "input_count": 1,
            "converted_count": 1,
            "failed_by_reason": {},
            "excluded_by_reason": {},
        },
    )
    assert len(manifest["files"]) == 1
    content = (path / manifest["files"][0]["path"]).read_bytes()
    assert content.startswith(b"\x1f\x8b")
    assert (
        manifest["files"][0]["sha256"] == hashlib.sha256(content).hexdigest()
    )
    assert check_dataset(path)["record_count"] == 2


def test_conversion_summary_can_be_finalized_while_streaming(
    tmp_path: Path, example: dict[str, Any]
) -> None:
    summary: ConversionSummary = {
        "input_count": 1,
        "converted_count": 0,
        "failed_by_reason": {},
        "excluded_by_reason": {},
    }

    def cases() -> Iterator[ScoringCase]:
        yield parse_case(example)
        summary["converted_count"] = 1

    manifest = write_dataset(
        tmp_path / "streamed",
        cases(),
        conversion=summary,
        generator={"name": "test", "version": "1", "settings": {}},
    )
    assert manifest["conversion"]["converted_count"] == 1


def test_failure_reported_at_end_of_stream_prevents_publication(
    tmp_path: Path, example: dict[str, Any]
) -> None:
    summary: ConversionSummary = {
        "input_count": 1,
        "converted_count": 1,
        "failed_by_reason": {},
        "excluded_by_reason": {},
    }

    def cases() -> Iterator[ScoringCase]:
        yield parse_case(example)
        summary["input_count"] = 2
        summary["failed_by_reason"] = {"invalid_log": 1}

    with pytest.raises(CorpusError, match=r"conversion\.failed_by_reason"):
        write_dataset(
            tmp_path / "partial",
            cases(),
            conversion=summary,
            generator={"name": "test", "version": "1", "settings": {}},
        )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("limit", [0, -1, True])
def test_invalid_shard_size_is_rejected(tmp_path: Path, limit: int) -> None:
    with pytest.raises(CorpusError, match="cases_per_file"):
        write_dataset(
            tmp_path / "invalid",
            [],
            cases_per_file=limit,
            generator={"name": "test", "version": "1", "settings": {}},
            conversion={
                "input_count": 1,
                "converted_count": 1,
                "failed_by_reason": {},
                "excluded_by_reason": {},
            },
        )
    assert list(tmp_path.iterdir()) == []


def test_empty_manifest_is_not_a_successful_dataset(dataset: Path) -> None:
    manifest = _load_manifest(dataset)
    manifest["files"] = []
    manifest["record_count"] = 0
    manifest["conversion"] = {
        "input_count": 0,
        "converted_count": 0,
        "failed_by_reason": {},
        "excluded_by_reason": {},
    }
    _save_manifest(dataset, manifest)
    with pytest.raises(CorpusError, match="files"):
        list(read_dataset(dataset))
    with pytest.raises(CorpusError, match="files"):
        check_dataset(dataset)

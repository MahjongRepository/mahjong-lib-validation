import json
from pathlib import Path
from typing import Any

import pytest
from corpus import CorpusError, parse_manifest, read_manifest, write_manifest


@pytest.fixture
def manifest_value() -> dict[str, Any]:
    return {
        "schema_version": "v1",
        "case_type": "scoring",
        "generator": {
            "name": "test-converter",
            "version": "1",
            "settings": {},
        },
        "conversion": {
            "input_count": 1,
            "converted_count": 1,
            "failed_by_reason": {},
            "excluded_by_reason": {},
        },
        "record_count": 2,
        "files": [
            {
                "path": "scoring-000001.jsonl",
                "record_count": 2,
                "sha256": "a" * 64,
            }
        ],
    }


def test_parse_manifest(manifest_value: dict[str, Any]) -> None:
    manifest = parse_manifest(manifest_value)

    assert manifest["record_count"] == 2
    assert manifest["generator"]["name"] == "test-converter"
    assert manifest["files"][0]["path"] == "scoring-000001.jsonl"
    assert manifest == manifest_value


@pytest.mark.parametrize("count", [0, -1, 3])
def test_manifest_total_must_match_files(
    manifest_value: dict[str, Any], count: int
) -> None:
    manifest_value["record_count"] = count
    with pytest.raises(CorpusError) as error:
        parse_manifest(manifest_value)
    assert error.value.field == "record_count"


def test_conversion_tracks_logs_separately_from_cases(
    manifest_value: dict[str, Any],
) -> None:
    manifest_value["conversion"] = {
        "input_count": 3,
        "converted_count": 1,
        "failed_by_reason": {"invalid_xml": 1},
        "excluded_by_reason": {"unsupported_rules": 1},
    }
    assert parse_manifest(manifest_value)["record_count"] == 2


def test_conversion_counts_must_account_for_every_input(
    manifest_value: dict[str, Any],
) -> None:
    manifest_value["conversion"]["input_count"] = 2
    with pytest.raises(CorpusError) as error:
        parse_manifest(manifest_value)
    assert error.value.field == "conversion.input_count"


@pytest.mark.parametrize(
    ("reason", "count"), [("", 1), ("bad_xml", 0), ("bad_xml", -1)]
)
def test_invalid_conversion_reason_counts(
    manifest_value: dict[str, Any], reason: str, count: int
) -> None:
    manifest_value["conversion"]["failed_by_reason"] = {reason: count}
    manifest_value["conversion"]["input_count"] += count
    with pytest.raises(CorpusError, match=r"conversion\.failed_by_reason"):
        parse_manifest(manifest_value)


@pytest.mark.parametrize(
    "name",
    [
        "../a.jsonl",
        "/a.jsonl",
        "sub/a.jsonl",
        r"sub\a.jsonl",
        "C:a.jsonl",
        "manifest.json",
    ],
)
def test_reject_unsafe_data_file_names(
    manifest_value: dict[str, Any], name: str
) -> None:
    manifest_value["files"][0]["path"] = name
    with pytest.raises(CorpusError) as error:
        parse_manifest(manifest_value)
    assert error.value.field == "files[0].path"


def test_reject_duplicate_files(manifest_value: dict[str, Any]) -> None:
    manifest_value["files"].append(manifest_value["files"][0].copy())
    manifest_value["record_count"] = 4
    with pytest.raises(CorpusError, match="files"):
        parse_manifest(manifest_value)


def test_file_names_cannot_collide_on_case_insensitive_systems(
    manifest_value: dict[str, Any],
) -> None:
    other = manifest_value["files"][0].copy()
    other["path"] = "SCORING-000001.jsonl"
    manifest_value["files"].append(other)
    manifest_value["record_count"] = 4
    with pytest.raises(CorpusError) as error:
        parse_manifest(manifest_value)
    assert error.value.field == "files[1].path"


@pytest.mark.parametrize("digest", ["", "a" * 63, "g" * 64, "A" * 64])
def test_reject_invalid_sha256(
    manifest_value: dict[str, Any], digest: str
) -> None:
    manifest_value["files"][0]["sha256"] = digest
    with pytest.raises(CorpusError) as error:
        parse_manifest(manifest_value)
    assert error.value.field == "files[0].sha256"


def test_manifest_schema_and_settings_are_checked(
    manifest_value: dict[str, Any],
) -> None:
    manifest_value["schema_version"] = "v2"
    with pytest.raises(CorpusError, match="schema_version"):
        parse_manifest(manifest_value)
    manifest_value["schema_version"] = "v1"
    manifest_value["generator"]["settings"]["bad"] = float("nan")
    with pytest.raises(CorpusError, match=r"generator\.settings\.bad"):
        parse_manifest(manifest_value)


def test_manifest_io_matches_explicit_json(
    tmp_path: Path, manifest_value: dict[str, Any]
) -> None:
    path = tmp_path / "manifest.json"
    manifest_value["generator"]["settings"] = {"description": "合成テスト"}
    path.write_text(json.dumps(manifest_value), encoding="utf-8")
    manifest = read_manifest(path)
    assert manifest == manifest_value
    write_manifest(path, manifest)
    assert json.loads(path.read_text(encoding="utf-8")) == manifest_value
    assert "合成テスト" in path.read_text(encoding="utf-8")


def test_invalid_manifest_reports_its_path(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text('{\n"schema_version":', encoding="utf-8")
    with pytest.raises(CorpusError) as error:
        read_manifest(path)
    assert error.value.path == path
    assert error.value.line == 2


def test_empty_failed_manifest_can_be_kept_for_diagnostics(
    manifest_value: dict[str, Any],
) -> None:
    manifest_value["files"] = []
    manifest_value["record_count"] = 0
    manifest_value["conversion"] = {
        "input_count": 1,
        "converted_count": 0,
        "failed_by_reason": {"invalid_log": 1},
        "excluded_by_reason": {},
    }
    manifest = parse_manifest(manifest_value)
    assert manifest["record_count"] == 0
    assert manifest["conversion"]["failed_by_reason"] == {"invalid_log": 1}

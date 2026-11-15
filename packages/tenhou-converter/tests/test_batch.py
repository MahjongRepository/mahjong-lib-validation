import gzip
import json
from pathlib import Path
from typing import cast

import pytest
from corpus import read_dataset
from tenhou_converter import BatchConversionError, convert_files
from tenhou_converter.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_report_io_failure_retains_the_actual_publication_state(
    tmp_path: Path,
) -> None:
    blocked = tmp_path / "blocked"
    blocked.write_text("file", encoding="utf-8")
    output = tmp_path / "output"
    with pytest.raises(BatchConversionError) as caught:
        convert_files(
            FIXTURES / "four-ron.xml",
            output,
            report_path=blocked / "report.json",
        )
    assert caught.value.report["dataset_published"] is True
    assert output.is_dir()
    assert "report_io_error" in (caught.value.report["error"] or "")


def test_existing_output_is_rejected_before_missing_input_is_read(
    tmp_path: Path,
) -> None:
    output = tmp_path / "output"
    output.mkdir()
    with pytest.raises(FileExistsError):
        convert_files(tmp_path / "missing.xml", output)


@pytest.mark.parametrize(
    ("cases_per_file", "compress"),
    [
        (True, True),
        (1.5, True),
        ("1", True),
        (0, True),
        (-1, True),
        (1, 0),
        (1, "true"),
        (1, None),
    ],
    ids=[
        "boolean-size",
        "float-size",
        "string-size",
        "zero-size",
        "negative-size",
        "integer-compress",
        "string-compress",
        "null-compress",
    ],
)
def test_invalid_output_options_are_rejected_before_input_or_output_io(
    tmp_path: Path, cases_per_file: object, compress: object
) -> None:
    with pytest.raises(ValueError) as caught:  # noqa: PT011 -- message wording is not a contract
        convert_files(
            tmp_path / "missing.xml",
            tmp_path / "new" / "output",
            cases_per_file=cast("int", cases_per_file),
            compress=cast("bool", compress),
            report_path=tmp_path / "report.json",
        )

    assert type(caught.value) is ValueError
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("compress", [False, True])
def test_output_options_accept_minimum_shard_size(
    tmp_path: Path, *, compress: bool
) -> None:
    output = tmp_path / "output"

    manifest = convert_files(
        FIXTURES / "four-ron.xml", output, cases_per_file=1, compress=compress
    )

    assert manifest["record_count"] == 1
    assert manifest["files"][0]["record_count"] == 1
    expected_suffix = ".jsonl.gz" if compress else ".jsonl"
    assert manifest["files"][0]["path"].endswith(expected_suffix)
    assert len(list(read_dataset(output))) == 1


def test_corrupt_gzip_is_a_reported_input_failure(tmp_path: Path) -> None:
    source = tmp_path / "bad.xml.gz"
    source.write_bytes(b"not gzip")
    with pytest.raises(BatchConversionError) as caught:
        convert_files(source, tmp_path / "output")
    assert caught.value.report["conversion"]["failed_by_reason"] == {
        "input_io_error": 1
    }
    assert caught.value.report["dataset_published"] is False
    (diagnostic,) = caught.value.report["diagnostics"]
    assert diagnostic["path"] == str(source)
    assert diagnostic["log_id"] == "bad"
    assert diagnostic["reason"] == "input_io_error"
    assert diagnostic["event_index"] is None
    assert diagnostic["field"] is None


@pytest.mark.parametrize("encoding", ["nonexistent-encoding", "utf-7"])
def test_encoding_error_reports_failure_and_continues_batch(
    tmp_path: Path,
    encoding: str,
) -> None:
    source = tmp_path / "input"
    source.mkdir()
    (source / "a.xml").write_bytes(
        (
            f'<?xml version="1.0" encoding="{encoding}"?><mjloggm ver="2.3"/>'
        ).encode("ascii")
    )
    (source / "b.xml").write_bytes((FIXTURES / "four-ron.xml").read_bytes())
    output = tmp_path / "output"
    report_path = tmp_path / "report.json"

    assert (
        main(
            [
                "mjlog",
                str(source),
                "--output",
                str(output),
                "--report",
                str(report_path),
            ]
        )
        == 1
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["conversion"] == {
        "input_count": 2,
        "converted_count": 1,
        "failed_by_reason": {"invalid_xml": 1},
        "excluded_by_reason": {},
    }
    assert report["record_count"] == 1
    assert report["summary_complete"] is True
    assert report["dataset_published"] is False
    (diagnostic,) = report["diagnostics"]
    assert diagnostic["path"] == str(source / "a.xml")
    assert diagnostic["reason"] == "invalid_xml"
    assert not output.exists()
    assert not list(tmp_path.glob(".corpus-*"))


def test_successful_logs_without_wins_count_but_cannot_publish_empty_dataset(
    tmp_path: Path,
) -> None:
    with pytest.raises(BatchConversionError) as caught:
        convert_files(FIXTURES / "sanma-ryuukyoku.xml", tmp_path / "output")
    assert caught.value.report["conversion"]["converted_count"] == 1
    assert caught.value.report["conversion"]["failed_by_reason"] == {}
    assert caught.value.report["summary_complete"] is True
    assert not (tmp_path / "output").exists()


def test_late_failure_reports_all_inputs_without_publishing(
    tmp_path: Path,
) -> None:
    source = tmp_path / "input"
    source.mkdir()
    (source / "a.xml").write_bytes((FIXTURES / "four-ron.xml").read_bytes())
    (source / "b.xml").write_bytes(b"<broken")
    (source / "c.xml").write_bytes((FIXTURES / "sanma-tsumo.xml").read_bytes())
    output = tmp_path / "output"
    with pytest.raises(BatchConversionError) as caught:
        convert_files(source, output, cases_per_file=1)
    assert not output.exists()
    assert not list(tmp_path.glob(".corpus-*"))
    report = caught.value.report
    assert report["summary_complete"] is True
    assert report["conversion"] == {
        "input_count": 3,
        "converted_count": 2,
        "failed_by_reason": {"invalid_xml": 1},
        "excluded_by_reason": {},
    }
    assert report["diagnostics"][0]["log_id"] == "b"


def test_attribute_failure_preserves_diagnostic_location(
    tmp_path: Path,
) -> None:
    source = tmp_path / "bad.xml"
    source.write_bytes(
        (FIXTURES / "four-ron.xml")
        .read_bytes()
        .replace(b'type="41"', b'type="x"')
    )

    with pytest.raises(BatchConversionError) as caught:
        convert_files(source, tmp_path / "output")

    report = caught.value.report
    assert report["conversion"]["failed_by_reason"] == {"invalid_attribute": 1}
    (diagnostic,) = report["diagnostics"]
    assert diagnostic["reason"] == "invalid_attribute"
    assert diagnostic["event_index"] == 1
    assert diagnostic["field"] == "type"
    assert diagnostic["message"] == (
        "invalid_attribute: expected integer list (event=1, field=type)"
    )


@pytest.mark.parametrize(
    "name", ["game.mjlog", "game.xml.gz", "game.mjlog.gz", "game.XML.GZ"]
)
def test_gzip_detection_and_id_suffixes(tmp_path: Path, name: str) -> None:
    source = tmp_path / name
    source.write_bytes(gzip.compress((FIXTURES / "four-ron.xml").read_bytes()))
    output = tmp_path / "output"
    convert_files(source, output, compress=False)
    (case,) = read_dataset(output)
    assert case["source"]["log_id"] == "game"
    assert (output / "scoring-000001.jsonl").exists()


def test_cli_exit_codes_and_json_report(tmp_path: Path) -> None:
    output = tmp_path / "output"
    report = tmp_path / "report.json"
    assert (
        main(
            [
                "mjlog",
                str(FIXTURES / "sanma-three-nuki.xml"),
                "--output",
                str(output),
                "--report",
                str(report),
            ]
        )
        == 0
    )
    (case,) = read_dataset(output)
    assert case["input"]["nuki_count"] == 3
    assert case["round"]["wind"] == "south"
    assert case["expected"]["honba_points"] == 600
    assert (
        json.loads(report.read_text(encoding="utf-8"))["dataset_published"]
        is True
    )
    assert (
        main(
            ["mjlog", str(FIXTURES / "four-ron.xml"), "--output", str(output)]
        )
        == 1
    )
    with pytest.raises(SystemExit) as caught:
        main(
            [
                "mjlog",
                str(FIXTURES),
                "--output",
                str(tmp_path / "new"),
                "--cases-per-file",
                "0",
            ]
        )
    assert caught.value.code == 2


@pytest.mark.parametrize(
    ("game_type", "lobby"),
    [(40, 0), (43, 0), (41, 1)],
    ids=["computer-opponents", "unsupported-flags", "private-lobby"],
)
def test_known_unsupported_rules_are_counted_as_exclusions(
    tmp_path: Path,
    game_type: int,
    lobby: int,
) -> None:
    source = tmp_path / "input"
    source.mkdir()
    xml = (FIXTURES / "four-ron.xml").read_bytes()
    unsupported = xml.replace(b'type="41"', f'type="{game_type}"'.encode())
    unsupported = unsupported.replace(
        b'lobby="0"', f'lobby="{lobby}"'.encode()
    )
    (source / "a.xml").write_bytes(unsupported)
    (source / "b.xml").write_bytes(xml)
    manifest = convert_files(source, tmp_path / "output")
    assert manifest["conversion"]["excluded_by_reason"] == {
        "unsupported_rules": 1
    }
    assert manifest["record_count"] == 1


def test_duplicate_log_ids_are_rejected_before_output(tmp_path: Path) -> None:
    source = tmp_path / "input"
    source.mkdir()
    for name in ("same.xml", "same.mjlog"):
        (source / name).write_bytes((FIXTURES / "four-ron.xml").read_bytes())
    with pytest.raises(ValueError, match="duplicate_log_id"):
        convert_files(source, tmp_path / "output")


def test_existing_report_and_nested_output_are_rejected(
    tmp_path: Path,
) -> None:
    source = tmp_path / "input"
    source.mkdir()
    (source / "a.xml").write_bytes((FIXTURES / "four-ron.xml").read_bytes())
    with pytest.raises(ValueError, match="outside input"):
        convert_files(source, source / "output")
    report = tmp_path / "report.json"
    report.write_text("original", encoding="utf-8")
    with pytest.raises(FileExistsError):
        convert_files(source, tmp_path / "output", report_path=report)
    assert report.read_text(encoding="utf-8") == "original"

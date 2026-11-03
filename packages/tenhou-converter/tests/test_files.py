import json
from pathlib import Path

from corpus import check_dataset, read_dataset
from tenhou_converter import convert_files

FIXTURES = Path(__file__).parent / "fixtures"


def test_files_publish_checked_shards_and_report(tmp_path: Path) -> None:
    source = tmp_path / "input"
    source.mkdir()
    (source / "b.xml").write_bytes((FIXTURES / "sanma-tsumo.xml").read_bytes())
    (source / "a.xml").write_bytes((FIXTURES / "four-ron.xml").read_bytes())
    output = tmp_path / "output"
    report = tmp_path / "report.json"
    manifest = convert_files(
        source, output, cases_per_file=1, report_path=report
    )
    assert manifest == check_dataset(output)
    assert manifest["record_count"] == 2
    assert len(manifest["files"]) == 2
    assert manifest["conversion"]["converted_count"] == 2
    assert [case["source"]["log_id"] for case in read_dataset(output)] == [
        "a",
        "b",
    ]
    assert (
        json.loads(report.read_text(encoding="utf-8"))["dataset_published"]
        is True
    )

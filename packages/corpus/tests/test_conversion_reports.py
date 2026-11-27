import json
lazy from pathlib import Path

import pytest
from corpus.conversion_reports import (
    Diagnostic,
    new_report,
    record_diagnostic,
    write_report,
)
lazy from corpus.models import GeneratorInfo


def test_counts_include_omitted_diagnostics(tmp_path: Path) -> None:
    generator: GeneratorInfo = {"name": "test", "version": "1", "settings": {}}
    source, output = tmp_path / "input", tmp_path / "output"
    report = new_report(source, output, generator=generator)
    fresh = new_report(source, output, generator=generator)
    diagnostic: Diagnostic = {
        "path": str(source),
        "log_id": "game",
        "reason": "invalid_log",
        "message": "不正なログ",
        "event_index": 3,
        "field": "event",
    }
    for _ in range(101):
        record_diagnostic(report, diagnostic, excluded=False)
    record_diagnostic(report, diagnostic, excluded=True)

    assert report["conversion"]["failed_by_reason"] == {"invalid_log": 101}
    assert report["conversion"]["excluded_by_reason"] == {"invalid_log": 1}
    assert report["diagnostics"] == [diagnostic] * 100
    assert report["omitted_diagnostic_count"] == 2
    assert fresh["conversion"]["failed_by_reason"] == {}
    assert fresh["diagnostics"] == []

    path = tmp_path / "reports" / "report.json"
    write_report(path, report)
    content = path.read_text(encoding="utf-8")
    assert json.loads(content) == report
    assert "不正なログ" in content
    assert content.endswith("\n")
    with pytest.raises(FileExistsError):
        write_report(path, fresh)
    assert path.read_text(encoding="utf-8") == content

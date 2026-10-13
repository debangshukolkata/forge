from __future__ import annotations

from report import build_report, load


def test_report_lists_weeks_and_total(tmp_path) -> None:
    path = tmp_path / "w.yaml"
    path.write_text(
        "weeks:\n  - {start: '2024-03-04', sales: 120}\n  - {start: 2024-03-11, sales: 80}\n",
        encoding="utf-8",
    )
    text = build_report(load(str(path)))
    assert "2024-03-04" in text and "Mar 11" in text and "Total: 200" in text

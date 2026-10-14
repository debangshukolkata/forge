"""D-357: the document benchmark's checks pass on outputs made by DebCraft's own tools and fail on poor ones (no model involved)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("docx")
pytest.importorskip("openpyxl")
pytest.importorskip("pypdf")
pytest.importorskip("reportlab")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "benchmark"))
import run_document_benchmark as bench


def _workspace(tmp_path: Path) -> Path:
    (tmp_path / "project").mkdir()
    return tmp_path


def test_a_good_word_summary_passes_and_an_empty_workspace_fails(tmp_path: Path) -> None:
    from forge.documents.build import build_document
    from forge.documents.spec import parse_document

    assert not bench.check_w01(_workspace(tmp_path))["delivered"]
    outline = {
        "title": "Sales summary",
        "blocks": [
            {"type": "heading", "text": "Summary"},
            {"type": "paragraph", "text": "Total revenue was 734,850, led by West with 294,750."},
            {"type": "heading", "text": "Revenue by region"},
            {
                "type": "table",
                "header": ["Region", "Q1", "Q2"],
                "rows": [
                    ["North", "120400", "133900"],
                    ["South", "98200", "87600"],
                    ["West", "143000", "151750"],
                ],
            },
            {"type": "bullets", "items": ["West grew", "South fell"]},
        ],
    }
    (tmp_path / "project" / "sales-summary.docx").write_bytes(
        build_document(parse_document(json.dumps(outline)), lambda n: b"")
    )
    result = bench.check_w01(tmp_path)
    assert result["checks_failed"] == [], result


def test_a_good_workbook_and_a_pdf_pass(tmp_path: Path) -> None:
    from forge.pdfs.build import build_pdf, parse_pdf_spec
    from forge.sheets.build import build_workbook
    from forge.sheets.spec import parse_workbook

    workspace = _workspace(tmp_path)
    outline = {
        "sheets": [
            {
                "name": "Data",
                "columns": [{"header": "Product"}, {"header": "Amount", "format": "#,##0.00"}],
                "rows": [["Kettle", 1200.5], ["Toaster", -300], ["Blender", 950]],
                "total_row": {"A": "Total", "B": "SUM"},
                "charts": [
                    {
                        "type": "column",
                        "title": "Amount",
                        "data": "B1:B4",
                        "categories": "A2:A4",
                        "anchor": "E2",
                    }
                ],
            }
        ]
    }
    (workspace / "project" / "orders.xlsx").write_bytes(build_workbook(parse_workbook(json.dumps(outline))))
    result = bench.check_w02(workspace)
    assert result["checks_failed"] == [], result
    spec = {
        "title": "Volunteer day",
        "blocks": [
            {
                "type": "paragraph",
                "text": "Saturday 14 June at Riverside Park, meet at the boathouse. Bring gloves.",
            },
            {
                "type": "table",
                "header": ["Time", "What"],
                "rows": [["9:00", "Welcome and safety talk"], ["13:30", "Planting"]],
            },
            {"type": "paragraph", "text": "Maya, 0113 555 0142, volunteers@riverside.example"},
        ],
    }
    (workspace / "project" / "handout.pdf").write_bytes(
        build_pdf(parse_pdf_spec(json.dumps(spec)), lambda n: b"")
    )
    assert bench.check_w03(workspace)["checks_failed"] == []

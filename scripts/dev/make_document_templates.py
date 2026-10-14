"""Makes the document templates that ship with the skills (TODO W4, D-347): three Word templates (.docx with styles, header, footer) and
the starting outlines for a workbook and a PDF. Run it again after changing the builders:

    .venv\\Scripts\\python scripts/dev/make_document_templates.py

Pictures of the Word templates (Word prints them) go to `assets/preview/`. Then run `scripts/build_asset_catalogue.py <skill folder>`."""

from __future__ import annotations

import json
from pathlib import Path

from forge.documents.build import build_document
from forge.documents.preview import PreviewUnavailable, to_pdf
from forge.documents.spec import parse_document

SKILLS = Path(__file__).resolve().parents[2] / "src" / "forge" / "skills"

REPORT = {
    "title": "Quarterly report",
    "language": "en-GB",
    "header": "Company name | Confidential",
    "footer": "Prepared by the finance team",
    "brand": {"accent": "1F3864", "text": "262626", "title_font": "Georgia", "body_font": "Calibri"},
    "blocks": [
        {"type": "heading", "level": 1, "text": "Summary"},
        {
            "type": "paragraph",
            "text": "State the one thing the reader should know or do, with the number that proves it.",
        },
        {"type": "heading", "level": 1, "text": "Results"},
        {
            "type": "table",
            "header": ["Measure", "This quarter", "Last quarter"],
            "rows": [["Revenue", "4.2m", "3.8m"], ["Margin", "31%", "29%"]],
            "caption": "Table 1: Key figures",
        },
        {"type": "heading", "level": 1, "text": "Next steps"},
        {"type": "numbered", "items": ["First action, owner, date", "Second action, owner, date"]},
    ],
}
MEMO = {
    "title": "Memo",
    "header": "Company name",
    "footer": "Internal",
    "brand": {"accent": "333333", "text": "262626", "title_font": "Calibri", "body_font": "Calibri"},
    "blocks": [
        {
            "type": "table",
            "header": ["To", "Name and role"],
            "rows": [
                ["From", "Name and role"],
                ["Date", "1 January 2026"],
                ["Subject", "One line that says what this is about"],
            ],
        },
        {"type": "heading", "level": 1, "text": "Decision needed"},
        {"type": "paragraph", "text": "Say what you need from the reader and by when, in two sentences."},
        {"type": "heading", "level": 1, "text": "Background"},
        {"type": "paragraph", "text": "The facts the reader needs, shortest first."},
    ],
}
PROPOSAL = {
    "title": "Proposal",
    "toc": True,
    "header": "Company name | Proposal",
    "footer": "Valid for 30 days",
    "brand": {"accent": "0F766E", "text": "1F2937", "title_font": "Georgia", "body_font": "Calibri"},
    "blocks": [
        {"type": "heading", "level": 1, "text": "The problem"},
        {"type": "paragraph", "text": "Describe the customer's problem in their words, with one number."},
        {"type": "heading", "level": 1, "text": "Our approach"},
        {
            "type": "bullets",
            "items": ["Step one and what the customer gets", "Step two and what the customer gets"],
        },
        {"type": "heading", "level": 1, "text": "Timeline and price"},
        {
            "type": "table",
            "header": ["Phase", "Weeks", "Price"],
            "rows": [["Discovery", "2", "0"], ["Delivery", "6", "0"]],
        },
        {"type": "heading", "level": 1, "text": "Next step"},
        {"type": "paragraph", "text": "One clear action, who does it and by when."},
    ],
}
WORKBOOK_BUDGET = {
    "title": "Budget",
    "brand": {"accent": "1F3864", "body_font": "Calibri"},
    "sheets": [
        {
            "name": "Assumptions",
            "columns": [{"header": "Item", "width": 28}, {"header": "Value", "format": "0.0%"}],
            "rows": [["Growth per month", 0.03], ["Tax rate", 0.2], ["Cost growth per month", 0.01]],
        },
        {
            "name": "Budget",
            "columns": [
                {"header": "Month", "width": 14},
                {"header": "Revenue", "format": "#,##0"},
                {"header": "Costs", "format": "#,##0"},
                {"header": "Profit", "format": "#,##0"},
                {"header": "Tax", "format": "#,##0"},
            ],
            "rows": [
                ["Jan", 10000, 8000, "=B2-C2", "=MAX(D2,0)*TaxRate"],
                ["Feb", "=B2*(1+GrowthPerMonth)", "=C2*(1+CostGrowth)", "=B3-C3", "=MAX(D3,0)*TaxRate"],
                ["Mar", "=B3*(1+GrowthPerMonth)", "=C3*(1+CostGrowth)", "=B4-C4", "=MAX(D4,0)*TaxRate"],
            ],
            "total_row": {"A": "Total", "B": "SUM", "C": "SUM", "D": "SUM", "E": "SUM"},
            "charts": [
                {
                    "type": "column",
                    "title": "Revenue and costs",
                    "data": "B1:C4",
                    "categories": "A2:A4",
                    "anchor": "G2",
                }
            ],
        },
    ],
    "names": {
        "GrowthPerMonth": "Assumptions!$B$2",
        "TaxRate": "Assumptions!$B$3",
        "CostGrowth": "Assumptions!$B$4",
    },
}
WORKBOOK_TRACKER = {
    "title": "Task tracker",
    "brand": {"accent": "0F766E", "body_font": "Calibri"},
    "sheets": [
        {
            "name": "Tasks",
            "table": True,
            "columns": [
                {"header": "Task", "width": 36},
                {"header": "Owner", "width": 16},
                {"header": "Status", "width": 14},
                {"header": "Due", "width": 14, "format": "yyyy-mm-dd"},
                {"header": "Priority", "width": 10},
            ],
            "rows": [
                ["Write the plan", "Asha", "Open", "2026-02-01", "High"],
                ["Review with the team", "Ravi", "Done", "2026-02-05", "Medium"],
            ],
            "validations": [
                {"range": "C2:C200", "choices": ["Open", "In progress", "Done"]},
                {"range": "E2:E200", "choices": ["High", "Medium", "Low"]},
            ],
            "conditional": [
                {"range": "C2:C200", "rule": "text_contains", "value": "Done", "fill": "C6EFCE"},
                {"range": "E2:E200", "rule": "text_contains", "value": "High", "fill": "FFC7CE"},
            ],
        }
    ],
}
PDF_HANDOUT = {
    "title": "Handout",
    "author": "Company name",
    "footer": "Company name",
    "brand": {"accent": "1F3864", "text": "262626"},
    "blocks": [
        {"type": "heading", "level": 1, "text": "What you need to know"},
        {
            "type": "paragraph",
            "text": "One short paragraph that says what this handout is for and who it is for.",
        },
        {"type": "bullets", "items": ["The first thing to do", "The second thing to do"]},
        {"type": "heading", "level": 1, "text": "Contacts"},
        {
            "type": "table",
            "header": ["Name", "Role", "Email"],
            "rows": [["Name", "Role", "name@example.com"]],
        },
    ],
}


def _write(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))


def main() -> int:
    word = SKILLS / "make-document"
    for name, outline in (("report-clean", REPORT), ("memo", MEMO), ("proposal", PROPOSAL)):
        data = build_document(parse_document(json.dumps(outline)), lambda _name: b"")
        _write(word / "templates" / f"{name}.docx", data)
        try:
            import pypdfium2  # noqa: F401  (optional: only for the preview picture)

            pdf = to_pdf(data)
            from forge.vision.pdf import render

            folder = word / "assets" / "preview"
            folder.mkdir(parents=True, exist_ok=True)
            scratch = folder / f"{name}.pdf"
            scratch.write_bytes(pdf)
            picture = render(scratch, folder, [1], 80)[0]
            from PIL import Image

            with Image.open(picture) as image:
                image.convert("RGB").save(folder / f"tpl-doc-{name}-page1.jpg", quality=82)
            picture.unlink()
            scratch.unlink()
        except (ImportError, PreviewUnavailable) as error:
            print(f"no preview picture for {name}: {error}")
    _write(SKILLS / "make-spreadsheet" / "templates" / "budget.json", json.dumps(WORKBOOK_BUDGET, indent=2))
    _write(SKILLS / "make-spreadsheet" / "templates" / "tracker.json", json.dumps(WORKBOOK_TRACKER, indent=2))
    _write(SKILLS / "pdf-toolkit" / "templates" / "handout.json", json.dumps(PDF_HANDOUT, indent=2))
    print("templates written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

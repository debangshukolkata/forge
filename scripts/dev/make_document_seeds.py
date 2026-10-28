"""Builds the seed files of the document benchmark tasks that start from an existing document (TODO W5, D-519).

    python scripts/dev/make_document_seeds.py

Writes into tests/benchmarks/documents/<task>/seed/: report.pdf (w08), cover.pdf, annex.pdf and terms.pdf (w09), minutes.docx (w12), sales.xlsx (w13) and
kpis.csv (w14). The files are small and are committed, so the benchmark does not depend on this script at run time; rerun it only to change them.
Needs reportlab, python-docx and openpyxl (the optional `docs` extra)."""

from __future__ import annotations

import datetime
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2] / "tests" / "benchmarks" / "documents"


def pdf(path: Path, pages: list[list[str]], title: str) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    path.parent.mkdir(parents=True, exist_ok=True)
    sheet = canvas.Canvas(str(path), pagesize=A4)
    sheet.setTitle(title)
    for lines in pages:
        y = 780
        for line in lines:
            sheet.setFont("Helvetica", 12)
            sheet.drawString(60, y, line)
            y -= 22
        sheet.showPage()
    sheet.save()


def main() -> None:
    import openpyxl
    from docx import Document
    from openpyxl.chart import BarChart, Reference

    # w08: a report with one table to extract
    pdf(
        BENCH / "w08_pdf_extract" / "seed" / "report.pdf",
        [
            [
                "Harbour Street Cafe: quarterly sales report",
                "Sales were steady through the year, with a strong autumn.",
                "",
                "Quarter     Sales (GBP)     Orders",
                "Q1          41200           3100",
                "Q2          45800           3380",
                "Q3          52300           3790",
                "Q4          61900           4410",
            ]
        ],
        "Quarterly sales report",
    )
    # w09: three small PDFs to merge in a given order
    pdf(
        BENCH / "w09_pdf_merge" / "seed" / "cover.pdf",
        [["COVER SHEET", "Proposal for Harbour Street Bakery"]],
        "Cover",
    )
    pdf(
        BENCH / "w09_pdf_merge" / "seed" / "annex.pdf",
        [["ANNEX A", "Price list"], ["ANNEX B", "Delivery map"]],
        "Annex",
    )
    pdf(
        BENCH / "w09_pdf_merge" / "seed" / "terms.pdf",
        [["TERMS AND CONDITIONS", "Payment within 30 days."]],
        "Terms",
    )
    # w10: a fillable form (AcroForm text fields) and the details to put in it
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    folder = BENCH / "w10_pdf_form" / "seed"
    folder.mkdir(parents=True, exist_ok=True)
    sheet = canvas.Canvas(str(folder / "form.pdf"), pagesize=A4)
    sheet.setTitle("Membership form")
    sheet.setFont("Helvetica-Bold", 16)
    sheet.drawString(60, 780, "Membership application")
    sheet.setFont("Helvetica", 12)
    for index, (label, name) in enumerate(
        [
            ("Full name", "full_name"),
            ("E-mail", "email"),
            ("Postcode", "postcode"),
            ("Start date", "start_date"),
        ]
    ):
        y = 730 - index * 50
        sheet.drawString(60, y + 6, label)
        sheet.acroForm.textfield(
            name=name, x=180, y=y, width=260, height=22, borderStyle="solid", forceBorder=True
        )
    sheet.save()
    (folder / "details.txt").write_text(
        "Full name: Priya Raman\nE-mail: priya.raman@example.org\nPostcode: MB3 4QF\nStart date: 8 January 2027\n",
        encoding="utf-8",
        newline="\n",
    )
    # w11: a scanned page (text drawn into a picture, no text layer) to read with OCR
    from PIL import Image, ImageDraw, ImageFont

    folder = BENCH / "w11_pdf_ocr" / "seed"
    folder.mkdir(parents=True, exist_ok=True)
    page = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(page)
    try:
        big = ImageFont.truetype("arial.ttf", 54)
        body = ImageFont.truetype("arial.ttf", 38)
    except OSError:
        big = body = ImageFont.load_default()
    draw.text((120, 140), "Delivery note 4471", fill="black", font=big)
    for index, line in enumerate(
        [
            "Customer: Harbour Street Bakery",
            "Date: 18 November 2026",
            "Items: 40 loaves, 12 trays of rolls",
            "Signed by: D. Whitfield",
        ]
    ):
        draw.text((120, 300 + index * 80), line, fill="black", font=body)
    page.save(folder / "scan.pdf", "PDF", resolution=150)
    # w12: meeting minutes to edit
    folder = BENCH / "w12_word_edit" / "seed"
    folder.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.add_heading("Minutes of the planning meeting", level=1)
    document.add_paragraph("Meeting date: 3 March. Present: Dana, Sam, Priya.")
    document.add_heading("Decisions", level=2)
    document.add_paragraph("The new menu starts in April. The delivery van is replaced before the summer.")
    document.add_heading("Actions", level=2)
    table = document.add_table(rows=2, cols=3)
    table.style = "Table Grid"
    for cell, text in zip(table.rows[0].cells, ["Owner", "Task", "Due"], strict=True):
        cell.text = text
    for cell, text in zip(
        table.rows[1].cells, ["Priya", "Order the new menu boards", "10 March"], strict=True
    ):
        cell.text = text
    document.add_paragraph(
        "Next meeting: 3 March next year is too late, so we meet again in the first week of May."
    )
    document.save(folder / "minutes.docx")
    # w13: a workbook with formulas and a chart to extend
    folder = BENCH / "w13_excel_edit" / "seed"
    folder.mkdir(parents=True, exist_ok=True)
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Sales"
    sheet.append(["Product", "Revenue", "Cost"])
    for row in [
        ["Kettle", 5200, 3100],
        ["Toaster", 3400, 2200],
        ["Blender", 4100, 2500],
        ["Grinder", 2900, 1700],
    ]:
        sheet.append(row)
    sheet.append(["Total", "=SUM(B2:B5)", "=SUM(C2:C5)"])
    for cell in sheet[1]:
        cell.font = openpyxl.styles.Font(bold=True)
    for row in sheet.iter_rows(min_row=2, min_col=2, max_col=3):
        for cell in row:
            cell.number_format = "#,##0"
    chart = BarChart()
    chart.title = "Revenue by product"
    chart.add_data(Reference(sheet, min_col=2, min_row=1, max_row=5), titles_from_data=True)
    chart.set_categories(Reference(sheet, min_col=1, min_row=2, max_row=5))
    sheet.add_chart(chart, "F2")
    book.save(folder / "sales.xlsx")
    # w14: the data of a small dashboard
    folder = BENCH / "w14_excel_dashboard" / "seed"
    folder.mkdir(parents=True, exist_ok=True)
    rows = ["Month,Revenue,Customers,Refunds"]
    base = datetime.date(2026, 1, 1)
    for index, (revenue, customers, refunds) in enumerate(
        [
            (41200, 310, 12),
            (43800, 322, 9),
            (47100, 340, 15),
            (45200, 336, 11),
            (49900, 361, 8),
            (52300, 378, 10),
        ]
    ):
        month = (base.replace(month=index + 1)).strftime("%Y-%m")
        rows.append(f"{month},{revenue},{customers},{refunds}")
    (folder / "kpis.csv").write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    print("seed files written")


if __name__ == "__main__":
    main()

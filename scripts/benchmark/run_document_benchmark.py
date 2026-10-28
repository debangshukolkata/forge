"""Document benchmark (TODO W5, D-357). Three fixed tasks on the real model (tests/benchmarks/documents): a Word sales summary from a CSV, a messy export
turned into a workbook with a chart, a PDF handout from notes. Each result is scored by deterministic checks (package validity, the numbers and phrases
that must be there, formulas instead of typed totals, charts, pages) and, when Word, Excel or a PDF renderer is available, by a blind vision judgement of
the printed pages.

    python scripts/benchmark/run_document_benchmark.py <run-name> [--tasks w01_sales_report] [--env KEY=VALUE ...] [--no-judge]

Results go to C:\\Work\\ForgeRuns\\docbench\\<run-name>; paste the table into docs/DOCUMENT_BENCHMARK.md with the date and what changed. It spends Azure tokens
(about a dollar a task), so it is run by hand."""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_code_benchmark import PYTHON, REPO
from run_speed_benchmark import timing

sys.path.insert(0, str(Path(__file__).resolve().parent))
from awake import keep_awake

TASKS = REPO / "tests" / "benchmarks" / "documents"
RUNS = Path(os.environ.get("FORGE_BENCH_RUNS", r"C:\Work\ForgeRuns")) / "docbench"
JUDGE_RUBRIC = (
    "You are a demanding editor judging a finished business document from pictures of its printed pages. Be strict and use the whole scale: 5 is "
    "professionally typeset work, 3 is competent but plain, 2 is the generic machine-made look, 1 is poor. Score: structure (clear title, headings, "
    "reading order), readability (type size, spacing, line length, contrast), tables (clear header, aligned numbers, nothing cut off), polish (alignment, "
    'consistency, nothing clipped or empty). Reply with JSON only: {"structure": n, "readability": n, "tables": n, "polish": n, "worst_problem": "one sentence"}.'
)  # fmt: skip


# --- checks (each returns (passed, total, failed names)) ---


def _report(passed: dict[str, bool]) -> dict[str, Any]:
    failed = [name for name, ok in passed.items() if not ok]
    return {"checks_passed": len(passed) - len(failed), "checks_total": len(passed), "checks_failed": failed}


def check_w01(workspace: Path) -> dict[str, Any]:
    from forge.documents.check import check_document
    from forge.documents.read import read_document
    from forge.ooxml.validate import validate_package

    file = workspace / "project" / "sales-summary.docx"
    if not file.is_file():
        return {"delivered": False, "checks_passed": 0, "checks_total": 8, "checks_failed": ["no document"]}
    data = file.read_bytes()
    info = read_document(data)
    text = info.markdown.replace(",", "").replace(" ", "")
    passed = {
        "package valid": not validate_package(data),
        "no structure or accessibility problems": not check_document(data),
        "total revenue stated (734850)": bool(
            re.search(r"734850|734\.9|735k|\b735,?000\b|0\.73m", text, re.I)
        ),
        "best region named (West)": "West" in info.markdown,
        "a table of the data": "|" in info.markdown and "120400" in text and "151750" in text,
        "a title and two headings or more": info.markdown.count("#") >= 2,
        "bullet points": info.markdown.count("\n- ") >= 2,
        "no invented figure over 100000": all(
            n
            in (
                "120400",
                "133900",
                "98200",
                "87600",
                "143000",
                "151750",
                "734850",
                "294750",
                "254300",
                "185800",
                "235400",
            )
            for n in re.findall(r"\d{6}", text)
        ),
    }
    return {"delivered": True, **_report(passed)}


def check_w02(workspace: Path) -> dict[str, Any]:
    from forge.ooxml.validate import validate_package
    from forge.sheets.check import check_workbook
    from forge.sheets.read import package_extras

    file = workspace / "project" / "orders.xlsx"
    if not file.is_file():
        return {"delivered": False, "checks_passed": 0, "checks_total": 8, "checks_failed": ["no workbook"]}
    import openpyxl

    data = file.read_bytes()
    book = openpyxl.load_workbook(io.BytesIO(data))
    cells = [c for sheet in book.worksheets for row in sheet.iter_rows() for c in row if c.value is not None]
    formulas = [c for c in cells if isinstance(c.value, str) and c.value.startswith("=")]
    texts = [str(c.value) for c in cells if isinstance(c.value, str)]
    errors = [f for f in check_workbook(data) if f.level == "error"]
    charts, _, macros = package_extras(data)
    amounts = [c.value for c in cells if isinstance(c.value, (int, float)) and not isinstance(c.value, bool)]
    passed = {
        "package valid": not validate_package(data),
        "no formula errors": not errors,
        "amounts are numbers (1200.5 present)": 1200.5 in amounts and not any("$1,200" in t for t in texts),
        "a total made of formulas": any("SUM" in str(c.value).upper() for c in formulas),
        "a chart": charts >= 1,
        "duplicate row removed": sum(1 for t in texts if t.strip().lower() == "kettle") == 1,
        "title lines removed": not any("Quarterly export" in t or "Generated" in t for t in texts),
        "no macros": not macros,
    }
    return {"delivered": True, **_report(passed)}


def check_w03(workspace: Path) -> dict[str, Any]:
    from forge.pdfs.read import read_pdf

    file = workspace / "project" / "handout.pdf"
    if not file.is_file():
        return {"delivered": False, "checks_passed": 0, "checks_total": 7, "checks_failed": ["no pdf"]}
    info = read_pdf(file.read_bytes())
    text = " ".join(info.texts)
    passed = {
        "one or two pages": 1 <= info.pages <= 2,
        "has text": not info.scanned,
        "title set in the file": bool(info.title.strip()),
        "place and date": "Riverside Park" in text and "14 June" in text,
        "schedule rows": "Welcome and safety talk" in text and "Planting" in text,
        "contact line": "0113 555 0142" in text and "volunteers@riverside.example" in text,
        "what to bring": "gloves" in text.lower(),
    }
    return {"delivered": True, **_report(passed)}


def check_w04(workspace: Path) -> dict[str, Any]:
    from forge.documents.check import check_document
    from forge.documents.read import read_document
    from forge.ooxml.validate import validate_package

    file = workspace / "project" / "proposal.docx"
    if not file.is_file():
        return {"delivered": False, "checks_passed": 0, "checks_total": 9, "checks_failed": ["no document"]}
    data = file.read_bytes()
    info = read_document(data)
    markdown = info.markdown
    plain = markdown.replace(",", "").replace(" ", "")
    prices = ("1200", "2800", "3500", "900", "8400")
    passed = {
        "package valid": not validate_package(data),
        "no structure or accessibility problems": not check_document(data),
        "client named": "Harbour Street Bakery" in markdown or "Dana Whitfield" in markdown,
        "every phase price and the total": all(price in plain for price in prices),
        "a table": "|" in markdown,
        "the three dates": all(date in markdown for date in ("3 March", "21 March", "18 April")),
        "deliverables as bullet points": markdown.count("\n- ") >= 3,
        "three headings or more": markdown.count("#") >= 3,
        "no invented price": all(
            n in prices for n in re.findall(r"(?<![\d.])\d{3,5}(?![\d.])", plain) if n not in ("2026", "2027")
        ),
    }
    return {"delivered": True, **_report(passed)}


def check_w05(workspace: Path) -> dict[str, Any]:
    from forge.documents.check import check_document
    from forge.documents.read import read_document
    from forge.ooxml.validate import validate_package

    file = workspace / "project" / "letter.docx"
    if not file.is_file():
        return {"delivered": False, "checks_passed": 0, "checks_total": 9, "checks_failed": ["no document"]}
    data = file.read_bytes()
    info = read_document(data)
    markdown = info.markdown
    passed = {
        "package valid": not validate_package(data),
        "no structure or accessibility problems": not check_document(data),
        "the date": "12 November 2026" in markdown,
        "the recipient": "Admissions Office" in markdown and "8 Harbour Street" in markdown,
        "the sender's address": "14 Elm Court" in markdown,
        "the child named in the subject and the body": markdown.count("Anika") >= 2,
        "the trial dates": "20" in markdown and "27 November" in markdown,
        "the reply details": "priya.raman@example.org" in markdown and "07700 900 456" in markdown,
        "a closing and the name": "Yours" in markdown and markdown.count("Priya Raman") >= 2,
    }
    return {"delivered": True, **_report(passed)}


MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")


def check_w06(workspace: Path) -> dict[str, Any]:
    from forge.ooxml.validate import validate_package
    from forge.sheets.check import check_workbook
    from forge.sheets.read import package_extras

    file = workspace / "project" / "budget.xlsx"
    if not file.is_file():
        return {"delivered": False, "checks_passed": 0, "checks_total": 7, "checks_failed": ["no workbook"]}
    import openpyxl

    data = file.read_bytes()
    book = openpyxl.load_workbook(io.BytesIO(data))
    cells = [c for sheet in book.worksheets for row in sheet.iter_rows() for c in row if c.value is not None]
    formulas = [c for c in cells if isinstance(c.value, str) and c.value.startswith("=")]
    numbers = [c.value for c in cells if isinstance(c.value, (int, float)) and not isinstance(c.value, bool)]
    months = [
        c
        for c in cells
        if isinstance(c.value, str) and c.value.strip().lower()[:3] in MONTHS and not c.value.startswith("=")
    ]
    errors = [f for f in check_workbook(data) if f.level == "error"]
    charts, _, macros = package_extras(data)
    passed = {
        "package valid": not validate_package(data),
        "no formula errors": not errors,
        "twelve month columns": len({c.column for c in months}) >= 12,
        "the figures are numbers (2850 present)": 2850 in numbers,
        "totals made of formulas": sum("SUM" in str(c.value).upper() for c in formulas) >= 2,
        "what is left each month is a formula": len(formulas) >= 12,
        "a chart": charts >= 1 and not macros,
    }
    return {"delivered": True, **_report(passed)}


def check_w07(workspace: Path) -> dict[str, Any]:
    from forge.ooxml.validate import validate_package
    from forge.sheets.check import check_workbook
    from forge.sheets.read import package_extras

    file = workspace / "project" / "tracker.xlsx"
    if not file.is_file():
        return {"delivered": False, "checks_passed": 0, "checks_total": 7, "checks_failed": ["no workbook"]}
    import datetime

    import openpyxl

    data = file.read_bytes()
    book = openpyxl.load_workbook(io.BytesIO(data))
    first = book.worksheets[0]
    cells = [c for sheet in book.worksheets for row in sheet.iter_rows() for c in row if c.value is not None]
    dates = [
        c for c in first.iter_rows() for c in c if isinstance(c.value, (datetime.date, datetime.datetime))
    ]
    lists = [str(rule.formula1) for rule in first.data_validations.dataValidation if rule.type == "list"]
    summary_formulas = [
        c
        for sheet in book.worksheets[1:]
        for row in sheet.iter_rows()
        for c in row
        if isinstance(c.value, str) and c.value.upper().startswith("=COUNTIF")
    ]
    errors = [f for f in check_workbook(data) if f.level == "error"]
    _, _, macros = package_extras(data)
    passed = {
        "package valid": not validate_package(data),
        "no formula errors": not errors,
        "a status drop-down with the four statuses": any(
            "In progress" in rule and "Blocked" in rule for rule in lists
        ),
        "real dates (ten or more)": len(dates) >= 10,
        "the header stays in view": bool(first.freeze_panes),
        "a second sheet counting each status": len(book.worksheets) >= 2 and len(summary_formulas) >= 4,
        "no macros": not macros and bool(cells),
    }
    return {"delivered": True, **_report(passed)}


def _workbook_cells(data: bytes) -> tuple[Any, list[Any]]:
    import openpyxl

    book = openpyxl.load_workbook(io.BytesIO(data))
    return book, [
        c for sheet in book.worksheets for row in sheet.iter_rows() for c in row if c.value is not None
    ]


def _is_formula(cell: Any) -> bool:
    return isinstance(cell.value, str) and cell.value.startswith("=")


def check_w08(workspace: Path) -> dict[str, Any]:
    from forge.ooxml.validate import validate_package
    from forge.sheets.check import check_workbook

    file = workspace / "project" / "figures.xlsx"
    if not file.is_file():
        return {"delivered": False, "checks_passed": 0, "checks_total": 6, "checks_failed": ["no workbook"]}
    data = file.read_bytes()
    _, cells = _workbook_cells(data)
    numbers = [c.value for c in cells if isinstance(c.value, (int, float)) and not isinstance(c.value, bool)]
    texts = " ".join(str(c.value) for c in cells if isinstance(c.value, str) and not c.value.startswith("="))
    plain = texts.replace(",", "").replace(" ", "")
    # The sentence may be a formula that builds it from the total (="Total sales were " & B6): better than typed text, because it stays right.
    total_cells = {c.coordinate for c in cells if _is_formula(c) and "SUM" in str(c.value).upper()}
    sentence_from_formula = any(
        _is_formula(c)
        and "&" in str(c.value)
        and "total" in str(c.value).lower()
        and any(
            re.search(rf"(?<![A-Z]){re.escape(coordinate)}(?!\d)", str(c.value)) for coordinate in total_cells
        )
        for c in cells
    )
    passed = {
        "package valid": not validate_package(data),
        "no formula errors": not [f for f in check_workbook(data) if f.level == "error"],
        "the four quarters as numbers": all(n in numbers for n in (41200, 45800, 52300, 61900)),
        "the order counts as numbers": all(n in numbers for n in (3100, 3380, 3790, 4410)),
        "a total made of a formula": any("SUM" in str(c.value).upper() for c in cells if _is_formula(c)),
        "the yearly total stated (201200, typed or built by a formula from the total)": "201200" in plain
        or sentence_from_formula,
    }
    return {"delivered": True, **_report(passed)}


def check_w09(workspace: Path) -> dict[str, Any]:
    from forge.pdfs.read import read_pdf

    file = workspace / "project" / "pack.pdf"
    if not file.is_file():
        return {"delivered": False, "checks_passed": 0, "checks_total": 6, "checks_failed": ["no pdf"]}
    info = read_pdf(file.read_bytes())
    texts = [t.upper() for t in info.texts]
    passed = {
        "four pages": info.pages == 4,
        "the cover first": len(texts) > 0 and "COVER SHEET" in texts[0],
        "the terms second": len(texts) > 1 and "TERMS AND CONDITIONS" in texts[1],
        "the annex pages third and fourth": len(texts) > 3
        and "ANNEX A" in texts[2]
        and "ANNEX B" in texts[3],
        "the title is set": info.title.strip() == "Proposal pack",
        "the text is kept as text": not info.scanned,
    }
    return {"delivered": True, **_report(passed)}


def check_w10(workspace: Path) -> dict[str, Any]:
    from pypdf import PdfReader

    file = workspace / "project" / "form-filled.pdf"
    if not file.is_file():
        return {"delivered": False, "checks_passed": 0, "checks_total": 6, "checks_failed": ["no pdf"]}
    reader = PdfReader(io.BytesIO(file.read_bytes()))
    fields = {name: str(field.get("/V") or "") for name, field in (reader.get_fields() or {}).items()}
    passed = {
        "the form fields are still there": {"full_name", "email", "postcode", "start_date"} <= set(fields),
        "full name filled": fields.get("full_name", "") == "Priya Raman",
        "e-mail filled": fields.get("email", "") == "priya.raman@example.org",
        "postcode filled": fields.get("postcode", "") == "MB3 4QF",
        "start date filled": fields.get("start_date", "") == "8 January 2027",
        "the form text is kept": "Membership application" in (reader.pages[0].extract_text() or ""),
    }
    return {"delivered": True, **_report(passed)}


def check_w11(workspace: Path) -> dict[str, Any]:
    from forge.documents.check import check_document
    from forge.documents.read import read_document
    from forge.ooxml.validate import validate_package

    file = workspace / "project" / "delivery-note.docx"
    if not file.is_file():
        return {"delivered": False, "checks_passed": 0, "checks_total": 7, "checks_failed": ["no document"]}
    data = file.read_bytes()
    markdown = read_document(data).markdown
    passed = {
        "package valid": not validate_package(data),
        "no structure or accessibility problems": not check_document(data),
        "the note number in the title": "4471" in markdown,
        "the customer": "Harbour Street Bakery" in markdown,
        "the date": "18 November 2026" in markdown,
        "the items": "40 loaves" in markdown and "12 trays" in markdown,
        "the signer in a table": "Whitfield" in markdown and "|" in markdown,
    }
    return {"delivered": True, **_report(passed)}


def check_w12(workspace: Path) -> dict[str, Any]:
    from forge.documents.read import read_document
    from forge.ooxml.validate import validate_package

    file = workspace / "project" / "minutes-updated.docx"
    if not file.is_file():
        return {"delivered": False, "checks_passed": 0, "checks_total": 7, "checks_failed": ["no document"]}
    data = file.read_bytes()
    markdown = read_document(data).markdown
    passed = {
        "package valid": not validate_package(data),
        "the date changed in the first paragraph": "Meeting date: 10 March" in markdown
        and "Meeting date: 3 March" not in markdown,
        "the other 3 March left alone": "3 March next year" in markdown,
        "the new action row": bool(
            re.search(r"\|\s*Sam\s*\|\s*Send the notes\s*\|\s*14 March\s*\|", markdown)
        ),
        "the old action row kept": bool(
            re.search(r"\|\s*Priya\s*\|\s*Order the new menu boards\s*\|\s*10 March\s*\|", markdown)
        ),
        "the decisions paragraph untouched": "The new menu starts in April. The delivery van is replaced before the summer."
        in markdown,
        "the three headings kept": all(
            h in markdown for h in ("Minutes of the planning meeting", "Decisions", "Actions")
        )
        and markdown.count("#") >= 3,
    }
    return {"delivered": True, **_report(passed)}


def check_w13(workspace: Path) -> dict[str, Any]:
    from forge.ooxml.validate import validate_package
    from forge.sheets.check import check_workbook
    from forge.sheets.read import package_extras

    file = workspace / "project" / "sales-margin.xlsx"
    if not file.is_file():
        return {"delivered": False, "checks_passed": 0, "checks_total": 8, "checks_failed": ["no workbook"]}
    data = file.read_bytes()
    book, _ = _workbook_cells(data)
    sheet = book["Sales"] if "Sales" in book.sheetnames else book.worksheets[0]
    charts, _, macros = package_extras(data)
    margin = [sheet.cell(row=r, column=4) for r in range(2, 7)]
    passed = {
        "package valid": not validate_package(data),
        "no formula errors": not [f for f in check_workbook(data) if f.level == "error"],
        "a margin formula for each product": all(_is_formula(c) for c in margin[:4]),
        "a margin in the total row": _is_formula(margin[4]),
        "the original numbers untouched": sheet["B2"].value == 5200 and sheet["C5"].value == 1700,
        "the existing chart kept": charts >= 1,
        "the number format kept": sheet["B2"].number_format == "#,##0",
        "the bold header kept": bool(sheet["A1"].font and sheet["A1"].font.bold) and not macros,
    }
    return {"delivered": True, **_report(passed)}


def check_w14(workspace: Path) -> dict[str, Any]:
    from forge.ooxml.validate import validate_package
    from forge.sheets.check import check_workbook
    from forge.sheets.read import package_extras

    file = workspace / "project" / "dashboard.xlsx"
    if not file.is_file():
        return {"delivered": False, "checks_passed": 0, "checks_total": 7, "checks_failed": ["no workbook"]}
    data = file.read_bytes()
    book, cells = _workbook_cells(data)
    numbers = [c.value for c in cells if isinstance(c.value, (int, float)) and not isinstance(c.value, bool)]
    formulas = [str(c.value).upper() for c in cells if _is_formula(c)]
    charts, _, macros = package_extras(data)
    passed = {
        "package valid": not validate_package(data),
        "no formula errors": not [f for f in check_workbook(data) if f.level == "error"],
        "the data as numbers": all(n in numbers for n in (41200, 52300, 310, 378)),
        "total revenue and average customers as formulas": any("SUM" in f for f in formulas)
        and any("AVERAGE" in f for f in formulas),
        "a refund rate as a division": any("/" in f for f in formulas),
        "two charts": charts >= 2,
        "a conditional format": any(len(sheet.conditional_formatting) > 0 for sheet in book.worksheets)
        and not macros,
    }
    return {"delivered": True, **_report(passed)}


CHECKS = {
    "w08_pdf_extract": check_w08,
    "w09_pdf_merge": check_w09,
    "w10_pdf_form": check_w10,
    "w11_pdf_ocr": check_w11,
    "w12_word_edit": check_w12,
    "w13_excel_edit": check_w13,
    "w14_excel_dashboard": check_w14,
    "w01_sales_report": check_w01,
    "w02_clean_and_chart": check_w02,
    "w03_handout": check_w03,
    "w04_proposal": check_w04,
    "w05_letter": check_w05,
    "w06_budget": check_w06,
    "w07_tracker": check_w07,
}
OUTPUT = {
    "w08_pdf_extract": "figures.xlsx",
    "w09_pdf_merge": "pack.pdf",
    "w10_pdf_form": "form-filled.pdf",
    "w11_pdf_ocr": "delivery-note.docx",
    "w12_word_edit": "minutes-updated.docx",
    "w13_excel_edit": "sales-margin.xlsx",
    "w14_excel_dashboard": "dashboard.xlsx",
    "w01_sales_report": "sales-summary.docx",
    "w02_clean_and_chart": "orders.xlsx",
    "w03_handout": "handout.pdf",
    "w04_proposal": "proposal.docx",
    "w05_letter": "letter.docx",
    "w06_budget": "budget.xlsx",
    "w07_tracker": "tracker.xlsx",
}


# --- the blind judgement of the printed pages ---


def printed_pages(file: Path, folder: Path) -> list[Path]:
    from forge.vision import pdf as pdf_render

    folder.mkdir(parents=True, exist_ok=True)
    suffix = file.suffix.lower()
    if suffix == ".pdf":
        source = file
    else:
        if suffix == ".docx":
            from forge.documents.preview import to_pdf
        else:
            from forge.sheets.excel import to_pdf  # type: ignore[assignment]
        source = folder / "printed.pdf"
        source.write_bytes(to_pdf(file.read_bytes()))
    return pdf_render.render(source, folder, list(range(1, min(pdf_render.page_count(source), 3) + 1)), 90)


async def judge(brief: str, pictures: list[Path]) -> dict[str, object]:
    sys.path.insert(0, str(REPO))
    from forge.config import load_config, load_secrets
    from forge.llm.base import ChatRequest, Message
    from forge.vision import images
    from tests.test_live_llm import router_for

    router = router_for(load_config(), load_secrets())
    urls = [images.for_model(images.open_image(p))[0] for p in pictures]
    response = await router.chat(
        "vision",
        ChatRequest(
            messages=[
                Message.system(JUDGE_RUBRIC),
                Message(role="user", content=f"Brief: {brief}", images=urls),
            ]
        ),
    )
    found = re.search(r"\{.*\}", response.text, re.S)
    try:
        return json.loads(found.group(0)) if found else {"error": response.text[:200]}
    except ValueError:
        return {"error": response.text[:200]}


# --- running ---


def run_task(task: Path, run_dir: Path, env: dict[str, str], with_judge: bool) -> dict[str, object]:
    meta = json.loads((task / "task.json").read_text(encoding="utf-8"))
    workspace = run_dir / meta["id"]
    shutil.rmtree(workspace, ignore_errors=True)
    created = subprocess.run(
        [str(PYTHON), "-m", "forge.cli", "new", "--standalone", "--project", f"doc-{meta['id']}", "--workspace", str(workspace)],
        env=env, capture_output=True, text=True,
    )  # fmt: skip
    if created.returncode != 0:
        return {
            "id": meta["id"],
            "error": f"workspace setup failed: {created.stdout[-300:]}{created.stderr[-300:]}",
        }
    shutil.copytree(task / "seed", workspace / "project", dirs_exist_ok=True)
    brief = (task / "task.md").read_text(encoding="utf-8")
    prompt_file = run_dir / f"{meta['id']}_prompt.txt"
    prompt_file.write_text(
        brief
        + "\n\nYou may install packages with `python -m pip install ...` in this project's environment: that is approved.",
        encoding="utf-8",
    )
    started = time.time()
    try:
        subprocess.run(
            [str(PYTHON), str(REPO / "scripts" / "campaign" / "drive_forge.py"), str(workspace), str(prompt_file), str(run_dir / f"{meta['id']}_run.json")],
            env=env, capture_output=True, timeout=3600,
        )  # fmt: skip
        timed_out = False
    except subprocess.TimeoutExpired:
        timed_out = True
    row: dict[str, object] = {
        "id": meta["id"],
        "title": meta["title"],
        "timed_out": timed_out,
        "outer_wall_s": round(time.time() - started),
    }
    row.update(timing(workspace / ".forge" / "transcripts" / "events.jsonl"))
    row.update(CHECKS[meta["id"]](workspace))
    output = workspace / "project" / OUTPUT[meta["id"]]
    if with_judge and output.is_file():
        try:
            row["judge"] = asyncio.run(judge(brief, printed_pages(output, run_dir / f"{meta['id']}_pages")))
        except Exception as error:  # no Word, Excel or renderer here: the checks still count
            row["judge"] = {"error": f"{type(error).__name__}: {str(error)[:120]}"}
    return row


def markdown(name: str, rows: list[dict[str, object]]) -> str:
    lines = [
        f"### Run `{name}` ({time.strftime('%Y-%m-%d %H:%M')})",
        "",
        "| Task | Checks | Wall | Cost | Judge (structure/readability/tables/polish) |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['id']} | ERROR: {r['error']} | | | |")
            continue
        judge_row = r.get("judge") if isinstance(r.get("judge"), dict) else {}
        scores = (
            "/".join(str(judge_row.get(k, "?")) for k in ("structure", "readability", "tables", "polish"))
            if judge_row and "error" not in judge_row
            else "n/a"
        )
        cost = format(float(r["cost_usd"]), ".2f") if r.get("cost_usd") is not None else ""  # type: ignore[arg-type]
        lines.append(
            f"| {r['id']} | {r.get('checks_passed')}/{r.get('checks_total')} | {r.get('wall_s')}s | {cost} | {scores} |"
        )
    lines.append("")
    for r in rows:
        if r.get("checks_failed"):
            lines.append(f"- {r['id']}: failed checks: {r['checks_failed']}")
        judge_row = r.get("judge")
        if isinstance(judge_row, dict) and judge_row.get("worst_problem"):
            lines.append(f"- {r['id']}: judge's worst problem: {judge_row['worst_problem']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--tasks", default="")
    parser.add_argument("--env", action="append", default=[])
    parser.add_argument(
        "--all-roles",
        default="",
        help="a model key (for example gpt54) used for every role: the builder, the reviewer, the vision judge",
    )
    parser.add_argument("--no-judge", action="store_true")
    args = parser.parse_args()
    keep_awake()
    run_dir = RUNS / args.name
    run_dir.mkdir(parents=True, exist_ok=True)
    home = run_dir / "home"
    home.mkdir(exist_ok=True)
    if args.all_roles:  # an A/B on the model: every role names the same model in the run's own config.yaml
        import yaml

        roles = {
            role: args.all_roles
            for role in ("coder", "kb_builder", "summariser", "vision", "reviewer", "judge")
        }
        (home / "config.yaml").write_text(yaml.safe_dump({"llm": {"roles": roles}}), encoding="utf-8")
    env = {
        **os.environ,
        "FORGE_HOME": str(home),
        "FORGE_ENV_FILE": str(REPO / ".env"),
        "PYTHONIOENCODING": "utf-8",
    }
    for pair in args.env:
        key, _, value = pair.partition("=")
        env[key] = value
    wanted = {t for t in args.tasks.split(",") if t}
    rows: list[dict[str, object]] = []
    for task in sorted(
        p for p in TASKS.iterdir() if (p / "task.json").exists() and (not wanted or p.name in wanted)
    ):
        print(f"[{args.name}] {task.name} ...", flush=True)
        rows.append(run_task(task, run_dir, env, not args.no_judge))
        (run_dir / "results.json").write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")
    report = markdown(args.name, rows)
    (run_dir / "results.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())

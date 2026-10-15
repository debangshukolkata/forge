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


CHECKS = {"w01_sales_report": check_w01, "w02_clean_and_chart": check_w02, "w03_handout": check_w03}
OUTPUT = {
    "w01_sales_report": "sales-summary.docx",
    "w02_clean_and_chart": "orders.xlsx",
    "w03_handout": "handout.pdf",
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

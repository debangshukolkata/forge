"""Presentation parity benchmark (TODO P0.1). Runs DebCraft on each request in tests/benchmarks/decks on the real model, then
scores the deck it delivers two ways: automatic checks (the file opens, package is valid, PowerPoint measures no overflow, slide
count, notes, native charts, titles, smallest font) and a judge: the real model looking at PowerPoint's own pictures of every
slide against a fixed rubric. This spends Azure tokens, so it is run by hand, never by the test suite.

    python scripts/benchmark/run_deck_benchmark.py <run-name> [--tasks d01_status_update,d07_edit_deck] [--env KEY=VALUE ...]
    python scripts/benchmark/run_deck_benchmark.py <run-name> --score-only      (score what is already in the run folder again)

Everything lives under C:\\Work\\ForgeRuns\\deckbench\\<run-name>. Paste the printed table into docs/PPT_BENCHMARK.md with the date
and what changed. The judge is a model, not a person: the user's own ratings of a few decks are the final check.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "benchmark"))

TASKS = REPO / "tests" / "benchmarks" / "decks"
RUNS = Path(os.environ.get("FORGE_BENCH_RUNS", r"C:\Work\ForgeRuns")) / "deckbench"
PYTHON = REPO / ".venv" / "Scripts" / "python.exe"
MIN_FONT_PT = 12
MAX_JUDGED_SLIDES = 30

JUDGE_PROMPT = """You are a demanding presentation design judge. You see PowerPoint's own pictures of every slide of a deck, in order,
that an assistant made for the request below. Judge the deck as a senior presentation designer would before it goes to a client.
A competent but generic deck is a 3. Reserve 5 for work you would be proud to present. Name actual slides in your comments.

Score each line from 1 to 5:
- story: a clear arc, one message per slide, titles that state the point, the order makes sense for the audience
- hierarchy: the eye knows where to go first on each slide; type sizes and weights are clearly ranked
- contrast: all text is readable against its background at presentation distance; no tiny text
- alignment: shared edges and margins, even spacing, nothing cramped or floating, nothing cut off or overlapping
- polish: colour, fonts and shapes look designed and consistent; charts and tables are clean; varied layouts; not a template wall of bullets
- fit: the content follows the request and its facts exactly (numbers, names, asks); nothing invented that is wrong

Reply with ONLY a JSON object: {"story": n, "hierarchy": n, "contrast": n, "alignment": n, "polish": n, "fit": n,
"worst_slides": [numbers], "biggest_problem": "one sentence", "comments": "at most 80 words"}"""


# --- running DebCraft ---


def run_task(task: Path, run_dir: Path, env: dict[str, str]) -> dict[str, object]:
    from tests.benchmarks.decks.seeds import make_seed

    meta = json.loads((task / "task.json").read_text(encoding="utf-8"))
    workspace = run_dir / meta["id"]
    shutil.rmtree(workspace, ignore_errors=True)
    created = subprocess.run(
        [
            str(PYTHON),
            "-m",
            "forge.cli",
            "new",
            "--standalone",
            "--project",
            f"deckbench-{meta['id']}",
            "--workspace",
            str(workspace),
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    if created.returncode != 0:
        return {
            "id": meta["id"],
            "kind": meta["kind"],
            "error": f"workspace setup failed: {created.stdout[-300:]}",
        }
    make_seed(meta["id"], workspace / "project")
    prompt_file = run_dir / f"{meta['id']}_prompt.txt"
    prompt_file.write_text((task / "request.md").read_text(encoding="utf-8"), encoding="utf-8")
    started = time.time()
    try:
        subprocess.run(
            [
                str(PYTHON),
                str(REPO / "scripts" / "campaign" / "drive_forge.py"),
                str(workspace),
                str(prompt_file),
                str(run_dir / f"{meta['id']}_run.json"),
            ],
            env=env,
            capture_output=True,
            timeout=3600,
        )
        timed_out = False
    except subprocess.TimeoutExpired:
        timed_out = True
    row: dict[str, object] = {
        "id": meta["id"],
        "kind": meta["kind"],
        "wall_s": round(time.time() - started),
        "timed_out": timed_out,
    }
    row.update(event_numbers(workspace / ".forge" / "transcripts" / "events.jsonl"))
    return row


def event_numbers(events_path: Path) -> dict[str, object]:
    if not events_path.exists():
        return {}
    events = [
        json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    llm = [e["payload"] for e in events if e["type"] == "llm_call"]
    costs = [e["payload"] for e in events if e["type"] == "cost_updated"]
    return {
        "model_calls": len(llm),
        "cost_usd": costs[-1].get("total_usd") if costs else None,
    }


def find_deck(workspace: Path) -> Path | None:
    """The delivered deck: deck.pptx anywhere in the workspace (not in preview or scratch folders), else the newest new .pptx."""
    skipped = {".forge", ".venv", "node_modules"}
    found = [
        p
        for folder in ("project", "output")
        for p in (workspace / folder).rglob("*.pptx")
        if not skipped.intersection(p.relative_to(workspace / folder).parts)
    ]
    exact = [p for p in found if p.name == "deck.pptx"]
    return max(exact or found, key=lambda p: p.stat().st_mtime) if found else None


# --- automatic checks ---


def automatic_checks(deck: Path, meta: dict[str, object]) -> dict[str, object]:
    from pptx import Presentation

    from forge.slides import preview
    from forge.slides.measure import measure_deck, overflow_problems
    from forge.slides.validate import validate_package

    checks: dict[str, object] = {}
    try:
        prs = Presentation(str(deck))
    except Exception as error:
        return {"opens": False, "note": f"does not open: {error}"}
    slides = list(prs.slides)
    checks["opens"] = True
    checks["slides"] = len(slides)
    checks["slides_in_range"] = int(meta["min_slides"]) <= len(slides) <= int(meta["max_slides"])  # type: ignore[call-overload]
    faults = validate_package(deck.read_bytes())
    checks["package_clean"] = not faults
    with_notes = sum(1 for s in slides if s.has_notes_slide and s.notes_slide.notes_text_frame.text.strip())
    checks["notes_pct"] = round(100 * with_notes / max(len(slides), 1))
    charts = sum(1 for s in slides for sh in s.shapes if getattr(sh, "has_chart", False) and sh.has_chart)
    checks["charts"] = charts
    checks["charts_enough"] = charts >= int(meta["min_charts"])  # type: ignore[call-overload]
    titled = sum(1 for s in slides if s.shapes.title is not None and s.shapes.title.text_frame.text.strip())
    checks["titled_pct"] = round(100 * titled / max(len(slides), 1))
    sizes = [
        run.font.size.pt
        for s in slides
        for sh in s.shapes
        if getattr(sh, "has_text_frame", False) and sh.has_text_frame
        for p in sh.text_frame.paragraphs
        for run in p.runs
        if run.font.size is not None and run.text.strip()
    ]
    checks["min_font_pt"] = min(sizes) if sizes else None
    checks["fonts_ok"] = bool(sizes) and min(sizes) >= MIN_FONT_PT
    try:
        spilled = overflow_problems(measure_deck(deck))
        checks["overflow"] = len(spilled)
        checks["overflow_free"] = not spilled
    except (preview.PreviewUnavailable, OSError, ValueError, KeyError):
        checks["overflow"] = None
    wanted = [k for k, v in checks.items() if isinstance(v, bool)]
    checks["passed"] = sum(1 for k in wanted if checks[k])
    checks["of"] = len(wanted)
    return checks


# --- the judge ---


async def judge(deck: Path, request: str, pictures: list[Path]) -> dict[str, object]:
    from forge.config import forge_home, load_config, load_secrets
    from forge.llm.base import ChatRequest, Message
    from forge.llm.router import LLMRouter
    from forge.vision import images

    home = forge_home()
    router = LLMRouter(load_config(home), load_secrets(home))
    urls = [images.for_model(images.open_image(p), None)[0] for p in pictures[:MAX_JUDGED_SLIDES]]
    text = f"REQUEST:\n{request}\n\nThe deck has {len(pictures)} slides; the pictures follow in order."
    response = await router.chat(
        "vision",
        ChatRequest(messages=[Message.system(JUDGE_PROMPT), Message(role="user", content=text, images=urls)]),
    )
    raw = response.text.strip()
    start, end = raw.find("{"), raw.rfind("}")
    try:
        return dict(json.loads(raw[start : end + 1]))
    except ValueError:
        return {"error": f"the judge did not answer in JSON: {raw[:200]}"}


def score_task(task: Path, run_dir: Path, row: dict[str, object]) -> dict[str, object]:
    from forge.slides import preview

    meta = json.loads((task / "task.json").read_text(encoding="utf-8"))
    workspace = run_dir / meta["id"]
    deck = find_deck(workspace)
    if deck is None:
        return {**row, "delivered": False}
    row = {**row, "delivered": True, "deck": str(deck)}
    row["auto"] = automatic_checks(deck, meta)
    pictures_dir = run_dir / f"{meta['id']}_pictures"
    shutil.rmtree(pictures_dir, ignore_errors=True)
    try:
        pictures = sorted(preview.export_slides(deck, pictures_dir), key=lambda p: int(p.stem.split("-")[-1]))
    except preview.PreviewUnavailable as error:
        row["judge"] = {"error": f"no pictures: {error}"}
        return row
    row["judge"] = asyncio.run(judge(deck, (task / "request.md").read_text(encoding="utf-8"), pictures))
    return row


# --- report ---


RUBRIC = ("story", "hierarchy", "contrast", "alignment", "polish", "fit")


def markdown(name: str, rows: list[dict[str, object]]) -> str:
    lines = [
        f"### Run `{name}` ({datetime.now():%Y-%m-%d %H:%M})",
        "",
        "| Task | Slides | Auto | Overflow | Notes % | Story | Hier. | Contr. | Align. | Polish | Fit | Judge avg | Wall | Cost |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    averages: list[float] = []
    for row in rows:
        if "error" in row or not row.get("delivered"):
            lines.append(
                f"| {row['id']} | "
                + (f"ERROR {row['error']}" if "error" in row else "NOT DELIVERED")
                + " |"
                + " |" * 12
            )
            continue
        auto: dict[str, object] = row.get("auto", {})  # type: ignore[assignment]
        judged: dict[str, object] = row.get("judge", {})  # type: ignore[assignment]
        scores = [judged.get(k) for k in RUBRIC]
        numeric = [float(s) for s in scores if isinstance(s, int | float)]  # type: ignore[arg-type]
        average = statistics.mean(numeric) if numeric else None
        if average is not None:
            averages.append(average)
        cost = row.get("cost_usd")
        lines.append(
            f"| {row['id']} | {auto.get('slides', '?')} | {auto.get('passed', '?')}/{auto.get('of', '?')} | "
            f"{auto.get('overflow', '?')} | {auto.get('notes_pct', '?')} | "
            + " | ".join(str(s) if s is not None else "-" for s in scores)
            + f" | {'-' if average is None else f'{average:.1f}'} | {row.get('wall_s', '?')}s | "
            + ("" if cost is None else f"${float(cost):.2f}")  # type: ignore[arg-type]
            + " |"
        )
    delivered = sum(1 for r in rows if r.get("delivered"))
    lines += [
        "",
        f"Delivered: {delivered}/{len(rows)}; mean judge score: "
        + (f"{statistics.mean(averages):.2f}" if averages else "n/a")
        + ".",
    ]
    for row in rows:
        judged = row.get("judge") or {}  # type: ignore[assignment]
        if isinstance(judged, dict) and judged.get("biggest_problem"):
            lines.append(f"- {row['id']}: {judged['biggest_problem']}")
    return "\n".join(lines)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]  # judge comments hold non-cp1252 characters
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--tasks", default="", help="comma-separated task ids (default: all)")
    parser.add_argument("--env", action="append", default=[], help="KEY=VALUE for the DebCraft process")
    parser.add_argument(
        "--score-only", action="store_true", help="do not run DebCraft; score the decks already there"
    )
    args = parser.parse_args()
    run_dir = RUNS / args.name
    run_dir.mkdir(parents=True, exist_ok=True)
    home = run_dir / "home"
    home.mkdir(exist_ok=True)
    env = {
        **os.environ,
        "FORGE_HOME": str(home),
        "FORGE_ENV_FILE": str(REPO / ".env"),
        "PYTHONIOENCODING": "utf-8",
    }
    for pair in args.env:
        key, _, value = pair.partition("=")
        env[key] = value
    os.environ.update({"FORGE_HOME": env["FORGE_HOME"], "FORGE_ENV_FILE": env["FORGE_ENV_FILE"]})
    wanted = {t for t in args.tasks.split(",") if t}
    folders = [p for p in sorted(TASKS.iterdir()) if p.is_dir() and (not wanted or p.name in wanted)]
    previous = {}
    if args.score_only and (run_dir / "results.json").exists():
        previous = {r["id"]: r for r in json.loads((run_dir / "results.json").read_text(encoding="utf-8"))}
    rows: list[dict[str, object]] = []
    for task in folders:
        print(f"[{args.name}] {task.name} ...", flush=True)
        row = previous.get(task.name) if args.score_only else run_task(task, run_dir, env)
        row = score_task(task, run_dir, row or {"id": task.name, "kind": ""})
        rows.append(row)
        (run_dir / "results.json").write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")
        judged = row.get("judge") or {}
        print(f"[{args.name}] {task.name}: delivered={row.get('delivered')} judge={judged}", flush=True)
    report = markdown(args.name, rows)
    (run_dir / "results.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())

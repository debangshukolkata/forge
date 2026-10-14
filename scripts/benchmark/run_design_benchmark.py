"""Design benchmark (TODO DS5, D-352). Fixed briefs for a new one-page site, built by DebCraft on the real model and then scored:

- the page in headless Edge at desktop and phone width (no sideways scroll, no console errors, no broken images);
- the style audit of the rendered page (how many measurable problems are left) and the DESIGN.md lint (errors, warnings);
- how far the design is from the generic default (light, blue accent, Inter, soft corners): the number of the six dimensions that differ;
- whether the design ladder was used (candidates drawn, `.forge/design-rounds.json`);
- a blind judgement by the vision model on a desktop and a phone screenshot: distinctiveness, hierarchy, harmony, fit, polish (1 to 5).

    python scripts/benchmark/run_design_benchmark.py <run-name> [--tasks d01_science_museum] [--env KEY=VALUE ...]

Results go to C:\\Work\\ForgeRuns\\designbench\\<run-name>; paste the table into docs/DESIGN_BENCHMARK.md with the date and what changed. It spends Azure
tokens (about a dollar a brief), so it is run by hand. One run per brief is noise-prone: compare conditions only with several runs."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_code_benchmark import PYTHON, REPO
from run_speed_benchmark import timing

TASKS = REPO / "tests" / "benchmarks" / "design"
RUNS = Path(os.environ.get("FORGE_BENCH_RUNS", r"C:\Work\ForgeRuns")) / "designbench"
JUDGE_RUBRIC = (
    "You are a demanding art director. You see a desktop screenshot and a phone screenshot of the same finished web page and its brief. Judge only what you see. "
    "Be strict and use the whole scale: 5 is award-winning studio work, 4 is clearly professional studio work whose distinctive quality you can name, 3 is competent but template-like, 2 is the generic machine-made look (system fonts, a default hero, identical cards), 1 is poor; most machine-made pages are 2 or 3. Score: typography (the type suits the product, mood and language; a system font stack is a 2), distinctiveness (looks designed for this product, not a default template: generic blue SaaS, purple-blue gradients, "
    "cream-and-terracotta, identical card rows score low), hierarchy, harmony (palette, type, shape belong together), fit (the feeling the brief asks for), "
    'polish (alignment, spacing, contrast, nothing broken or clipped). Reply with JSON only: {"typography": n, "distinctiveness": n, "hierarchy": n, "harmony": n, "fit": n, '
    '"polish": n, "worst_problem": "one sentence"}.'
)  # fmt: skip


def screenshots(page_file: Path, folder: Path) -> tuple[Path, Path, dict[str, object]]:
    """Desktop and phone pictures, plus the checks and the style audit of the page."""
    from playwright.sync_api import sync_playwright

    folder.mkdir(parents=True, exist_ok=True)
    facts: dict[str, object] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        for name, width, height in (("desktop", 1280, 800), ("phone", 375, 800)):
            page = browser.new_page(viewport={"width": width, "height": height})
            errors: list[str] = []
            page.on("console", lambda m, errors=errors: errors.append(m.text) if m.type == "error" else None)
            page.goto(page_file.resolve().as_uri())
            page.wait_for_timeout(600)
            facts[f"sideways_scroll_{name}"] = (
                page.evaluate("document.documentElement.scrollWidth - window.innerWidth") > 1
            )
            facts[f"broken_images_{name}"] = page.evaluate(
                "[...document.images].filter(i => !i.naturalWidth).length"
            )
            facts[f"console_errors_{name}"] = len(
                [e for e in errors if "favicon" not in e and "ERR_" not in e]
            )
            if name == "desktop":
                from forge.tools.ui_audit import AUDIT_SCRIPT

                result = page.evaluate(AUDIT_SCRIPT)
                facts["audit_findings"] = len(result.get("findings", []))
                facts["audit_text"] = [f[:140] for f in result.get("findings", [])][:6]
            page.screenshot(path=str(folder / f"{name}.png"), full_page=False)
            page.close()
        browser.close()
    return folder / "desktop.png", folder / "phone.png", facts


async def judge(brief: str, desktop: Path, phone: Path) -> dict[str, object]:
    sys.path.insert(0, str(REPO))
    from forge.config import load_config, load_secrets
    from forge.llm.base import ChatRequest, Message
    from forge.vision import images
    from tests.test_live_llm import router_for

    config, secrets = load_config(), load_secrets()
    router = router_for(config, secrets)
    urls = [images.for_model(images.open_image(p))[0] for p in (desktop, phone)]
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


def design_facts(workspace: Path) -> dict[str, object]:
    """DESIGN.md lint, distance from the generic default, and whether candidates were compared."""
    from forge.designsystem.lint import lint_text
    from forge.designsystem.novelty import Fingerprint, differences, fingerprint
    from forge.designsystem.spec import DesignMdError, parse_design_md

    facts: dict[str, object] = {"ladder_used": (workspace / ".forge" / "design-rounds.json").is_file()}
    path = next(
        (
            workspace / "project" / n
            for n in ("DESIGN.md", "design.md")
            if (workspace / "project" / n).is_file()
        ),
        None,
    )
    if path is None:
        path = next((workspace / n for n in ("DESIGN.md",) if (workspace / n).is_file()), None)
    facts["design_md"] = path is not None
    if path is None:
        return facts
    text = path.read_text(encoding="utf-8", errors="replace")
    findings = lint_text(text)
    facts["lint_errors"] = len([f for f in findings if f.severity == "error"])
    facts["lint_warnings"] = len([f for f in findings if f.severity == "warning"])
    try:
        mine = fingerprint(parse_design_md(text))
        default = Fingerprint("light", "blue", "inter", "soft", "balanced", "balanced")
        facts["fingerprint"] = str(mine)
        facts["differs_from_default_in"] = len(differences(mine, default))
    except DesignMdError:
        facts["differs_from_default_in"] = None
    return facts


def run_task(task: Path, run_dir: Path, env: dict[str, str]) -> dict[str, object]:
    meta = json.loads((task / "task.json").read_text(encoding="utf-8"))
    workspace = run_dir / meta["id"]
    shutil.rmtree(workspace, ignore_errors=True)
    created = subprocess.run(
        [str(PYTHON), "-m", "forge.cli", "new", "--standalone", "--project", f"design-{meta['id']}", "--workspace", str(workspace)],
        env=env, capture_output=True, text=True,
    )  # fmt: skip
    if created.returncode != 0:
        return {
            "id": meta["id"],
            "error": f"workspace setup failed: {created.stdout[-300:]}{created.stderr[-300:]}",
        }
    brief = (task / "task.md").read_text(encoding="utf-8")
    prompt_file = run_dir / f"{meta['id']}_prompt.txt"
    prompt_file.write_text(brief, encoding="utf-8")
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
    page = next(iter(sorted((workspace / "project").rglob("index.html"))), None)
    row["delivered"] = page is not None
    row.update(design_facts(workspace))
    if page is not None:
        desktop, phone, facts = screenshots(page, run_dir / f"{meta['id']}_shots")
        row.update(facts)
        row["judge"] = asyncio.run(judge(brief, desktop, phone))
    return row


def markdown(name: str, rows: list[dict[str, object]]) -> str:
    lines = [
        f"### Run `{name}` ({time.strftime('%Y-%m-%d %H:%M')})",
        "",
        "| Brief | Wall | Cost | Ladder | DESIGN.md lint (err/warn) | Differs from default in | Audit left | Sideways scroll | Judge (type/dist/hier/harm/fit/polish) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['id']} | ERROR: {r['error']} |" + " |" * 7)
            continue
        judge_row = r.get("judge") or {}
        scores = (
            "/".join(
                str(judge_row.get(k, "?"))
                for k in ("typography", "distinctiveness", "hierarchy", "harmony", "fit", "polish")
            )
            if isinstance(judge_row, dict)
            else "?"
        )
        cost = format(float(r["cost_usd"]), ".2f") if r.get("cost_usd") is not None else ""  # type: ignore[arg-type]
        lines.append(
            f"| {r['id']} | {r.get('wall_s')}s | {cost} | {'yes' if r.get('ladder_used') else 'no'} | "  # type: ignore[arg-type]
            f"{r.get('lint_errors', '-')}/{r.get('lint_warnings', '-')} | {r.get('differs_from_default_in', '-')} | {r.get('audit_findings', '-')} | "
            f"{'desktop ' if r.get('sideways_scroll_desktop') else ''}{'phone' if r.get('sideways_scroll_phone') else 'no'} | {scores} |"
        )
    lines.append("")
    for r in rows:
        judge_row = r.get("judge")
        if isinstance(judge_row, dict) and judge_row.get("worst_problem"):
            lines.append(f"- {r['id']}: judge's worst problem: {judge_row['worst_problem']}")
        if r.get("audit_text"):
            lines.append(f"- {r['id']}: audit left: {r['audit_text']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--tasks", default="")
    parser.add_argument("--env", action="append", default=[])
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
    wanted = {t for t in args.tasks.split(",") if t}
    rows: list[dict[str, object]] = []
    for task in sorted(
        p for p in TASKS.iterdir() if (p / "task.json").exists() and (not wanted or p.name in wanted)
    ):
        print(f"[{args.name}] {task.name} ...", flush=True)
        rows.append(run_task(task, run_dir, env))
        (run_dir / "results.json").write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")
    report = markdown(args.name, rows)
    (run_dir / "results.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "overnight"))
from fsutil import remove_tree
from run_code_benchmark import PYTHON, REPO
from run_speed_benchmark import timing

sys.path.insert(0, str(Path(__file__).resolve().parent))
from awake import keep_awake, stall_note

TASKS = REPO / "tests" / "benchmarks" / "design"
RUNS = Path(os.environ.get("FORGE_BENCH_RUNS", r"C:\Work\ForgeRuns")) / "designbench"
JUDGE_RUBRIC = (
    "You are a demanding art director. You see a desktop screenshot and a phone screenshot of the same finished web page and its brief. Judge only what you see. "
    "Be strict and use the whole scale: 5 is award-winning studio work, 4 is clearly professional studio work whose distinctive quality you can name, 3 is competent but template-like, 2 is the generic machine-made look (system fonts, a default hero, identical cards), 1 is poor; most machine-made pages are 2 or 3. Judge the first screen as a stranger would: could it belong to any business of this kind? Text beside a picture in a white card, followed by three equal boxes, is a 2 or 3 however tidy; a drawn stand-in where a photograph belongs caps distinctiveness at 2. Score: typography (the type suits the product, mood and language; a system font stack is a 2), distinctiveness (looks designed for this product, not a default template: generic blue SaaS, purple-blue gradients, "
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
            from forge.tools.ui_audit import AUDIT_SCRIPT

            result = page.evaluate(AUDIT_SCRIPT)
            if name == "desktop":
                facts["audit_findings"] = len(result.get("findings", []))
                facts["audit_text"] = [f[:140] for f in result.get("findings", [])][:6]
            else:  # the phone has its own findings (the message must come first, nothing sideways)
                facts["audit_findings_phone"] = len(result.get("findings", []))
                facts["audit_text_phone"] = [f[:140] for f in result.get("findings", [])][:4]
            page.screenshot(path=str(folder / f"{name}.png"), full_page=False)
            page.close()
        browser.close()
    return folder / "desktop.png", folder / "phone.png", facts


async def judge(brief: str, desktop: Path, phone: Path) -> dict[str, object]:
    sys.path.insert(0, str(REPO))
    from forge.config import load_config, load_secrets
    from forge.llm.base import ChatRequest, Message
    from forge.llm.router import LLMRouter
    from forge.net import use_system_certificates
    from forge.vision import images

    use_system_certificates()  # company HTTPS inspection, as the app does at start
    config, secrets = load_config(), load_secrets()
    # The router's own provider factory builds Azure or Gemini by model: the test helper builds Azure only, which made a Gemini scorer fail ("needs deployment_env", first overnight night, 2026-10-16).
    router = LLMRouter(config, secrets)
    if os.environ.get("FORGE_BENCH_SCORER"):  # the same scorer in every condition of an A/B (D-418)
        router.set_role_model("vision", os.environ["FORGE_BENCH_SCORER"])
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


def run_task(task: Path, run_dir: Path, env: dict[str, str], design_from: str = "") -> dict[str, object]:
    meta = json.loads((task / "task.json").read_text(encoding="utf-8"))
    workspace = run_dir / meta["id"]
    remove_tree(workspace)
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
    if (
        design_from
    ):  # arm B of the taste test (DIE8): another model's DESIGN.md is binding, this run only builds
        earlier = RUNS / design_from / meta["id"]
        # The designer may have left DESIGN.md in project/, in the delivered output/ or in the workspace root (office laptop: Argon's was in output/).
        candidates = [
            earlier / "project" / "DESIGN.md",
            earlier / "output" / "DESIGN.md",
            earlier / "DESIGN.md",
        ]
        supplied = next((path for path in candidates if path.is_file()), candidates[0])
        if not supplied.is_file():
            return {
                "id": meta["id"],
                "error": f"no DESIGN.md in {earlier} (looked in project/, output/ and the root) to build from",
            }
        target = workspace / "project" / "DESIGN.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(supplied, target)
        brief += (
            chr(10)
            * 2
            + "A DESIGN.md is already in the project root. It is the user's binding design: build the page to it, "
            "do not redesign, do not write candidate designs, and do not change its tokens."
        )
    prompt_file = run_dir / f"{meta['id']}_prompt.txt"
    prompt_file.write_text(brief, encoding="utf-8")
    started = time.time()
    try:
        driven = subprocess.run(
            [str(PYTHON), str(REPO / "scripts" / "campaign" / "drive_forge.py"), str(workspace), str(prompt_file), str(run_dir / f"{meta['id']}_run.json")],
            env=env, capture_output=True, timeout=3600,
        )  # fmt: skip
        timed_out = False
        # Kept, because a run that ends in seconds (a model that cannot be called) leaves nothing else to read.
        (run_dir / f"{meta['id']}_drive.log").write_text(
            (driven.stdout + driven.stderr).decode("utf-8", errors="replace")[-20000:], encoding="utf-8"
        )
    except subprocess.TimeoutExpired:
        timed_out = True
    row: dict[str, object] = {
        "id": meta["id"],
        "title": meta["title"],
        "timed_out": timed_out,
        "outer_wall_s": round(time.time() - started),
    }
    row.update(timing(workspace / ".forge" / "transcripts" / "events.jsonl"))
    page = next(iter(sorted((workspace / "project").rglob("index.html"))), None) or next(
        iter(sorted((workspace / "output").rglob("index.html"))), None
    )  # the page may have been written only into the delivered output/ folder
    row["delivered"] = page is not None
    row.update(design_facts(workspace))
    if page is None and not timed_out:  # not a pass: say why, from the run's own result file and console
        result_file = run_dir / f"{meta['id']}_run.json"
        reason = (
            result_file.read_text(encoding="utf-8", errors="replace")[:300] if result_file.is_file() else ""
        )
        log_file = run_dir / f"{meta['id']}_drive.log"
        tail = log_file.read_text(encoding="utf-8", errors="replace")[-300:] if log_file.is_file() else ""
        row["error"] = f"no page was delivered. {reason} {tail}".replace(chr(10), " ")
    if page is not None:
        desktop, phone, facts = screenshots(page, run_dir / f"{meta['id']}_shots")
        row.update(facts)
        row["judge"] = asyncio.run(judge(brief, desktop, phone))
    return row


def markdown(name: str, rows: list[dict[str, object]]) -> str:
    lines = [
        f"### Run `{name}` ({time.strftime('%Y-%m-%d %H:%M')})",
        "",
        "| Brief | Wall | Cost | Ladder | DESIGN.md lint (err/warn) | Differs from default in | Audit left (desktop / phone) | Sideways scroll | Judge (type/dist/hier/harm/fit/polish) |",
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
            f"| {r['id']} | {r.get('wall_s')}s{stall_note(r)} | {cost} | {'yes' if r.get('ladder_used') else 'no'} | "  # type: ignore[arg-type]
            f"{r.get('lint_errors', '-')}/{r.get('lint_warnings', '-')} | {r.get('differs_from_default_in', '-')} | {r.get('audit_findings', '-')} / {r.get('audit_findings_phone', '-')} | "
            f"{'desktop ' if r.get('sideways_scroll_desktop') else ''}{'phone' if r.get('sideways_scroll_phone') else 'no'} | {scores} |"
        )
    lines.append("")
    for r in rows:
        judge_row = r.get("judge")
        if isinstance(judge_row, dict) and judge_row.get("worst_problem"):
            lines.append(f"- {r['id']}: judge's worst problem: {judge_row['worst_problem']}")
        if r.get("audit_text"):
            lines.append(f"- {r['id']}: audit left: {r['audit_text']}")
        if r.get("audit_text_phone"):
            lines.append(f"- {r['id']}: audit left on the phone: {r['audit_text_phone']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--tasks", default="")
    parser.add_argument(
        "--mini",
        action="store_true",
        help="run only the small briefs (one section or one screen, about 5 minutes each) for a quick check; without it the full briefs run",
    )
    parser.add_argument("--env", action="append", default=[])
    parser.add_argument(
        "--all-roles",
        default="",
        help="a model key (for example gpt54) used for every role: the builder, the reviewer, the vision judge",
    )
    parser.add_argument(
        "--coder-model",
        default="",
        help="a model key (for example gemini31pro) for the builder roles only (coder, kb_builder, summariser); the reviewer, the vision check and the judge keep their models, so the judge is not the builder's own family",
    )
    parser.add_argument(
        "--critic-model",
        default="",
        help="a model key (for example gemini4argon) for the critic, judge and reviewer roles of the run: the independent design critic and the vote between candidates run on it (D-409, D-418)",
    )
    parser.add_argument(
        "--scorer-model",
        default="",
        help="a model key for the benchmark's own scoring judge, the same in every condition of an A/B (default: the machine's vision model); use a model that built nothing in the run",
    )
    parser.add_argument(
        "--design-from",
        default="",
        help="the name of an earlier run whose DESIGN.md of each brief is given to this run as binding, so only the builder differs (the taste test, DIE8, docs/DESIGN_TASTE_TEST.md)",
    )
    args = parser.parse_args()
    if args.scorer_model:
        os.environ["FORGE_BENCH_SCORER"] = args.scorer_model
    keep_awake()
    run_dir = RUNS / args.name
    run_dir.mkdir(parents=True, exist_ok=True)
    home = run_dir / "home"
    home.mkdir(exist_ok=True)
    if (
        args.coder_model and not args.all_roles
    ):  # an A/B on the designer: only the builder roles change (D-403)
        import yaml

        roles = {role: args.coder_model for role in ("coder", "kb_builder", "summariser")}
        (home / "config.yaml").write_text(yaml.safe_dump({"llm": {"roles": roles}}), encoding="utf-8")
    if args.critic_model and not args.all_roles:  # an A/B on the critic: only the checking roles change
        import yaml

        roles = {role: args.critic_model for role in ("critic", "judge", "reviewer")}
        existing = (
            (home / "config.yaml").read_text(encoding="utf-8") if (home / "config.yaml").exists() else ""
        )
        merged = yaml.safe_load(existing) or {}
        merged.setdefault("llm", {}).setdefault("roles", {}).update(roles)
        (home / "config.yaml").write_text(yaml.safe_dump(merged), encoding="utf-8")
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

    def is_mini(folder: Path) -> bool:
        return bool(json.loads((folder / "task.json").read_text(encoding="utf-8")).get("mini"))

    for task in sorted(
        p
        for p in TASKS.iterdir()
        if (p / "task.json").exists()
        and (not wanted or p.name in wanted)
        and (wanted or is_mini(p) == args.mini)
    ):
        print(f"[{args.name}] {task.name} ...", flush=True)
        rows.append(run_task(task, run_dir, env, args.design_from))
        (run_dir / "results.json").write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")
    report = markdown(args.name, rows)
    (run_dir / "results.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())

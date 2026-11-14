"""`forge laptop`: close the items that need the user's office laptop from photographs (D-615).

    forge laptop plan     the steps to run, in order, with the exact commands and the sentences to type
    forge laptop check    the checks that need no model: setup and sign-in, the Development DB (triggers, rules and
                          functions that delete), the relay with the drivers of the application, the settings of the
                          copy that point at the Development DB
    forge laptop live     the live model tests (TR6)
    forge laptop report   what the real sessions did: sign-in, second run, the requirement, the Development DB
                          tools, speed, knowledge, hand-off cards; the last page lists every item with its verdict

Each command prints short pages (one photograph each) and writes the same pages under
`<DebCraft Home>/laptop_report/`. Nothing on a page is a secret: names, counts, seconds and first words only.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit

from forge.config import forge_home, load_config, load_secrets
from forge.db.connection import DbTarget, connect
from forge.db.dev_guard import dev_settings
from forge.db.dev_proxy import DevProxy
from forge.db.tunnel import TunnelError, ensure_tunnel
from forge.engine.facts_report import newest_workspace, setup_page
from forge.engine.laptop_pages import Page, Verdict, emit, report_folder, save_verdicts, summary_page
from forge.engine.laptop_probe import DRIVERS, PROBE
from forge.engine.laptop_report import (
    dev_database_page,
    live_tests_page,
    load_conversations,
    requirement_page,
    second_run_page,
    speed_page,
    tokens_page,
)
from forge.toolkit import field_log
from forge.workspace.workspace import Workspace

LIVE_FILES = ("test_live_tool_search.py", "test_live_handoff_review.py")
LIVE_TIMEOUT_S = 2400
PROBE_TIMEOUT_S = 150
ENV_KEPT = ("PATH", "SYSTEMROOT", "SystemRoot", "TEMP", "TMP", "USERPROFILE", "HOMEDRIVE", "HOMEPATH")
REMOVING = r"\m(delete|truncate|drop)\M"
CONFIRM = (
    "!!! THIS CHECK WORKS ON THE SHARED DEVELOPMENT DATABASE !!!\n"
    "It opens a connection through DebCraft's relay with each driver of the application and, per driver:\n"
    "  - reads (SELECT 1, a parameter query, a 300 KB answer),\n"
    "  - creates a TEMPORARY table (visible to nobody else; gone when the connection ends),\n"
    "  - inserts 2 rows into it and updates 1, and\n"
    "  - sends one DELETE on that temporary table, which the relay must refuse.\n"
    "Nothing else is created, changed or deleted. Type yes to run it, anything else to skip it: "
)


def _red_input(text: str) -> str:
    """A question about something shared, in red (D-608), answered at the keyboard."""
    from rich.console import Console

    Console().print(text, style="bold red", markup=False, highlight=False)
    return input("> ")


FUNCTIONS_SQL = f"""
SELECT n.nspname, p.proname, p.prokind,
       (l.lanname IN ('sql', 'plpgsql', 'plpython3u', 'plperl', 'plperlu', 'pltcl', 'plv8')
        AND p.prosrc ~* '{REMOVING}') AS removes
FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace JOIN pg_language l ON l.oid = p.prolang
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema') AND n.nspname NOT LIKE 'pg_toast%'
  AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = p.oid AND d.deptype = 'e')
ORDER BY 1, 2
"""
TRIGGERS_SQL = """
SELECT n.nspname || '.' || c.relname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
JOIN pg_namespace n ON n.oid = c.relnamespace WHERE NOT t.tgisinternal ORDER BY 1
"""
RULES_SQL = """
SELECT n.nspname || '.' || c.relname FROM pg_rewrite r JOIN pg_class c ON c.oid = r.ev_class
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE r.ev_type <> '1' AND n.nspname NOT IN ('pg_catalog', 'information_schema') ORDER BY 1
"""
SCHEMAS_SQL = """
SELECT schemaname, count(*) FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema') GROUP BY 1 ORDER BY 2 DESC
"""


def _dev_target(home: Path) -> tuple[DbTarget | None, str, object]:
    """The development connection of DebCraft's own .env: the target, its URL and the secrets, or a reason."""
    secrets = load_secrets(home)
    url = secrets.get("DEV_PG_URL")
    if not url:
        return None, "DEV_PG_URL is not set in DebCraft's .env", secrets
    config = load_config(home).postgres.connections.get("dev")
    return DbTarget("dev", "DEV_PG_URL", config.sslmode if config else "prefer"), url, secrets


def database_page(home: Path, workspace: Path | None) -> Page:
    """DV9 (nothing that deletes behind a statement) and DV10 (settings of the copy that point at this database)."""
    page = Page("THE DEVELOPMENT DATABASE")
    target, url, secrets = _dev_target(home)
    if target is None:
        page.lines.append(f"PROBLEM: {url}")
        page.verdicts += [Verdict("DV9", "NOT RUN", url[:80]), Verdict("DV10", "NOT RUN", url[:80])]
        return page
    started = time.monotonic()
    try:
        note = ensure_tunnel("dev", home)
        page.lines.append(f"tunnel: {note or 'not needed'} ({time.monotonic() - started:.1f}s)")
        with connect(target, secrets, read_only=True) as connection:  # type: ignore[arg-type]
            version = connection.execute("SELECT current_setting('server_version')").fetchone()
            page.lines.append(
                f"connected in {time.monotonic() - started:.1f}s; server {version[0] if version else '?'}"
            )
            schemas = connection.execute(SCHEMAS_SQL).fetchall()
            functions = connection.execute(FUNCTIONS_SQL).fetchall()
            triggers = [row[0] for row in connection.execute(TRIGGERS_SQL).fetchall()]
            rules = [row[0] for row in connection.execute(RULES_SQL).fetchall()]
    except (TunnelError, OSError, Exception) as error:  # any failure is the fact: say it in a line
        page.lines.append(f"CONNECTION FAILED: {' '.join(str(error).split())[:150]}")
        page.verdicts += [
            Verdict("DV9", "NOT RUN", "could not connect"),
            _settings_verdict(page, home, workspace, url),
        ]
        return page
    page.lines.append("schemas with tables: " + ", ".join(f"{name} ({count})" for name, count in schemas[:6]))
    procedures = [f"{schema}.{name}" for schema, name, kind, _ in functions if kind == "p"]
    removing = [f"{schema}.{name}" for schema, name, _, removes in functions if removes]
    page.lines += [
        f"functions of the application: {len(functions)} (procedures {len(procedures)})",
        f"functions whose text has DELETE, TRUNCATE or DROP: {len(removing)}",
        *[f"   {name}" for name in removing[:8]],
        f"triggers: {len(triggers)} {triggers[:3] if triggers else ''}",
        f"rules that are not SELECT: {len(rules)} {rules[:3] if rules else ''}",
        "(the scan reads each function's own text: a function that only calls another is not followed)",
    ]
    page.verdicts.append(
        Verdict("DV9", "PASS", f"{len(functions)} functions, none removes; no triggers; no rules")
        if not (removing or triggers or rules)
        else Verdict(
            "DV9",
            "CHECK",
            f"removing functions {len(removing)}, triggers {len(triggers)}, rules {len(rules)}",
        )
    )
    page.verdicts.append(_settings_verdict(page, home, workspace, url))
    return page


def _settings_verdict(page: Page, home: Path, workspace: Path | None, url: str) -> Verdict:
    """DV10: which settings of the copy hold the Development DB's address (names and files, never values)."""
    root = workspace or newest_workspace(home)
    if root is None:
        page.lines.append("settings of the copy: no project found (use --workspace <project folder>)")
        return Verdict("DV10", "NOT RUN", "no project folder")
    try:
        opened = Workspace.open(root)
        held = dev_settings([opened.repo_dir, opened.app_dir], url)
    except Exception as error:
        page.lines.append(f"settings of the copy: PROBLEM {str(error)[:90]}")
        return Verdict("DV10", "NOT RUN", "project could not be opened")
    page.lines.append(
        f"settings of the copy that point at it: {sorted(held.kinds) or 'none'} in {held.files or '-'}"
    )
    return Verdict(
        "DV10", "PASS", f"{len(held.kinds)} setting(s) found: {', '.join(sorted(held.kinds))[:70] or 'none'}"
    )


# --- the relay with the drivers of the application (DV8) -----------------------------------------------------


async def _run_probe(python: Path, driver: str, env: dict[str, str]) -> dict[str, object]:
    process = await asyncio.create_subprocess_exec(
        str(python),
        "-I",
        "-c",
        PROBE,
        driver,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(process.communicate(), timeout=PROBE_TIMEOUT_S)
    except TimeoutError:
        process.kill()
        return {
            "driver": driver,
            "available": True,
            "steps": [["the probe", "fail", f"no end after {PROBE_TIMEOUT_S}s"]],
        }
    lines = out.decode("utf-8", "replace").strip().splitlines()
    try:
        return json.loads(lines[-1])  # type: ignore[no-any-return]
    except (IndexError, ValueError):
        reason = (err.decode("utf-8", "replace").strip().splitlines() or ["no output"])[-1]
        return {"driver": driver, "available": True, "steps": [["the probe", "fail", reason[:120]]]}


async def _drivers(python: Path, url: str, sslmode: str) -> tuple[list[dict[str, object]], dict[str, object]]:
    parts = urlsplit(url)
    proxy = DevProxy(parts.hostname or "127.0.0.1", parts.port or 5432, sslmode, log=field_log.write)
    port = await proxy.start()
    env = {name: os.environ[name] for name in ENV_KEPT if name in os.environ}
    env.update(
        DEVCHK_HOST="127.0.0.1",
        DEVCHK_PORT=str(port),
        DEVCHK_USER=parts.username or "",
        DEVCHK_PASSWORD=parts.password or "",
        DEVCHK_DB=parts.path.lstrip("/"),
    )
    try:
        results = [await _run_probe(python, driver, env) for driver in DRIVERS]
    finally:
        stats = proxy.stats()
        await proxy.close()
    return results, stats


def drivers_page(home: Path, app_python: Path | None, confirm: Callable[[str], str] = input) -> Page:
    page = Page("THE RELAY WITH THE APPLICATION'S DRIVERS")
    target, url, _ = _dev_target(home)
    if app_python is None or not app_python.is_file():
        page.lines += [
            "NOT RUN: give the Python of the application's own environment:",
            "   forge laptop check --app-python <WisdomNext folder>\\venv\\Scripts\\python.exe",
        ]
        page.verdicts.append(Verdict("DV8", "NOT RUN", "no --app-python"))
        return page
    if target is None:
        page.lines.append(f"PROBLEM: {url}")
        page.verdicts.append(Verdict("DV8", "NOT RUN", url[:80]))
        return page
    if confirm(CONFIRM).strip().lower() != "yes":
        page.lines.append("You skipped the check.")
        page.verdicts.append(Verdict("DV8", "NOT RUN", "skipped by you"))
        return page
    try:
        ensure_tunnel("dev", home)
        results, stats = asyncio.run(_drivers(app_python, url, target.sslmode))
    except (TunnelError, Exception) as error:
        page.lines.append(f"FAILED to start the relay: {' '.join(str(error).split())[:140]}")
        page.verdicts.append(Verdict("DV8", "FAIL", "the relay could not be started"))
        return page
    tested = failed = 0
    for result in results:
        name = str(result["driver"])
        if not result.get("available"):
            page.lines.append(f"{name}: not installed there")
            continue
        raw = result.get("steps", [])
        steps = [step for step in raw if isinstance(step, list)] if isinstance(raw, list) else []
        bad = [step for step in steps if step[1] != "ok"]
        tested += 1
        failed += bool(bad)
        page.lines.append(
            f"{name} {result.get('version', '')}: {len(steps) - len(bad)}/{len(steps)} steps ok"
        )
        page.lines += [f"   FAIL {step[0]}: {step[2]}"[:98] for step in bad[:3]]
    page.lines += [
        f"relay: {stats['connections']} connections, refused {stats['refused_statements']}, "
        f"writing {stats['writing_statements']}, rows {stats['rows']}",
        f"   messages {stats['messages']} errors {stats['errors'] or 'none'}",
    ]
    page.verdicts.append(
        Verdict("DV8", "NOT RUN", "no driver is installed in that Python: is it the application's own?")
        if not tested
        else Verdict("DV8", "FAIL", f"{failed} of {tested} drivers failed a step")
        if failed
        else Verdict("DV8", "PASS", f"{tested} drivers: reads, writes and the refused delete all worked")
    )
    return page


# --- the live model tests (TR6) --------------------------------------------------------------------------------


def live_tests(home: Path, write: Callable[[str], None] = print) -> list[dict[str, object]]:
    root = Path(__file__).resolve().parents[3]
    results: list[dict[str, object]] = []
    for name in LIVE_FILES:
        path = root / "tests" / name
        entry: dict[str, object] = {
            "file": name,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "seconds": 0,
            "notes": [],
        }
        results.append(entry)
        if not path.is_file():
            entry["notes"] = [f"not found: {path}"]
            continue
        write(f"running {name} (up to {LIVE_TIMEOUT_S // 60} minutes) ...")
        started = time.monotonic()
        try:
            done = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-m",
                    "live",
                    "-q",
                    "-rsf",
                    "--tb=line",
                    "-p",
                    "no:cacheprovider",
                    str(path),
                ],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=LIVE_TIMEOUT_S,
                encoding="utf-8",
                errors="replace",
            )
            text = done.stdout + done.stderr
        except subprocess.TimeoutExpired:
            text = "TIMEOUT"
            entry["notes"] = [f"no end after {LIVE_TIMEOUT_S // 60} minutes"]
        entry["seconds"] = round(time.monotonic() - started)
        for count, word in re.findall(r"(\d+) (passed|failed|skipped|error)", text):
            key = "failed" if word == "error" else word
            entry[key] = int(entry[key]) + int(count)  # type: ignore[call-overload]
        notes = [
            " ".join(line.split())
            for line in text.splitlines()
            if line.startswith(("FAILED", "SKIPPED", "ERROR"))
        ]
        entry["notes"] = [*entry["notes"], *notes[:6]]  # type: ignore[misc]
        if not any(entry[k] for k in ("passed", "failed", "skipped")) and not entry["notes"]:
            entry["notes"] = [" ".join(text.split())[-120:] or "no output"]
    folder = report_folder(home)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "live_tests.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    return results


# --- the plan --------------------------------------------------------------------------------------------------


def plan_page() -> Page:
    cli = "& $py -m forge.cli laptop"
    page = Page("THE STEPS (run them in this order; photograph what each prints)")
    page.lines += [
        "0. Pull the code. In PowerShell, from the DebCraft folder, once:",
        f'   $py = "{sys.executable}"',
        "1. Then:",
        f"   {cli} check --app-python <WisdomNext>\\venv\\Scripts\\python.exe `",
        "      --workspace <project folder>",
        "   about 3 minutes; type yes once (a TEMP table on the Development DB). Items TK5 DV8 DV9 DV10",
        "2. Up to 40 minutes (it calls the model; leave it running):",
        f"   {cli} live                                                    items TR6 RS15",
        "3. Open DebCraft on the WisdomNext project, a NEW conversation, type exactly:",
        '   "Sign in to dev and to SIT with app_login, then check both with app_token_status."   TK5',
        "   Close DebCraft. Open it again, a NEW conversation, type the same sentence. If you can,",
        "   once more after the token has run out (about an hour): that shows a sign-in without a window.",
        "4. A NEW conversation, type (put in your agent and its question):",
        '   "Run the <agent> agent once with the question <question> through its API."    item RN2',
        "   Wait for the answer. Close DebCraft. Open it again, a NEW conversation, type:",
        '   "Run the same agent again with the same question."',
        "5. A NEW conversation: type your real requirement for the LangChain agent and let it finish.",
        "   Approve the cards as you would for real; do not add hints.      items RS7 RS11 DB2 RS15 DV8 DV10",
        "6. A NEW conversation, type:  /learn   then, when it ends:",
        '   "Where are the orchestration, the common LLM gateway and the file operations in this code?"  KL6',
        "7. Then:",
        f"   {cli} report --workspace <project folder>",
        "   Photograph every page. The last page lists all items with PASS, CHECK, FAIL or NOT RUN.",
        "",
        "If a step fails or a page says NOT RUN, photograph that screen too and go on.",
    ]
    return page


# --- the commands ----------------------------------------------------------------------------------------------


def _record(pages: list[Page], home: Path) -> None:
    """Keeps the verdicts for the summary page; a NOT RUN never replaces an earlier real verdict."""
    from forge.engine.laptop_pages import load_verdicts

    stored = load_verdicts(home)
    keep = [v for page in pages for v in page.verdicts if not (v.status == "NOT RUN" and v.item in stored)]
    save_verdicts(keep, home)


def run(
    action: str,
    app_python: Path | None = None,
    workspace: Path | None = None,
    pause: bool = True,
    home: Path | None = None,
    write: Callable[[str], None] = print,
    wait: Callable[[str], str] = input,
) -> int:
    home = home or forge_home()
    if action == "plan":
        emit([plan_page()], "plan", pause=False, home=home, write=write, wait=wait)
        return 0
    if action == "live":
        results = live_tests(home, write)
        pages = [live_tests_page(home)]
        _record(pages, home)
        emit([*pages, summary_page(home)], "live", pause, home, write, wait)
        return 0 if all(not r["failed"] for r in results) else 1
    root = workspace or newest_workspace(home)
    if action == "check":
        setup = Page("SETUP", [line for line in setup_page(home)[1:]])
        pages = [
            setup,
            tokens_page([], home, with_cards=False),
            database_page(home, root),
            drivers_page(home, app_python, _red_input if wait is input else wait),
        ]
        _record(pages, home)
        emit([*pages, summary_page(home)], "check", pause, home, write, wait)
        return 0
    if action == "report":
        conversations = load_conversations(root) if root else []
        if root is None or not conversations:
            write("No conversation was found. Give --workspace <project folder> of the project you used.")
        pages = [
            tokens_page(conversations, home),
            second_run_page(conversations, root or Path(".")),
            requirement_page(conversations),
            dev_database_page(conversations, home),
            speed_page(conversations),
            live_tests_page(home),
        ]
        _record(pages, home)
        emit([*pages, summary_page(home)], "report", pause, home, write, wait)
        return 0
    write(f"unknown action {action!r}: plan, check, live or report")
    return 2

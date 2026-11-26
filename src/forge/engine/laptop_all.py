"""`forge laptop all` (`Laptop-Report.cmd`): what the office laptop owes, in one run, with no questions (D-660, D-661).

Nothing here runs on WisdomNext or its Development DB (the user's choice, D-661). It shows the roles as DebCraft will use
them, checks Gemini 4 Argon step by step, makes a test project of the sample repository shipped with DebCraft and holds
two conversations there (a task planned by the two planners, a Tavily crawl), approving ordinary cards as a run nobody
watches does, runs the live tests and ends with the pages to photograph.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from forge.config import load_config
from forge.engine.headless import auto_reply
from forge.engine.laptop_pages import Page, Verdict, report_folder
from forge.engine.laptop_report import load_conversations
from forge.engine.session_host import SessionHost
from forge.protocol.events import EventType
from forge.protocol.inputs import Interrupt, SendMessage
from forge.workspace.conversations import ConversationStore
from forge.workspace.workspace import Workspace

SessionFactory = Callable[[Workspace], SessionHost]
# The items this run closes (D-661): none of them runs anything on WisdomNext or its Development DB.
COVERED = ("GM1", "GQ1", "DP1", "TV1", "TR6")
PLAN_TASK = (
    "Plan this with the planner subagent (spawn_subagent, agent planner) and show me its plan; do not build it. "
    "Task: add an endpoint to the backend that answers questions about the stored records, also when a question "
    "is worded differently from the data, with tests."
)
CRAWL_SITE = "https://docs.python.org/3/"


def conversations_to_hold() -> list[tuple[str, list[str], int]]:
    """(items, what is typed one message after the other, minutes at most) for each new conversation."""
    return [
        ("DP1", [PLAN_TASK], 30),
        ("TV1", [f"Crawl {CRAWL_SITE} with tavily_crawl and list the pages you found."], 10),
    ]


def make_test_project(home: Path, repo: Path) -> Path:
    """A new DebCraft project of the sample repository shipped with DebCraft; WisdomNext is never opened."""
    from forge.workspace.create import create_workspace

    root = report_folder(home) / f"test-project-{datetime.now():%Y%m%d-%H%M%S}"
    create_workspace(repo / "tests" / "fixtures" / "sample_repo", root, "backend")
    return root


async def _until_idle(host: SessionHost, limit: float) -> bool:
    """True when the turn ended by itself within `limit` seconds."""
    began = time.monotonic()
    while not host.busy and host.inputs_empty and time.monotonic() - began < 30:
        await asyncio.sleep(0.5)  # the turn has not started yet
    while time.monotonic() - began < limit:
        if not host.busy and host.inputs_empty:
            return True
        await asyncio.sleep(1)
    return False


async def hold(
    root: Path,
    make_session: SessionFactory,
    title: str,
    texts: list[str],
    minutes: int,
    write: Callable[[str], None],
) -> str:
    """One new conversation of the project: each text after the previous turn ended. Returns how it went."""
    ConversationStore(Workspace.open(root)).create(title)
    host = make_session(Workspace.open(root))
    subscription = host.bus.subscribe(since_seq=host.bus.last_seq)
    errors: list[str] = []

    async def answer() -> None:
        async for event in subscription:
            if event.type == EventType.ERROR:
                errors.append(str(event.payload.get("message"))[:120])
            if (reply := auto_reply(event, auto_approve=True)) is not None:
                await host.submit(reply)

    responder = asyncio.create_task(answer())
    runner = asyncio.create_task(host.run())
    outcome = "finished"
    try:
        deadline = time.monotonic() + minutes * 60
        for text in texts:
            await host.submit(SendMessage(text=text))
            if not await _until_idle(host, max(60.0, deadline - time.monotonic())):
                await host.submit(Interrupt())
                await asyncio.sleep(5)
                outcome = f"stopped after {minutes} min"
                break
    finally:
        subscription.close()
        await host.close()
        for task in (responder, runner):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
    result = outcome + (f"; error: {errors[-1]}" if errors else "")
    write(f"  {title}: {result}")
    return result


async def hold_all(root: Path, make_session: SessionFactory, write: Callable[[str], None]) -> list[str]:
    lines = []
    for items, texts, minutes in conversations_to_hold():
        write(f"{datetime.now():%H:%M} {items}: {texts[0][:70]} (up to {minutes} min)")
        try:
            lines.append(
                f"{items}: {await hold(root, make_session, f'laptop {items}', texts, minutes, write)}"
            )
        except Exception as error:  # one conversation that breaks must not end the run
            lines.append(f"{items}: broke: {type(error).__name__}: {str(error)[:100]}")
            write(f"  broke: {error}")
    return lines


def crawl_page(root: Path) -> Page:
    """TV1 alone from the calls page: the test project has no sign-in or stream to report."""
    from forge.engine.laptop_report_more import calls_page

    full = calls_page(load_conversations(root), None)
    return Page(
        "TAVILY CRAWL (TV1)",
        [line for line in full.lines if "tavily" in line],
        [verdict for verdict in full.verdicts if verdict.item == "TV1"],
    )


def roles_page(home: Path, make_router: Callable[[], Any]) -> Page:
    """GM1: the model of every role as DebCraft will use it, and the two planners."""
    page = Page("THE ROLES AS SET (GM1, DP1)")
    router = make_router()
    llm = router.config.llm
    for role, key in router.role_models.items():
        page.lines.append(f"{role:<11} {key}")
    ready = [key for key in llm.plan_twice if key in llm.models and router._configured(key)]
    page.lines += [
        "",
        f"two planners: {', '.join(llm.plan_twice) or 'off'} (set up: {', '.join(ready) or 'none'}); merger {llm.plan_merger}",
    ]
    coder = router.role_models.get("coder")
    page.verdicts.append(
        Verdict(
            "GM1",
            "PASS" if coder == "gemini4hydrogen" else "CHECK",
            f"coder {coder}, judge {router.role_models.get('judge')}",
        )
    )
    return page


def dual_plan_page(root: Path | None) -> Page:
    """DP1: did a planner run twice, and what came of the merge."""
    page = Page("TWO PLANNERS (DP1)")
    cards = plans = merged = 0
    for conversation in load_conversations(root) if root else []:
        for event in conversation.events:
            text = json.dumps(event.payload)
            if event.type == EventType.QUESTION_ASKED and "Two plans differ" in text:
                cards += 1
                page.lines.append("card: " + str(event.payload.get("question", ""))[:90])
            if event.type == EventType.TOOL_CALL_FINISHED and "[planner" in text:
                plans += 1
                merged += "Decided between the two plans" in text or "agreed on every point" in text
    page.lines.append(f"planner calls {plans}, merged plans {merged}, cards {cards}")
    status = "PASS" if merged else ("CHECK" if plans else "NOT RUN")
    page.verdicts.append(Verdict("DP1", status, f"{plans} plan(s), {merged} merged, {cards} card(s)"))
    return page


def gemini_page(repo: Path, write: Callable[[str], None]) -> Page:
    """GQ1: every step of the Gemini provider check on Gemini 4 Argon."""
    page = Page("GEMINI 4 ARGON, STEP BY STEP (GQ1)")
    script = repo / "scripts" / "dev" / "gemini_smoke.py"
    if not script.is_file():
        page.verdicts.append(Verdict("GQ1", "NOT RUN", "scripts/dev/gemini_smoke.py is missing"))
        return page
    write(f"{datetime.now():%H:%M} GQ1: the Gemini check (a few minutes)")
    try:
        done = subprocess.run(
            [sys.executable, str(script), "gemini-4-argon"],
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
            cwd=repo,
        )
    except subprocess.TimeoutExpired:
        page.verdicts.append(Verdict("GQ1", "FAIL", "no end within 15 minutes"))
        return page
    lines = [line for line in done.stdout.splitlines() if "OK" in line or "FAIL" in line]
    page.lines += [line[:100] for line in lines[-20:]]
    failed = sum("FAIL" in line for line in lines)
    status = "PASS" if done.returncode == 0 and not failed else "FAIL"
    page.verdicts.append(Verdict("GQ1", status, f"{len(lines) - failed} steps OK, {failed} failed"))
    return page


def role_challenge_page(home: Path) -> Page:
    """Why the coder runs of the last role challenge ended (D-657)."""
    page = Page("ROLE CHALLENGE: HOW THE CODER TURNS ENDED")
    runs = sorted((home / "reports" / "role-challenge").glob("2*/results.json"))
    if not runs:
        page.lines.append("no role challenge yet")
        return page
    rows = json.loads(runs[-1].read_text(encoding="utf-8"))["rows"]
    for row in (r for r in rows if r["role"] == "coder"):
        ends = [f for f in row.get("failed_calls") or [] if str(f).startswith("ERROR")]
        page.lines.append(f"{row['model']} {row['repeat'] + 1}: {row.get('note', '')[:60]}")
        page.lines += [f"   {str(end)[:95]}" for end in ends[:3]]
    return page


def load_config_router(home: Path) -> Callable[[], Any]:
    def make() -> Any:
        from forge.config import load_secrets
        from forge.environment.plan import apply_saved_plan
        from forge.llm.router import LLMRouter

        router = LLMRouter(load_config(home), load_secrets(home))
        apply_saved_plan(router, home)
        return router

    return make

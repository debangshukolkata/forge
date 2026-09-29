"""The browser smoke-check rung D-138 deferred and D-139 left as a comment in `verify/react_ladder.py`:
loads the React app in a headless browser once, at export, and reports what happened. Informational only
(D-132: verification is judgment-based, never a mandatory gate) — this never blocks or fails
`Orchestrator._export()`; it only adds a section to the export report.

Mechanism: starts the app's own dev/start/preview script (from `NodeEnvironment.dev_command`, never a
literal command Forge invents) as a background process on a free port, the same
`BackgroundManager`/`start_process` machinery `tools/background.py`'s `StartBackground` tool uses — called
directly here since this is an orchestrator-triggered check, not a model tool call. Once the port is open (or
a timeout passes), it opens the page with the existing `tools/browser.py` `BrowserSession` (D-083) and reads
its `console` log for `[pageerror]` entries. The background server is always stopped again right after,
win or lose, so nothing is left running for the rest of the session.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass

from forge.tools.background import BackgroundProcess, free_port, port_open
from forge.tools.base import ToolContext
from forge.tools.browser import BrowserSession
from forge.tools.powershell import build_script, kill_tree, start_process
from forge.workspace.nodeenv import NodeEnvironment

READY_TIMEOUT_S = 45
READY_POLL_S = 0.3
MIN_BODY_CHARS = 40  # a reasonable "isn't just a blank page" bar (v1; see report docstring for rationale)
_PAGEERROR = re.compile(r"^\[pageerror\]")


@dataclass
class SmokeCheckResult:
    """Outcome of one browser smoke check. `skipped` covers everything that must never fail export outright
    (no dev command, no browser available, the server never became ready) — mirroring `StepResult.skipped`
    from `verify/ladder.py` even though this isn't a verify rung."""

    ok: bool
    skipped: bool
    url: str | None
    detail: str


async def run_frontend_smoke_check(context: ToolContext, node_env: NodeEnvironment) -> SmokeCheckResult:
    """Starts the app's dev/preview server, loads it in a headless browser, and reports pass/fail/skip.
    Never raises: every failure mode (no dev script, no port opened in time, no browser installed, a page
    that errors) is caught and turned into a SmokeCheckResult so the caller can treat this as
    informational."""
    if node_env.dev_command is None:
        return SmokeCheckResult(
            ok=False, skipped=True, url=None, detail="the repo defines no dev/start/preview script to run"
        )
    assert context.shell is not None
    port = free_port()
    command = node_env.dev_command
    url = f"http://127.0.0.1:{port}"
    process = await _start_dev_server(context, command, port)
    if process is None:
        return SmokeCheckResult(
            ok=False, skipped=True, url=url, detail=f"could not start '{command}' as a background process"
        )
    try:
        ready = await _wait_for_port(port, READY_TIMEOUT_S)
        if not ready:
            return SmokeCheckResult(
                ok=False,
                skipped=True,
                url=url,
                detail=f"the dev server never became ready within {READY_TIMEOUT_S}s (tried {url})",
            )
        return await _check_page(url)
    finally:
        await _stop_dev_server(process)


async def _start_dev_server(context: ToolContext, command: str, port: int) -> BackgroundProcess | None:
    """Mirrors `StartBackground.run()`'s process-start mechanics (tools/background.py) directly, bypassing
    the Tool wrapper: this is a system-triggered check, not a model tool call, so there's no approval to ask
    for and no tool-result envelope to fill. A start failure (bad command, sandbox unavailable and the
    fallback also failing) is reported as None rather than raised, per the "never crash export" contract."""
    shell = context.shell
    assert shell is not None
    resolved = command.replace("{port}", str(port))
    script = build_script(resolved, shell.cwd, None)
    try:
        sandboxed = shell.prepare_sandbox()
        process = await start_process(script, shell.cwd, shell.environment(), sandboxed)
    except Exception:
        try:
            process = await start_process(script, shell.cwd, shell.environment())
        except Exception:
            return None
    return BackgroundProcess(name="frontend-smoke-check", command=resolved, process=process, port=port)


async def _wait_for_port(port: int, timeout_s: float) -> bool:
    deadline = asyncio.get_running_loop().time() + timeout_s
    while asyncio.get_running_loop().time() < deadline:
        if port_open(port):
            return True
        await asyncio.sleep(READY_POLL_S)
    return False


async def _check_page(url: str) -> SmokeCheckResult:
    """Pass = the page loaded (a response came back), no [pageerror] console entries, and the body isn't
    next-to-empty. This is the simple v1 bar per D-138's deferral note: no DOM-structure heuristics beyond
    a body-text length check, reusing BrowserSession's own console capture (tools/browser.py) rather than
    inventing a second one."""
    session = BrowserSession()
    try:
        page = await session.ensure()
    except Exception as error:
        return SmokeCheckResult(
            ok=False, skipped=True, url=url, detail=f"no browser could be started: {error}"
        )
    try:
        try:
            response = await page.goto(url, wait_until="networkidle", timeout=15_000)
        except Exception as error:
            return SmokeCheckResult(
                ok=False, skipped=False, url=url, detail=f"the page did not load: {error}"
            )
        status = response.status if response is not None else None
        page_errors = [line for line in session.console if _PAGEERROR.match(line)]
        try:
            body_text = await page.inner_text("body")
        except Exception:
            body_text = ""
        blank = len(body_text.strip()) < MIN_BODY_CHARS
        if status is not None and status >= 400:
            return SmokeCheckResult(ok=False, skipped=False, url=url, detail=f"HTTP {status}")
        if page_errors:
            return SmokeCheckResult(
                ok=False, skipped=False, url=url, detail="console errors:\n" + "\n".join(page_errors[:10])
            )
        if blank:
            return SmokeCheckResult(
                ok=False, skipped=False, url=url, detail="the page rendered next to no visible text"
            )
        return SmokeCheckResult(ok=True, skipped=False, url=url, detail=f"HTTP {status}, no console errors")
    finally:
        await session.close()


async def _stop_dev_server(process: BackgroundProcess) -> None:
    """Always stops the one server this check started, regardless of outcome — it never joins the session's
    long-lived BackgroundManager, so there's nothing for `SessionHost`'s end-of-session `stop_all()` to do
    for it and nothing left running once `_export()` returns."""
    kill_tree(process.process.pid)


def render_smoke_check_section(result: SmokeCheckResult) -> str:
    """Mirrors the `## Restructure check` block's style in `Orchestrator._export()` — informational
    markdown, never a reason to fail export."""
    if result.skipped:
        verdict = f"SKIPPED: {result.detail}"
    else:
        verdict = "PASSED" if result.ok else f"FAILED: {result.detail}"
    url_line = f"URL checked: {result.url}\n" if result.url else ""
    return f"\n\n## Frontend smoke check\n\n{url_line}{verdict}\n"

"""show_app: opens the running app in the user's own browser, after checking it is really the app (D-243).

A dev server's port is often taken by some other program, so "the port answers" proves nothing. The page is
opened only when (1) the background process is still running, (2) the port belongs to that process or one
of its children, and (3) a request to the page gets an answer that is not a server error. Otherwise the
tool says what is wrong, so the model can fix it (another port, a crash) instead of opening a wrong page."""

from __future__ import annotations

import asyncio
import re
import webbrowser
from typing import Any

import httpx
import psutil
from pydantic import Field

from forge.toolkit.background import BackgroundProcess
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult

LOCAL_ADDRESS_IN_OUTPUT = re.compile(r"(?:127\.0\.0\.1|localhost|0\.0\.0\.0|\[::1?\]):(\d{2,5})")
ANSWER_TIMEOUT_S = 20
ANSWER_RETRY_S = 1.0


def ports_in_output(lines: list[str]) -> list[int]:
    """Ports the process itself printed (newest first), e.g. 'Running on http://127.0.0.1:5055'."""
    found: list[int] = []
    for line in reversed(lines):
        for match in LOCAL_ADDRESS_IN_OUTPUT.finditer(line):
            port = int(match.group(1))
            if port not in found:
                found.append(port)
    return found


def listening_ports_of(pid: int) -> set[int] | None:
    """Ports the process and its children listen on; None when the system won't tell us."""
    try:
        root = psutil.Process(pid)
        owners = [root, *root.children(recursive=True)]
        ports: set[int] = set()
        for owner in owners:
            try:
                connections = owner.net_connections(kind="inet")
            except (psutil.NoSuchProcess, psutil.ZombieProcess):
                continue
            ports |= {c.laddr.port for c in connections if c.status == psutil.CONN_LISTEN and c.laddr}
        return ports
    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
        return None


def who_listens_on(port: int) -> str:
    """'name (pid N)' of whatever holds the port, for the message; empty when unknown."""
    try:
        for connection in psutil.net_connections(kind="inet"):
            if connection.status == psutil.CONN_LISTEN and connection.laddr and connection.laddr.port == port:
                if connection.pid is None:
                    return ""
                return f"{psutil.Process(connection.pid).name()} (pid {connection.pid})"
    except (psutil.Error, OSError):
        pass
    return ""


def choose_port(entry: BackgroundProcess, wanted: int | None) -> tuple[int | None, str]:
    """The app's port and, when it cannot be settled, why. Prefers a port the app listens on."""
    candidates = [p for p in (wanted, entry.port, *ports_in_output(list(entry.lines))) if p]
    owned = listening_ports_of(entry.process.pid)
    if owned is None:
        # The system would not list the process's sockets: fall back to what the app said about itself.
        return (candidates[0], "") if candidates else (None, "the app has not said which port it uses")
    for port in candidates:
        if port in owned:
            return port, ""
    if owned:
        return min(owned), ""  # the app moved to a port nobody told us about
    if candidates:
        holder = who_listens_on(candidates[0])
        taken = f" Port {candidates[0]} is held by {holder}." if holder else ""
        return None, f"the app is not listening on any port yet.{taken}"
    return None, "the app is not listening on any port yet"


async def wait_for_answer(url: str) -> tuple[bool, str]:
    deadline = asyncio.get_running_loop().time() + ANSWER_TIMEOUT_S
    reason = "no answer"
    async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
        while True:
            try:
                response = await client.get(url)
                if response.status_code < 500:
                    return True, f"HTTP {response.status_code}"
                reason = f"the page answers with HTTP {response.status_code}"
            except httpx.HTTPError as error:
                reason = f"no answer ({type(error).__name__})"
            if asyncio.get_running_loop().time() >= deadline:
                return False, reason
            await asyncio.sleep(ANSWER_RETRY_S)


class ShowApp(Tool):
    name = "show_app"
    description = (
        "Open the running app in the user's own browser window, after checking that the page really comes "
        "from the background process `name` (not from another program on the same port). Use it once, when "
        "the user asked to run or see the app and start_background reports it ready. If it fails, fix the "
        "reason it names (a crashed app, a wrong port) and call it again. Local app only."
    )

    class Args(ToolArgs):
        name: str = Field(description="The name given to start_background.")
        path: str = Field(default="/", description="Page to open, e.g. '/' or '/docs'.")
        port: int | None = Field(default=None, description="Only when the app prints a port you must use.")

    def summary(self, args: ShowApp.Args) -> str:
        return f"show '{args.name}' in the browser"

    async def run(self, args: ShowApp.Args, context: ToolContext) -> ToolResult:
        manager = context.background
        entry = manager.processes.get(args.name) if manager is not None else None
        if entry is None:
            return ToolResult(ok=False, content=f"No background process named '{args.name}': start it first.")
        if not entry.running:
            recent = "\n".join(list(entry.lines)[-15:])
            return ToolResult(ok=False, content=f"'{args.name}' has stopped:\n{recent}")
        port, problem = await asyncio.to_thread(choose_port, entry, args.port)
        if port is None:
            recent = "\n".join(list(entry.lines)[-10:])
            return ToolResult(ok=False, content=f"Not opened: {problem}\n{recent}")
        url = f"http://127.0.0.1:{port}/{args.path.lstrip('/')}"
        answered, detail = await wait_for_answer(url)
        if not answered:
            return ToolResult(ok=False, content=f"Not opened: {url} gave {detail}.")
        opened: Any = await asyncio.to_thread(webbrowser.open, url)
        if not opened:
            return ToolResult(
                ok=True,
                content=f"The app answers at {url} ({detail}), but no browser could be opened here. "
                "Tell the user the link.",
            )
        return ToolResult(ok=True, content=f"Opened {url} in the user's browser ({detail}).")

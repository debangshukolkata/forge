"""Background processes such as dev servers (spec §9.3). All are stopped when the session ends."""

from __future__ import annotations

import asyncio
import re
import socket
from collections import deque
from dataclasses import dataclass, field

from pydantic import Field

from forge.safety.sandbox import SandboxedProcess, SandboxUnavailableError
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.toolkit.powershell import build_script, kill_tree, start_process
from forge.toolkit.progress import ProgressTracker

READY_TIMEOUT_S = 60
FAILURE_SIGNS = re.compile(
    r"Traceback|\bFAILED\b|\bERROR\b|Killed|Segmentation fault|\bfatal:", re.IGNORECASE
)
KEPT_LINES = 2000
PORT_PLACEHOLDER = "{port}"


@dataclass
class BackgroundProcess:
    name: str
    command: str
    process: asyncio.subprocess.Process | SandboxedProcess
    port: int | None
    lines: deque[str] = field(default_factory=lambda: deque(maxlen=KEPT_LINES))
    reader: asyncio.Task[None] | None = None
    total_lines: int = 0  # every line the process has printed, also those that scrolled out of `lines`

    @property
    def running(self) -> bool:
        return self.process.returncode is None


class BackgroundManager:
    def __init__(self) -> None:
        self.processes: dict[str, BackgroundProcess] = {}

    async def stop(self, name: str) -> bool:
        entry = self.processes.pop(name, None)
        if entry is None:
            return False
        kill_tree(entry.process.pid)
        if entry.reader is not None:
            entry.reader.cancel()
        return True

    async def stop_all(self) -> None:
        for name in list(self.processes):
            await self.stop(name)


def free_port(start: int = 5055) -> int:
    for port in range(start, start + 200):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("no free port found")


def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        return probe.connect_ex(("127.0.0.1", port)) == 0


class StartBackground(Tool):
    name = "start_background"
    description = (
        "Start a long-running process (e.g. a dev server) and wait until it is ready. Put {port} in the "
        "command to get a free port, e.g. 'python -m flask --app app:create_app run --port {port}'. "
        "Readiness: the port accepting connections, or ready_pattern appearing in the output."
    )

    class Args(ToolArgs):
        name: str = Field(description="Short name used to read or stop it later.")
        command: str
        ready_pattern: str | None = Field(default=None, description="Regex that means 'ready' in the output.")
        timeout_s: int = Field(default=READY_TIMEOUT_S, ge=1, le=300)

    def summary(self, args: StartBackground.Args) -> str:
        return f"start '{args.name}': {args.command}"

    def command(self, args: StartBackground.Args, context: ToolContext) -> str:
        return args.command.replace(PORT_PLACEHOLDER, "5055")

    async def run(self, args: StartBackground.Args, context: ToolContext) -> ToolResult:
        shell, manager = context.shell, context.background
        assert shell is not None and manager is not None
        if args.name in manager.processes:
            await manager.stop(args.name)
        port = free_port() if PORT_PLACEHOLDER in args.command else None
        command = args.command.replace(PORT_PLACEHOLDER, str(port)) if port else args.command
        script = build_script(command, shell.cwd, None)
        sandboxed = shell.prepare_sandbox()
        try:
            process = await start_process(script, shell.cwd, shell.environment(), sandboxed)
        except SandboxUnavailableError as error:
            shell.disable_sandbox(str(error))
            process = await start_process(script, shell.cwd, shell.environment())
        entry = BackgroundProcess(args.name, command, process, port)
        entry.reader = asyncio.create_task(_collect(entry))
        manager.processes[args.name] = entry
        ready = await _wait_until_ready(entry, args.ready_pattern, args.timeout_s)
        recent = "\n".join(list(entry.lines)[-20:])
        if not entry.running:
            await manager.stop(args.name)
            return ToolResult(
                ok=False, content=f"'{args.name}' exited with code {process.returncode}:\n{recent}"
            )
        where = f" on http://127.0.0.1:{port}" if port else ""
        status = "ready" if ready else f"started but not confirmed ready after {args.timeout_s}s"
        return ToolResult(ok=ready, content=f"'{args.name}' {status}{where}.\n{recent}", meta={"port": port})


class ReadBackground(Tool):
    name = "read_background"
    output_kind = "shell"
    read_only = True
    description = "Show the latest output lines of a background process."

    class Args(ToolArgs):
        name: str
        tail: int = Field(default=50, ge=1, le=KEPT_LINES)

    async def run(self, args: ReadBackground.Args, context: ToolContext) -> ToolResult:
        manager = context.background
        assert manager is not None
        entry = manager.processes.get(args.name)
        if entry is None:
            return ToolResult(ok=False, content=f"No background process named '{args.name}'.")
        state = "running" if entry.running else f"exited ({entry.process.returncode})"
        text, _ = context.cap_output("\n".join(list(entry.lines)[-args.tail :]), "shell")
        return ToolResult(ok=True, content=f"[{state}]\n{text}")


class Monitor(Tool):
    name = "monitor"
    output_kind = "shell"
    read_only = True
    description = (
        "Wait for a background process: returns as soon as `until` (a regex) appears in its output, or the "
        "process exits (with its exit code), or the timeout passes (the process keeps running), with "
        "the new output. While it waits the user sees the newest line and any progress figure. Use it "
        "instead of calling read_background in a loop, e.g. after start_background to wait for a build "
        "or 'Running on'. Make `until` cover failure as well as success (for example "
        "'passed|failed|error|Traceback'): silence is not success, so check the exit code or the "
        "failure lines too."
    )

    class Args(ToolArgs):
        name: str
        until: str | None = Field(default=None, description="Regex to wait for in the output.")
        timeout_s: int = Field(default=60, ge=1, le=300)

    def summary(self, args: Monitor.Args) -> str:
        return f"monitor {args.name}" + (f" until /{args.until}/" if args.until else "")

    async def run(self, args: Monitor.Args, context: ToolContext) -> ToolResult:
        manager = context.background
        assert manager is not None
        entry = manager.processes.get(args.name)
        if entry is None:
            return ToolResult(ok=False, content=f"No background process named '{args.name}'.")
        try:
            regex = re.compile(args.until) if args.until else None
        except re.error as error:
            return ToolResult(ok=False, content=f"Invalid regex: {error}")
        seen = entry.total_lines  # output printed from now on counts as new
        tracker = ProgressTracker(
            lambda progress: context.emit(
                "tool_progress", {"source": "monitor", "name": args.name, **progress}
            )
        )
        fed = entry.total_lines
        deadline = asyncio.get_running_loop().time() + args.timeout_s
        outcome = "timeout"
        while True:
            if regex is not None and any(regex.search(line) for line in entry.lines):
                outcome = "matched"
                break
            if not entry.running:
                outcome = "exited"
                break
            if asyncio.get_running_loop().time() >= deadline:
                break
            await asyncio.sleep(0.2)
            news = max(entry.total_lines - fed, 0)
            if news:
                tracker.feed("\n".join(list(entry.lines)[-news:]) + "\n")
                fed = entry.total_lines
            await tracker.tick()
        fresh = max(entry.total_lines - seen, 0)
        shown = list(entry.lines)[-fresh:] if fresh else []
        text, _ = context.cap_output("\n".join(shown), "shell")
        state = {
            "matched": "pattern matched; still running" if entry.running else "pattern matched; exited",
            "exited": f"exited ({entry.process.returncode})",
            "timeout": f"timed out after {args.timeout_s}s; still running",
        }[outcome]
        trouble = (
            "\n[the output shows trouble: look at the Traceback / error lines above]"
            if FAILURE_SIGNS.search(text)
            else ""
        )
        return ToolResult(ok=True, content=(f"[{state}]\n{text}" if text else f"[{state}]") + trouble)


class StopBackground(Tool):
    name = "stop_background"
    description = "Stop a background process and all its child processes."

    class Args(ToolArgs):
        name: str

    async def run(self, args: StopBackground.Args, context: ToolContext) -> ToolResult:
        manager = context.background
        assert manager is not None
        stopped = await manager.stop(args.name)
        return ToolResult(
            ok=stopped, content=f"Stopped '{args.name}'." if stopped else f"No process '{args.name}'."
        )


async def _collect(entry: BackgroundProcess) -> None:
    assert entry.process.stdout is not None
    while line := await entry.process.stdout.readline():
        entry.lines.append(line.decode("utf-8", errors="replace").rstrip("\r\n"))
        entry.total_lines += 1


async def _wait_until_ready(entry: BackgroundProcess, pattern: str | None, timeout_s: int) -> bool:
    regex = re.compile(pattern) if pattern else None
    deadline = asyncio.get_running_loop().time() + timeout_s
    while asyncio.get_running_loop().time() < deadline and entry.running:
        if regex is not None and any(regex.search(line) for line in entry.lines):
            return True
        if regex is None and entry.port is not None and port_open(entry.port):
            return True
        if regex is None and entry.port is None:
            return True  # nothing to wait for
        await asyncio.sleep(0.3)
    return False

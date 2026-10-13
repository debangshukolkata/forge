"""X3: which shell commands may overlap, and that overlapping ones still ask one at a time."""

from __future__ import annotations

import pytest

from forge.agent.parallel import is_parallel_safe_command, is_test_command


@pytest.mark.parametrize(
    "command",
    [
        "ruff check .",
        "python -m ruff check src",
        "ruff format --check .",
        "mypy",
        "python -m mypy src",
        "npx tsc --noEmit",
        "pytest -q tests/test_a.py",
        "python -m pytest -q",
        "black --check .",
        "ls src",
        "cat README.md",
    ],
)
def test_checks_and_reads_may_overlap(command: str) -> None:
    assert is_parallel_safe_command(command)


@pytest.mark.parametrize(
    "command",
    [
        "",
        "ruff check --fix .",
        "ruff format .",
        "black .",
        "npm install",
        "pip install x",
        "npm run build",
        "python app.py",
        "git commit -am x",
        "ruff check . && pytest",
        "ruff check . > out.txt",
        "pytest; rm -rf x",
        "cat $(whoami)",
        "ls | del x",
        "start-process foo",
    ],
)
def test_anything_that_changes_things_or_chains_runs_alone(command: str) -> None:
    assert not is_parallel_safe_command(command)


def test_test_runs_are_recognised() -> None:
    assert is_test_command("python -m pytest -q") and is_test_command("pytest")
    assert not is_test_command("ruff check .")


async def test_checks_overlap_but_two_test_runs_and_installs_do_not(tmp_path):  # type: ignore[no-untyped-def]
    import asyncio
    import time
    from pathlib import Path

    import httpx2

    from forge.engine.session_host import SessionHost
    from forge.llm.base import ToolCall
    from forge.protocol.events import EventBus
    from forge.safety.redact import Redactor
    from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
    from forge.tools.registry import ToolRegistry
    from forge.workspace.create import create_workspace
    from tests.helpers import mocked_router

    class FakeRun(Tool):
        name = "run_command"
        description = "sleeps"

        class Args(ToolArgs):
            command: str

        async def run(self, args: FakeRun.Args, context: ToolContext) -> ToolResult:
            await asyncio.sleep(0.3)
            return ToolResult(ok=True, content="ok")

    original = Path(__file__).resolve().parent / "fixtures" / "sample_repo"
    workspace = create_workspace(original, tmp_path / "ws", "backend")
    host = SessionHost(
        mocked_router(lambda request: httpx2.Response(500)),
        EventBus(redactor=Redactor()),
        workspace=workspace,
    )
    assert host.agent is not None
    host.agent.tools = ToolRegistry([FakeRun()])
    host.agent.gate.mode = "auto"

    async def elapsed(commands: list[str]) -> float:
        calls = [
            ToolCall(id=f"c{i}", name="run_command", raw_arguments="{}", arguments={"command": c})
            for i, c in enumerate(commands)
        ]
        results: dict = {}
        started = time.perf_counter()
        await host.agent._run_calls(calls, results)
        assert len(results) == len(commands)
        return time.perf_counter() - started

    await elapsed(["ls"])  # warm-up
    assert await elapsed(["ruff check .", "mypy", "pytest -q", "ls src"]) < 0.7  # four at once
    assert await elapsed(["pytest -q a", "pytest -q b"]) >= 0.55  # one test run at a time
    assert await elapsed(["npm install", "ruff check ."]) >= 0.55  # an install never overlaps
    assert (
        await elapsed(["ruff check .", "mypy", "ls", "cat x", "pytest"]) >= 0.55
    )  # more than four wait for the next batch


async def test_approval_cards_are_asked_one_at_a_time(tmp_path):  # type: ignore[no-untyped-def]
    import asyncio
    from pathlib import Path
    from types import SimpleNamespace

    import httpx2

    from forge.engine.session_host import SessionHost
    from forge.protocol.events import EventBus
    from forge.safety.redact import Redactor
    from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
    from forge.workspace.create import create_workspace
    from tests.helpers import mocked_router

    class Quick(Tool):
        name = "run_command"
        description = "x"

        class Args(ToolArgs):
            command: str

        async def run(self, args: Quick.Args, context: ToolContext) -> ToolResult:
            return ToolResult(ok=True, content="ok")

    open_now = 0
    peak = 0

    class FakeApprovals:
        async def request(self, payload: dict) -> SimpleNamespace:  # type: ignore[type-arg]
            nonlocal open_now, peak
            open_now += 1
            peak = max(peak, open_now)
            await asyncio.sleep(0.05)
            open_now -= 1
            return SimpleNamespace(approved=True, scope="once", instruction="")

    original = Path(__file__).resolve().parent / "fixtures" / "sample_repo"
    workspace = create_workspace(original, tmp_path / "ws", "backend")
    host = SessionHost(
        mocked_router(lambda request: httpx2.Response(500)),
        EventBus(redactor=Redactor()),
        workspace=workspace,
    )
    agent = host.agent
    assert agent is not None
    agent.approvals = FakeApprovals()  # type: ignore[assignment]
    decision = SimpleNamespace(command_prefix=None, always_ask=False, reason="", verdict="ask")
    tool = Quick()
    args = Quick.Args(command="ruff check .")
    waits: list[float] = []
    results = await asyncio.gather(
        *(agent._approved_run(tool, args, "s", "ruff check .", decision, waits) for _ in range(3))  # type: ignore[arg-type]
    )
    assert all(r.ok for r in results) and peak == 1

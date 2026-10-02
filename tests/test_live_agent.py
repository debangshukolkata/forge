"""M3 live acceptance: the real model drives the tools on the fixture. Run with: pytest -m live"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

import psutil
import pytest

from forge.config import load_config, load_secrets
from forge.engine.session_host import SessionHost
from forge.llm.router import LLMRouter
from forge.protocol.events import Event, EventBus, EventType
from forge.protocol.inputs import Approve, Interrupt, Reject, SendMessage, UserInput
from forge.safety.permissions import PermissionMode
from forge.workspace.create import create_workspace
from tests.conftest import REPO_ROOT

pytestmark = pytest.mark.live
ERRORS = "backend/claims_app/errors.py"
TURN_TIMEOUT_S = 300


@pytest.fixture
def make_host(
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FORGE_ENV_FILE", str(REPO_ROOT / ".env"))
    secrets = load_secrets(isolated_forge_home)
    if not secrets.get("AZURE_OPENAI_API_KEY"):
        pytest.skip("AZURE_OPENAI_* not configured in .env")
    config = load_config(isolated_forge_home)
    count = iter(range(100))

    def build(mode: PermissionMode = "default") -> SessionHost:
        workspace = create_workspace(original_repo, tmp_path / f"ws{next(count)}", "backend")
        return SessionHost(
            LLMRouter(config, secrets),
            EventBus(workspace.forge_dir / "events.jsonl"),
            workspace=workspace,
            permission_mode=mode,
        )

    return build


async def run_turn(
    host: SessionHost, text: str, on_event: Callable[[Event], UserInput | None] | None = None
) -> None:
    """Sends one message and waits for the turn to finish, answering events via on_event."""
    since = host.bus.last_seq
    runner = asyncio.create_task(host.run())
    subscription = host.bus.subscribe(since_seq=since)
    await host.submit(SendMessage(text=text))
    try:
        async with asyncio.timeout(TURN_TIMEOUT_S):
            async for event in subscription:
                if on_event is not None and (reply := on_event(event)) is not None:
                    await host.submit(reply)
                if event.type in (EventType.COST_UPDATED, EventType.ERROR):
                    break
                if (
                    event.type == EventType.STATUS_CHANGED
                    and event.payload["state"] == "idle"
                    and event.seq > since + 2
                ):
                    break
    finally:
        subscription.close()
        runner.cancel()


def events_of(host: SessionHost, kind: EventType) -> list[Event]:
    return [event for event in host.bus.events_since(0) if event.type == kind]


def tool_calls_paired(host: SessionHost) -> bool:
    calls = {c.id for m in host.history if m.role == "assistant" for c in m.tool_calls}
    results = {m.tool_call_id for m in host.history if m.role == "tool"}
    return calls == results


async def test_agent_edits_the_fixture(make_host) -> None:  # type: ignore[no-untyped-def]
    host = make_host()

    await run_turn(
        host,
        f"In {ERRORS}, add a ConflictError class (HTTP 409, status text 'Conflict') "
        "following the style of the existing error classes. Don't change anything else.",
    )
    await host.close()

    text = host.workspace.path_of(ERRORS).read_text(encoding="utf-8")
    assert "class ConflictError(ClaimsAppError):" in text and "409" in text
    started = [e.payload["name"] for e in events_of(host, EventType.TOOL_CALL_STARTED)]
    assert "read_file" in started and started.index("read_file") < next(
        i for i, name in enumerate(started) if name in ("edit_file", "multi_edit", "write_file")
    )
    assert events_of(host, EventType.FILE_CHANGED)
    assert tool_calls_paired(host)
    compiled = [
        e
        for e in events_of(host, EventType.TOOL_CALL_FINISHED)
        if e.payload["name"] in ("edit_file", "multi_edit")
    ]
    assert all("Syntax check FAILED" not in e.payload["preview"] for e in compiled)


async def test_denied_command_feeds_the_instruction_back(make_host) -> None:  # type: ignore[no-untyped-def]
    host = make_host("default")
    asked: list[Event] = []

    def deny(event: Event) -> UserInput | None:
        if event.type == EventType.APPROVAL_REQUESTED:
            asked.append(event)
            return Reject(
                request_id=event.payload["id"],
                instruction="Do not run anything. Reply that the version is unknown.",
            )
        return None

    await run_turn(
        host, "Use run_command to execute exactly `python --version` and tell me the result.", deny
    )
    await host.close()

    assert asked and "python --version" in asked[0].payload["summary"]
    finished = [
        e for e in events_of(host, EventType.TOOL_CALL_FINISHED) if e.payload["name"] == "run_command"
    ]
    assert finished and not finished[0].payload["ok"] and "declined" in finished[0].payload["preview"]
    assert "unknown" in events_of(host, EventType.MESSAGE_DONE)[-1].payload["text"].lower()


async def test_approved_command_runs(make_host) -> None:  # type: ignore[no-untyped-def]
    host = make_host("default")

    def approve(event: Event) -> UserInput | None:
        return Approve(request_id=event.payload["id"]) if event.type == EventType.APPROVAL_REQUESTED else None

    await run_turn(
        host, "Use run_command to execute exactly `python --version` and tell me the version.", approve
    )
    await host.close()

    finished = [
        e for e in events_of(host, EventType.TOOL_CALL_FINISHED) if e.payload["name"] == "run_command"
    ]
    assert finished and finished[0].payload["ok"] and "Python 3" in finished[0].payload["preview"]


async def test_interrupt_kills_the_command_and_keeps_history_valid(make_host) -> None:  # type: ignore[no-untyped-def]
    host = make_host("auto")
    marker = "forge_interrupt_probe"

    def interrupt(event: Event) -> UserInput | None:
        if event.type == EventType.TOOL_CALL_STARTED and event.payload["name"] in (
            "run_command",
            "python_run",
        ):
            return Interrupt()
        return None

    await run_turn(
        host,
        f'Run exactly this with run_command: python -c "import time; {marker}=1; time.sleep(90)"',
        interrupt,
    )
    await asyncio.sleep(1)
    leftovers = [p for p in psutil.process_iter(["cmdline"]) if marker in " ".join(p.info["cmdline"] or [])]
    assert leftovers == []
    assert tool_calls_paired(host)
    assert any(e.payload.get("kind") == "interrupted" for e in events_of(host, EventType.NOTICE))

    await run_turn(
        host, "In one short sentence: what happened to the command?"
    )  # history must still be valid
    await host.close()
    assert events_of(host, EventType.MESSAGE_DONE)


async def test_plan_mode_cannot_edit(make_host) -> None:  # type: ignore[no-untyped-def]
    host = make_host("plan")
    before = host.workspace.path_of(ERRORS).read_bytes()

    await run_turn(host, f"Add a ConflictError class to {ERRORS}.")
    await host.close()

    assert host.workspace.path_of(ERRORS).read_bytes() == before
    assert not events_of(host, EventType.FILE_CHANGED)

"""D-195: the full result of a tool call is saved (redacted) for the web UI; the event has only a preview."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx2
import pytest

from forge.agent.tool_output import CUT_NOTE, FOLDER, MAX_SAVED_CHARS, save_full_output
from forge.engine.session_host import SessionHost
from forge.protocol.events import EventBus, EventType
from forge.protocol.inputs import SendMessage
from forge.safety.redact import Redactor
from forge.workspace.create import create_workspace
from tests.helpers import function_call_output, mocked_router, reply, responses_body, text_output

SECRET = "s3cr3t-value-123456"  # check_secrets: fake


def saved_files(workspace_root: Path) -> list[Path]:
    folder = workspace_root / ".forge" / FOLDER
    return sorted(folder.glob("*.txt")) if folder.exists() else []


def test_save_redacts_and_caps(original_repo: Path, tmp_path: Path) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    redactor = Redactor()
    redactor.register(SECRET, "TEST_KEY")
    output_id = save_full_output(workspace, f"before {SECRET} after", redactor.redact)
    assert output_id is not None and len(output_id) == 32
    text = (workspace.forge_dir / FOLDER / f"{output_id}.txt").read_text(encoding="utf-8")
    assert SECRET not in text and "before" in text and "after" in text

    huge = save_full_output(workspace, "x" * (MAX_SAVED_CHARS + 500), redactor.redact)
    assert huge is not None
    saved = (workspace.forge_dir / FOLDER / f"{huge}.txt").read_text(encoding="utf-8")
    assert saved.endswith(CUT_NOTE) and len(saved) == MAX_SAVED_CHARS + len(CUT_NOTE)


async def run_one_turn(host: SessionHost) -> None:
    runner = asyncio.create_task(host.run())
    await host.submit(SendMessage(text="Read the big file."))
    for _ in range(200):
        await asyncio.sleep(0.05)
        if any(e.type == EventType.COST_UPDATED for e in host.bus.events_since(0)):
            break
    runner.cancel()


async def test_a_long_result_is_saved_and_the_event_points_to_it(original_repo: Path, tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return reply(request, responses_body([function_call_output("read_file", '{"path": "big.txt"}')]))
        return reply(request, responses_body([text_output("Read it.")]))

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    lines = [f"line {n} {SECRET if n == 7 else ''}" for n in range(1, 400)]
    (workspace.repo_dir / "big.txt").write_text("\n".join(lines), encoding="utf-8")
    redactor = Redactor()
    redactor.register(SECRET, "TEST_KEY")
    host = SessionHost(mocked_router(handler), EventBus(redactor=redactor), workspace=workspace)
    await run_one_turn(host)

    [finished] = [e.payload for e in host.bus.events_since(0) if e.type == EventType.TOOL_CALL_FINISHED]
    assert finished["output_id"] and finished["output_chars"] > len(finished["preview"])
    full = (workspace.forge_dir / FOLDER / f"{finished['output_id']}.txt").read_text(encoding="utf-8")
    assert len(full) == finished["output_chars"] and "line 399" in full  # the part the preview cuts off
    assert SECRET not in full and SECRET not in json.dumps(finished)


async def test_a_short_result_saves_nothing(original_repo: Path, tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return reply(
                request, responses_body([function_call_output("read_file", '{"path": "small.txt"}')])
            )
        return reply(request, responses_body([text_output("Read it.")]))

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    (workspace.repo_dir / "small.txt").write_text("one line", encoding="utf-8")
    host = SessionHost(mocked_router(handler), EventBus(redactor=Redactor()), workspace=workspace)
    await run_one_turn(host)
    [finished] = [e.payload for e in host.bus.events_since(0) if e.type == EventType.TOOL_CALL_FINISHED]
    assert "output_id" not in finished and saved_files(workspace.root) == []


async def test_a_subagents_long_results_are_not_saved(original_repo: Path, tmp_path: Path) -> None:
    from forge.subagents.subagent import run_debugger

    calls = {"n": 0}

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return reply(request, responses_body([function_call_output("read_file", '{"path": "big.txt"}')]))
        return reply(request, responses_body([text_output("Root cause: x.")]))

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    (workspace.repo_dir / "big.txt").write_text(
        "\n".join(f"line {n}" for n in range(1, 400)), encoding="utf-8"
    )
    host = SessionHost(mocked_router(handler), EventBus(redactor=Redactor()), workspace=workspace)
    assert host.agent is not None
    await run_debugger(host.router, host.agent.context, "the build fails")
    assert calls["n"] == 2 and saved_files(workspace.root) == []  # it read the file; nothing was kept


@pytest.mark.parametrize("bad", ["../x", "short", "G" * 32, "a" * 31, "a" * 33])
def test_only_ids_the_engine_made_are_accepted(bad: str) -> None:
    from forge.web.tool_output_routes import OUTPUT_ID

    assert OUTPUT_ID.fullmatch(bad) is None
    assert OUTPUT_ID.fullmatch("0123456789abcdef" * 2) is not None

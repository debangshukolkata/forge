"""M10 wiring: the new tools are in every session, the session hands them their settings, memory is pinned
and managed with slash commands, custom commands become messages, post-edit hooks run, and the terminal
status bar reflects the session."""

from __future__ import annotations

import json
from pathlib import Path

import httpx2
import pytest

from forge.engine.session_host import SessionHost
from forge.protocol.events import Event, EventBus, EventType
from forge.safety.redact import Redactor
from forge.ui.console import ConsoleState, status_bar, track_status
from forge.workspace.create import create_workspace
from tests.helpers import mocked_router, reply, responses_body, text_output


def unreachable(request: object) -> object:
    raise AssertionError("no LLM call expected")


def host_for(original_repo: Path, tmp_path: Path, handler=unreachable) -> SessionHost:  # type: ignore[no-untyped-def]
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    return SessionHost(mocked_router(handler), EventBus(redactor=Redactor()), workspace=workspace)


def notices(host: SessionHost) -> list[str]:
    return [str(e.payload.get("text", "")) for e in host.bus.events_since(0) if e.type == EventType.NOTICE]


def test_sessions_get_the_m10_tools_and_their_settings(original_repo: Path, tmp_path: Path) -> None:
    host = host_for(original_repo, tmp_path)
    assert host.agent is not None
    names = set(host.agent.tools.names())
    assert {"web_search", "web_fetch", "memory_read", "memory_write", "browser_open", "http_request"} <= names
    context = host.agent.context
    assert context.web_search_order == ("searxng", "duckduckgo", "serpapi", "azure", "tavily")
    assert context.hosted_search is not None and context.summarise is not None


async def test_remember_and_memory_commands_keep_the_pin_current(
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path
) -> None:
    host = host_for(original_repo, tmp_path)
    assert host.context_manager.pinned.get("memory_index") is None
    await host._commands.handle("/remember Always use type hints in new code")
    pinned = host.context_manager.pinned.get("memory_index")
    assert pinned is not None and "Always use type hints in new code" in pinned
    await host._commands.handle("/memory")
    name = next(t for t in notices(host) if "type hints" in t and t.strip().startswith("user")).split()[1]
    await host._commands.handle(f"/memory delete {name}")
    assert host.context_manager.pinned.get("memory_index") is None


async def test_a_custom_command_is_sent_as_a_message(
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path
) -> None:
    commands = isolated_forge_home / "commands"
    commands.mkdir()
    (commands / "explain.md").write_text("Explain $ARGUMENTS in two sentences.", encoding="utf-8")
    bodies: list[dict[str, object]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        return reply(request, responses_body([text_output("It is the error module.")]))

    host = host_for(original_repo, tmp_path, handler)
    await host._commands.handle("/explain claims_app/errors.py")
    users = [e.payload["text"] for e in host.bus.events_since(0) if e.type == EventType.USER_MESSAGE]
    assert users == ["Explain claims_app/errors.py in two sentences."]
    assert "Explain claims_app/errors.py in two sentences." in json.dumps(bodies[0])
    await host._commands.handle("/nosuch")
    assert any("Unknown command: /nosuch" in n and "/explain" in n for n in notices(host))


async def test_post_edit_hooks_run_and_report(original_repo: Path, tmp_path: Path) -> None:
    host = host_for(original_repo, tmp_path)
    assert host.agent is not None
    host.router.config.hooks.post_edit = ["Write-Output 'formatted {file}'"]
    from forge.tools.files import WriteFile

    args = WriteFile.Args(path="backend/claims_app/new_module.py", content="x = 1\n")
    result = await WriteFile().run(args, host.agent.context)
    hooked = await host.agent._post_edit_hooks(args, result)
    assert (
        "[post-edit hook: Write-Output 'formatted 'backend/claims_app/new_module.py'' -> ok]"
        in hooked.content
    )
    assert "formatted" in hooked.content.split("post-edit hook")[1]


def test_status_bar_follows_the_session(original_repo: Path, tmp_path: Path) -> None:
    """No fixed phase any more (D-128/D-131): the status bar shows the current task and cadence instead."""
    host = host_for(original_repo, tmp_path)
    state = ConsoleState()
    for kind, payload in [
        (EventType.STATUS_CHANGED, {"state": "working", "permission_mode": "default"}),
        (EventType.CONTEXT_UPDATED, {"percent": 42.4}),
        (EventType.TASK_LIST_UPDATED, {"current_task": "T2", "cadence": "free_hand", "tasks": []}),
    ]:
        track_status(Event(seq=1, type=kind, ts="", payload=payload), state)
    bar = status_bar(host, state)
    assert (
        "task T2" in bar
        and "cadence free hand" in bar
        and "working" in bar
        and "ctx 42%" in bar
        and "mode default" in bar
    )


async def test_handoff_asks_the_model_to_write_the_project_state_memory(
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path
) -> None:
    bodies: list[dict[str, object]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        return reply(request, responses_body([text_output("Saved.")]))

    host = host_for(original_repo, tmp_path, handler)
    await host._commands.handle("/handoff the cart is half done")
    sent = json.dumps(bodies[0])
    assert "project-state" in sent and "## Next" in sent and "the cart is half done" in sent


def test_a_saved_project_state_is_flagged_first_in_the_pinned_memory(isolated_forge_home: Path) -> None:
    from forge.memory.store import MemoryStore, combined_index

    store = MemoryStore(isolated_forge_home, "repo:demo-1")
    assert combined_index(isolated_forge_home, "repo:demo-1") is None
    store.save("project-state", "where the work stands", "project", "## Next\n- finish the cart")
    pinned = combined_index(isolated_forge_home, "repo:demo-1") or ""
    flag = "Work on this project was left unfinished or paused: read the memory 'project-state'"
    assert flag in pinned and pinned.index(flag) < pinned.index("About this project:")
    assert "project-state (project): where the work stands" in pinned


async def test_todo_write_updates_the_pinned_list_and_the_event_and_survives_a_reopen(
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path
) -> None:
    import pydantic

    from forge.tools.todo import TodoWrite

    host = host_for(original_repo, tmp_path)
    assert host.agent is not None
    items = [
        {"content": "read the routes", "status": "completed"},
        {"content": "add the endpoint", "status": "in_progress"},
        {"content": "run the tests", "status": "pending"},
    ]
    result = await TodoWrite().run(TodoWrite.Args(todos=items), host.agent.context)  # type: ignore[arg-type]
    assert result.ok and "[~] add the endpoint" in result.content
    pinned = host.context_manager.pinned.get("todos") or ""
    assert "[x] read the routes" in pinned and "[ ] run the tests" in pinned
    events = [e for e in host.bus.events_since(0) if e.type == EventType.TODO_UPDATED]
    assert len(events) == 1 and len(events[0].payload["items"]) == 3
    with pytest.raises(pydantic.ValidationError):  # two in progress at once
        TodoWrite.Args(
            todos=[{"content": "a", "status": "in_progress"}, {"content": "b", "status": "in_progress"}]
        )  # type: ignore[list-item]
    # A new session over the same event log gets the list back.
    reopened = SessionHost(
        host.router,
        host.bus,
        workspace=host.workspace,
        orchestrated=False,  # same log, fresh host
    )
    assert "[~] add the endpoint" in (reopened.context_manager.pinned.get("todos") or "")

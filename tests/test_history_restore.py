"""The model's history survives a reopen, per conversation (D-582). A real SessionHost with a mocked network."""

from __future__ import annotations

import asyncio
import contextlib
import json
from pathlib import Path

import httpx2

from forge.engine.history_store import load_history, save_history, valid_prefix
from forge.engine.session_host import SessionHost
from forge.llm.base import Message, ToolCall
from forge.protocol.events import EventBus, EventType
from forge.protocol.inputs import SendMessage, SlashCommand
from forge.safety.redact import Redactor, default_redactor
from forge.workspace.conversations import ConversationStore
from forge.workspace.create import create_workspace
from forge.workspace.workspace import Workspace
from tests.helpers import function_call_output, mocked_router, reply, responses_body, text_output


def _host(workspace: Workspace, handler) -> SessionHost:  # type: ignore[no-untyped-def]
    store = ConversationStore(workspace)
    bus = EventBus(store.events_path(store.active().id), redactor=Redactor())
    return SessionHost(mocked_router(handler), bus, workspace=workspace)


async def _turn(host: SessionHost, text: str) -> None:
    """Sends one message and waits until its turn has ended (answer, then idle)."""
    runner = asyncio.create_task(host.run())
    await host.submit(SendMessage(text=text))
    for _ in range(200):
        await asyncio.sleep(0.05)
        events = host.bus.events_since(0)
        asked = [e.seq for e in events if e.type == EventType.USER_MESSAGE and e.payload.get("text") == text]
        # the turn has ended when the status is idle again after the answer (the end-of-turn save has run)
        done = [e.seq for e in events if e.type == EventType.MESSAGE_DONE and asked and e.seq > asked[-1]]
        if done and any(
            e.type == EventType.STATUS_CHANGED and e.payload.get("state") == "idle" and e.seq > done[0]
            for e in events
        ):
            break
    runner.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await runner


def _answering(text: str, bodies: list[dict]):  # type: ignore[no-untyped-def,type-arg]
    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        return reply(request, responses_body([text_output(text)]))

    return handler


def _texts(body: dict) -> str:  # type: ignore[type-arg]
    return json.dumps(body["input"])


async def test_a_reopened_conversation_goes_on_with_what_the_model_said(
    original_repo: Path, tmp_path: Path
) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    first: list[dict] = []  # type: ignore[type-arg]
    host = _host(workspace, _answering("The answer is 42", first))
    await _turn(host, "What is the answer to everything?")
    await host.close()

    second: list[dict] = []  # type: ignore[type-arg]
    reopened = _host(workspace, _answering("Yes", second))
    await _turn(reopened, "And the question?")
    await reopened.close()

    sent = _texts(second[0])
    assert "What is the answer to everything?" in sent and "The answer is 42" in sent
    assert "And the question?" in sent
    assert ConversationStore(workspace).get("c1").title == "What is the answer to everything?"


async def test_a_turn_killed_after_a_finished_step_keeps_that_step(
    original_repo: Path, tmp_path: Path
) -> None:
    """The history is saved after every finished step, not only at the end of a turn."""
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    calls = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return reply(
                request,
                responses_body(
                    [function_call_output("list_dir", json.dumps({"path": "."}), "call_a")],
                ),
            )
        raise RuntimeError("the process is killed here")  # never answered: the turn does not finish

    host = _host(workspace, handler)
    host._run_turn_error_seen = True  # type: ignore[attr-defined]
    runner = asyncio.create_task(host.run())
    await host.submit(SendMessage(text="Look around"))
    store = ConversationStore(workspace)
    for _ in range(200):
        await asyncio.sleep(0.05)
        saved = store.history_path("c1")
        if calls >= 2 and saved.exists() and "call_a" in saved.read_text(encoding="utf-8"):
            break
    runner.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await runner

    loaded = load_history(store.history_path("c1"), default_redactor.redact_data)
    assert loaded is not None
    messages, _ = loaded
    assert any(
        m.role == "tool" and m.tool_call_id == "call_a" for m in messages
    )  # the finished step is there


def test_a_history_ending_in_a_call_without_a_result_is_cut_back() -> None:
    kept = [
        Message.user("hi"),
        Message(role="assistant", content="a"),
        Message.user("again"),
        Message(
            role="assistant",
            tool_calls=[ToolCall(id="c1", name="read_file", arguments={}, raw_arguments="{}")],
        ),
    ]
    assert [m.content for m in valid_prefix(kept)] == ["hi", "a", "again"]
    whole = [*kept, Message.tool_result("c1", "ok")]
    assert valid_prefix(whole) == whole


def test_the_saved_history_holds_no_secret_and_a_tampered_file_loads_without_it(
    original_repo: Path, tmp_path: Path
) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    secret = "sk-live-" + "4f9a2c7e" * 4  # check_secrets: fake
    path = ConversationStore(workspace).history_path("c1")
    messages = [
        Message.user(f"my key is {secret}"),
        Message(role="assistant", content="ok", provider_items=[{"type": "reasoning"}], images=["data:x"]),
    ]
    save_history(
        workspace, path, messages, {"compaction_summary": f"key {secret}"}, default_redactor.redact_data
    )

    assert secret not in path.read_text(encoding="utf-8")
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["messages"][1]["provider_items"] is None and document["messages"][1]["images"] == []

    document["messages"][0]["content"] = f"my key is {secret}"  # a file edited by hand brings it back...
    path.write_text(json.dumps(document), encoding="utf-8")
    loaded = load_history(path, default_redactor.redact_data)
    assert loaded is not None and secret not in json.dumps(
        [m.content for m in loaded[0]]
    )  # ...but not to the model


def test_an_unusable_history_file_is_ignored(original_repo: Path, tmp_path: Path) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    path = ConversationStore(workspace).history_path("c1")
    path.parent.mkdir(parents=True, exist_ok=True)
    for text in (
        "{not json",
        '{"version": 99, "messages": []}',
        '{"version": 1, "messages": [{"role": "bogus"}]}',
    ):
        path.write_text(text, encoding="utf-8")
        assert load_history(path, default_redactor.redact_data) is None


async def test_an_old_project_says_once_that_its_history_is_gone(original_repo: Path, tmp_path: Path) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    log = workspace.forge_dir / "transcripts" / "events.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        json.dumps(
            {
                "seq": 1,
                "type": "user_message",
                "ts": "2026-01-01T00:00:00.000+00:00",
                "payload": {"text": "old"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    def handler(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("no model call expected")

    for _ in range(2):  # the second open must not add the notice again
        host = _host(workspace, handler)
        runner = asyncio.create_task(host.run())
        await asyncio.sleep(0.3)
        runner.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await runner
        await host.close()
    notices = [
        e
        for e in host.bus.events_since(0)
        if e.type == EventType.NOTICE and e.payload.get("kind") == "history_not_restored"
    ]
    assert len(notices) == 1


async def test_a_new_conversation_starts_empty_but_knows_the_others(
    original_repo: Path, tmp_path: Path
) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    first: list[dict] = []  # type: ignore[type-arg]
    host = _host(workspace, _answering("alpha-reply", first))
    await _turn(host, "alpha question")
    await host.close()

    ConversationStore(workspace).create()
    second: list[dict] = []  # type: ignore[type-arg]
    fresh = _host(workspace, _answering("beta-reply", second))
    await _turn(fresh, "beta question")
    sent = _texts(second[0])
    assert "alpha-reply" not in sent and "alpha question" in sent  # only the title line, not the messages
    assert "conversation_recall" in sent
    assert not any("alpha-reply" in m.content for m in fresh.history)
    await fresh.close()


async def test_clear_empties_the_saved_history(original_repo: Path, tmp_path: Path) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    bodies: list[dict] = []  # type: ignore[type-arg]
    host = _host(workspace, _answering("kept?", bodies))
    await _turn(host, "remember this")
    runner = asyncio.create_task(host.run())
    await host.submit(SlashCommand(text="/clear"))
    await asyncio.sleep(0.4)
    runner.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await runner
    await host.close()

    loaded = load_history(ConversationStore(workspace).history_path("c1"), default_redactor.redact_data)
    assert loaded is not None and loaded[0] == []


async def test_conversation_recall_reads_another_conversation_only(
    original_repo: Path, tmp_path: Path
) -> None:
    from forge.toolkit.base import ToolContext
    from forge.tools.conversation_recall import ConversationRecall

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    secret = "sk-live-" + "7b3d9e1f" * 4  # check_secrets: fake
    store = ConversationStore(workspace)
    log = store.events_path("c1")
    log.parent.mkdir(parents=True, exist_ok=True)
    events = [
        {"seq": 1, "type": "user_message", "payload": {"text": f"set up the token {secret}"}},
        {"seq": 2, "type": "message_done", "payload": {"text": "Done, it is set up."}},
        {"seq": 3, "type": "status_changed", "payload": {"state": "idle"}},
    ]
    log.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    store.create("second")
    context = ToolContext(workspace=workspace)
    tool = ConversationRecall()

    summary = await tool.run(ConversationRecall.Args(id="c1"), context)
    assert summary.ok and "set up the token" in summary.content and "Done, it is set up." in summary.content
    assert secret not in summary.content
    requests = await tool.run(ConversationRecall.Args(id="c1", what="requests"), context)
    assert "Done, it is set up." not in requests.content
    assert not (await tool.run(ConversationRecall.Args(id="c2"), context)).ok  # the active one
    assert not (await tool.run(ConversationRecall.Args(id="../x"), context)).ok
    assert not (await tool.run(ConversationRecall.Args(id="c9"), context)).ok

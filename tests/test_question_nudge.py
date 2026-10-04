"""A question the model writes as plain text becomes a clickable card (D-212), and a resumed request opens
the files its user named. The model is simulated at the network layer."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx2

from forge.agent.loop import ASK_WITH_OPTIONS_NOTE
from forge.engine.session_host import SessionHost
from forge.parity.mentions import grant_from_message
from forge.protocol.events import EventBus, EventType
from forge.protocol.inputs import Answer, SendMessage
from forge.safety.redact import Redactor
from forge.workspace.create import create_workspace
from forge.workspace.read_grants import ReadGrants
from tests.helpers import function_call_output, mocked_router, reply, responses_body, text_output


def todo_args(*items: tuple[str, str]) -> str:
    return json.dumps({"todos": [{"content": text, "status": status} for text, status in items]})


ASK_ARGS = json.dumps(
    {
        "question": "Which database?",
        "options": [{"label": "SQLite", "description": "No setup"}, {"label": "Postgres"}],
        "recommended": "SQLite",
    }
)


async def _run(
    original_repo: Path, tmp_path: Path, outputs: list[list[dict[str, object]]]
) -> tuple[SessionHost, int]:
    calls: list[int] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        index = len(calls)
        calls.append(1)
        return reply(request, responses_body(outputs[min(index, len(outputs) - 1)]))

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    host = SessionHost(mocked_router(handler), EventBus(redactor=Redactor()), workspace=workspace)
    runner = asyncio.create_task(host.run())
    subscription = host.bus.subscribe(since_seq=host.bus.last_seq)

    async def answer_cards() -> None:
        async for event in subscription:
            if event.type == EventType.QUESTION_ASKED:
                await host.submit(Answer(question_id=event.payload["id"], choice="SQLite"))

    responder = asyncio.create_task(answer_cards())
    await host.submit(SendMessage(text="Build the app."))
    for _ in range(200):
        await asyncio.sleep(0.05)
        finished = any(e.type == EventType.COST_UPDATED for e in host.bus.events_since(0))
        last = host.history[-1]
        if finished and last.role == "assistant" and not last.tool_calls:
            break
    subscription.close()
    responder.cancel()
    runner.cancel()
    return host, len(calls)


async def test_a_question_written_as_text_is_asked_again_as_options(
    original_repo: Path, tmp_path: Path
) -> None:
    host, requests = await _run(
        original_repo,
        tmp_path,
        [
            [text_output("Option A: SQLite. Option B: Postgres. Which database should I use?")],
            [function_call_output("ask_user", ASK_ARGS)],
            [text_output("Going with SQLite.")],
        ],
    )
    assert requests == 3
    assert any(m.role == "system" and m.content == ASK_WITH_OPTIONS_NOTE for m in host.history)
    cards = [e for e in host.bus.events_since(0) if e.type == EventType.QUESTION_ASKED]
    assert len(cards) == 1 and [o["label"] for o in cards[0].payload["options"]] == ["SQLite", "Postgres"]
    tool_results = [m.content for m in host.history if m.role == "tool"]
    assert any("The user chose: SQLite" in text for text in tool_results)
    assert host.history[-1].content == "Going with SQLite."


async def test_an_ordinary_reply_is_not_nudged(original_repo: Path, tmp_path: Path) -> None:
    host, requests = await _run(original_repo, tmp_path, [[text_output("Done. The tests pass.")]])
    assert requests == 1
    assert not any(m.role == "system" and m.content == ASK_WITH_OPTIONS_NOTE for m in host.history)


async def test_the_nudge_happens_once_even_if_the_model_asks_in_text_again(
    original_repo: Path, tmp_path: Path
) -> None:
    _, requests = await _run(
        original_repo,
        tmp_path,
        [[text_output("Should I use SQLite?")], [text_output("Still unsure, ok to proceed?")]],
    )
    assert requests == 2  # one nudge, then the turn ends as before


def test_a_resumed_request_opens_the_files_it_named(
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path
) -> None:
    named = tmp_path / "notes" / "brief.md"
    named.parent.mkdir()
    named.write_text("brief", encoding="utf-8")
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    workspace.read_grants = ReadGrants.for_workspace(workspace.root, isolated_forge_home)
    saved = f"Please read {named} and build the app."
    assert len(grant_from_message(saved, workspace)) == 1
    assert workspace.resolve_readable(str(named)) is not None
    assert grant_from_message(saved, workspace) == []  # already open: nothing new
    other = named.parent / "other.md"
    other.write_text("x", encoding="utf-8")
    assert grant_from_message(f"the file {other} is nice", workspace) == []  # no reading word
    assert workspace.resolve_readable(str(other)) is None


async def test_a_turn_that_ends_with_open_todo_items_carries_on(original_repo: Path, tmp_path: Path) -> None:
    host, requests = await _run(
        original_repo,
        tmp_path,
        [
            [
                function_call_output(
                    "todo_write", todo_args(("Phase 1", "in_progress"), ("Phase 2", "pending"))
                )
            ],
            [text_output("Phase 1 is done.")],  # a status message that would have ended the turn
            [
                function_call_output(
                    "todo_write", todo_args(("Phase 1", "completed"), ("Phase 2", "completed"))
                )
            ],
            [text_output("Everything is done.")],
        ],
    )
    assert requests == 4
    notes = [
        m.content
        for m in host.history
        if m.role == "system" and "todo list still has open items" in m.content
    ]
    assert len(notes) == 1 and "Phase 1; Phase 2" in notes[0]
    assert host.history[-1].content == "Everything is done."


async def test_the_open_todo_nudge_is_limited_and_never_pushes_past_a_question(
    original_repo: Path, tmp_path: Path
) -> None:
    stubborn = [
        [function_call_output("todo_write", todo_args(("Phase 1", "pending")))],
        [text_output("Pausing here.")],
    ]
    _, requests = await _run(original_repo, tmp_path, stubborn)
    assert requests == 4  # the plan, then two nudges, then the turn ends: it does not loop forever
    host, requests = await _run(
        original_repo,
        tmp_path / "q",
        [
            [function_call_output("todo_write", todo_args(("Phase 1", "pending")))],
            [text_output("Shall I use SQLite or Postgres for Phase 1?")],
            [function_call_output("ask_user", ASK_ARGS)],
            [text_output("Using SQLite.")],
        ],
    )
    first_note = next(
        m.content
        for m in host.history
        if m.role == "system"
        and (m.content == ASK_WITH_OPTIONS_NOTE or "todo list still has open items" in m.content)
    )
    assert first_note == ASK_WITH_OPTIONS_NOTE  # a question to the user is asked as options, not pushed past

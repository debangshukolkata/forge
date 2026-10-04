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

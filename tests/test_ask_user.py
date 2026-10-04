"""ask_user in a chat session: the question appears as clickable options plus a box for the user's own answer,
instead of the model asking in plain text."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from forge.protocol.events import EventType
from forge.protocol.inputs import Answer, SendMessage
from forge.toolkit.base import ToolContext
from forge.tools.interaction import AskUser, OptionSpec
from tests.test_parity import host, workspace  # noqa: F401  (fixtures)

ARGS = AskUser.Args(
    question="Which database?",
    context="The brief does not say.",
    options=[OptionSpec(label="SQLite", description="No setup"), OptionSpec(label="Postgres")],
    recommended="SQLite",
)


async def test_the_question_carries_the_options_and_the_choice_comes_back(host: Any) -> None:  # noqa: F811
    subscription = host.bus.subscribe(since_seq=host.bus.last_seq)
    seen: dict[str, Any] = {}

    async def answer() -> None:
        async for event in subscription:
            if event.type == EventType.QUESTION_ASKED:
                seen.update(event.payload)
                subscription.close()
                await host.submit(
                    Answer(question_id=event.payload["id"], choice="SQLite", text="keep it simple")
                )
                return

    responder = asyncio.create_task(answer())
    result = await AskUser().run(ARGS, host.agent.context)
    await responder
    assert result.ok and result.content == "The user chose: SQLite. They added: keep it simple"
    assert [o["label"] for o in seen["options"]] == ["SQLite", "Postgres"] and seen["recommended"] == "SQLite"
    assert seen["question"] == "Which database?" and seen["context"] == "The brief does not say."


async def test_the_users_own_typed_answer_comes_back(host: Any) -> None:  # noqa: F811
    waiting = asyncio.create_task(AskUser().run(ARGS, host.agent.context))
    await asyncio.sleep(0)
    await host.submit(SendMessage(text="neither, use a JSON file"))
    result = await asyncio.wait_for(waiting, timeout=2)
    assert result.ok and result.content == "The user answered: neither, use a JSON file"


def test_the_tool_is_offered_in_chat_sessions(host: Any) -> None:  # noqa: F811
    assert "ask_user" in host.agent.tools.names()


async def test_without_a_question_channel_it_says_so(workspace: Any, tmp_path: Path) -> None:  # noqa: F811
    result = await AskUser().run(ARGS, ToolContext(workspace=workspace))
    assert not result.ok and "only available" in result.content

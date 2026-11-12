"""ask_user in a chat session: the question appears as clickable options plus a box for the user's own answer,
instead of the model asking in plain text."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from forge.protocol.events import EventBus, EventType
from forge.protocol.inputs import Answer, SendMessage
from forge.toolkit.base import ToolContext
from forge.tools.interaction import (
    AskUser,
    OptionSpec,
    RequestUserAction,
    asks_for_a_restart_or_copy,
    asks_for_a_secret_in_chat,
)
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


async def test_request_ids_do_not_repeat_from_one_session_to_the_next() -> None:
    """The counter restarts with every session; ids must not, or a new request looks answered (D-218)."""
    from forge.protocol.approvals import ApprovalBroker, QuestionBroker
    from forge.safety.redact import Redactor

    ids: list[str] = []
    for _ in range(2):  # two sessions
        bus = EventBus(redactor=Redactor())
        tasks = [
            asyncio.create_task(QuestionBroker(bus).ask(EventType.QUESTION_ASKED, {"question": "q"})),
            asyncio.create_task(ApprovalBroker(bus).request({"tool": "x"})),
        ]
        await asyncio.sleep(0.05)
        ids += [event.payload["id"] for event in bus.events_since(0)]
        for task in tasks:
            task.cancel()
    assert len(ids) == 4 and len(set(ids)) == 4
    assert all(i.startswith(("question-", "approval-")) for i in ids)


# --- D-569: a question that tells the user to put a secret into the chat is not asked


def test_only_a_request_to_put_a_secret_into_the_chat_is_caught() -> None:
    caught = [
        "Please paste your JWT in your next message so I can call the API.",
        "I need the ArgoCD token. Send it here in the chat.",
        "Reply with the API key here and I will continue.",
        "Could you give me the password for the staging database?",
        "Re-send the token, it was hidden.",
    ]
    for text in caught:
        assert asks_for_a_secret_in_chat([text]), text
    allowed = [
        "Which database should the app use?",
        "Should login use a JWT or a session cookie?",
        "Should the reply include the token count of the answer?",
        "How long should a password be at least?",
        "Add the line ARGOCD_TOKEN=<the token> to the .env file. Do not paste the token into the chat.",
        "The token has expired. Please replace the line in the .env file and answer when it is done.",
        "Where should the API key be stored: in the .env file or in the key vault?",
        "The API needs a token that only you can get. Add it to the .env file. Tell me here when it is done.",
    ]
    for text in allowed:
        assert not asks_for_a_secret_in_chat([text]), text


async def test_asking_for_a_token_in_the_chat_is_refused_with_the_route_that_works(
    workspace: Any,  # noqa: F811
) -> None:
    seen: list[str] = []

    async def asker(question: str, background: str, options: list, recommended: str | None) -> str:  # type: ignore[type-arg]
        seen.append(question)
        return "The user answered: ok"

    context = ToolContext(workspace=workspace)
    context.ask_user = asker
    args = AskUser.Args(
        question="I need the JWT for the development instance.",
        context="It was hidden last time.",
        options=[
            OptionSpec(label="Paste the token", description="Send it in your next message"),
            OptionSpec(label="Skip"),
        ],
    )
    refused = await AskUser().run(args, context)
    assert not refused.ok and not seen
    assert "request_app_secret" in refused.content and "token_env" in refused.content
    assert "[REDACTED]" in refused.content
    fine = await AskUser().run(ARGS, context)
    assert fine.ok and seen == ["Which database?"]


# --- D-570: the user is not sent to restart DebCraft or to put a variable "where DebCraft can see it"


def test_only_a_restart_of_debcraft_or_a_variable_made_visible_is_caught() -> None:
    caught = [  # the cards from the office laptop
        "Restart DebCraft so this session inherits DEVELOPMENT_INSTANCE_TOKEN",
        "Reload DebCraft so the updated .forge env vars are available to commands",
        "Close this DebCraft session and start a fresh one after saving INTERNAL_GATEWAY in the .env file.",
        "Make the development JWT visible to this DebCraft session",
        "Set the environment variable DEVELOPMENT_INSTANCE_TOKEN in the environment DebCraft commands inherit from.",
        "Set the token where DebCraft can read it",
    ]
    for text in caught:
        assert asks_for_a_restart_or_copy([text]), text
    allowed = [
        "Grant the role forge_reader on the schema claims to the user forge.",
        "Install Node.js 20 from the company portal.",
        "Should I restart the application server on port 8000 now?",
        "Set JAVA_HOME in the Windows settings and open a new PowerShell window.",
        "Which environment should the deployment go to?",
    ]
    for text in allowed:
        assert not asks_for_a_restart_or_copy([text]), text


async def test_a_user_action_to_restart_or_to_paste_a_token_is_refused_with_what_to_do_instead(
    host: Any,  # noqa: F811
) -> None:
    restart = await RequestUserAction().run(
        RequestUserAction.Args(
            title="Restart DebCraft so this session inherits DEVELOPMENT_INSTANCE_TOKEN",
            steps=["Close this DebCraft session/window and start a new one."],
        ),
        host.agent.context,
    )
    assert not restart.ok and "request_app_secret" in restart.content and "token_env" in restart.content
    assert "reads its .env file again on every call" in restart.content
    paste = await RequestUserAction().run(
        RequestUserAction.Args(
            title="Provide the token",
            steps=["Paste a one-time raw JWT here and I will use it for this request."],
        ),
        host.agent.context,
    )
    assert not paste.ok and "[REDACTED]" in paste.content

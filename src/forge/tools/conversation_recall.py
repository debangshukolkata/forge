"""Reading an earlier conversation of the same project (D-582): what was asked and what was answered, and (D-597) the
steps that say how something was run."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import Field

from forge.errors import ConversationError
from forge.safety.redact import default_redactor
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.workspace.conversations import ConversationStore

MAX_CHARS = 12_000
ANSWER_CHARS = 1_500
# The tool calls that say how something was run: `what="steps"` lists these, in order.
STEP_TOOLS = frozenset(
    {
        "start_background",
        "stop_background",
        "run_command",
        "python_run",
        "http_request",
        "use_scratch_database",
        "db_copy_table",
        "scratch_exec",
        "request_app_secret",
        "request_app_keys",
        "mark_server_run",
    }
)
MAX_STEPS = 80
STEP_CHARS = 240


class ConversationRecall(Tool):
    name = "conversation_recall"
    read_only = True
    description = (
        "Read an earlier conversation of this project by its id (the list is in the pinned context): what the "
        "user asked and what DebCraft answered. Use it when the user refers to earlier work. `what`: "
        "'requests' (only the user's messages), 'summary' (requests with the answers, shortened) or 'steps' "
        "(the commands and calls that started, copied, configured or called something, in order: how it was "
        "run). The conversation you are in cannot be read this way."
    )

    class Args(ToolArgs):
        id: str = Field(description="The conversation id, like c2")
        what: Literal["summary", "requests", "steps"] = "summary"

    async def run(self, args: ConversationRecall.Args, context: ToolContext) -> ToolResult:
        store = ConversationStore(context.workspace)
        try:
            conversation = store.get(args.id)
            log = store.events_path(args.id)
        except ConversationError as error:
            return ToolResult(ok=False, content=str(error))
        if args.id == store.active().id:
            return ToolResult(
                ok=False, content="That is the conversation you are in: its messages are above."
            )
        steps: list[str] = []
        lines = [
            f'Conversation {conversation.id} "{conversation.title}" (last used {conversation.updated[:10]})'
        ]
        try:
            with log.open(encoding="utf-8") as handle:
                for raw in handle:
                    try:
                        event = json.loads(raw)
                    except ValueError:
                        continue
                    payload = event.get("payload", {})
                    if args.what == "steps":
                        if event.get("type") == "tool_call_started" and payload.get("name") in STEP_TOOLS:
                            steps.append(
                                f"- {str(payload.get('summary') or payload.get('name'))[:STEP_CHARS]}"
                            )
                        continue
                    text = str(payload.get("text", "")).strip()
                    if event.get("type") == "user_message" and text:
                        lines.append(f"User: {text[:ANSWER_CHARS]}")
                    elif event.get("type") == "message_done" and text and args.what == "summary":
                        lines.append(f"DebCraft: {text[:ANSWER_CHARS]}")
        except OSError:
            return ToolResult(ok=True, content=lines[0] + "\nNothing was said in it yet.")
        if args.what == "steps":
            lines.append(
                "Steps, in order (the last ones are the newest):\n" + "\n".join(steps[-MAX_STEPS:])
                if steps
                else "No commands or calls of that kind were recorded."
            )
        text = default_redactor.redact("\n".join(lines))
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS] + "\n[cut: the conversation is longer]"
        return ToolResult(ok=True, content=text)

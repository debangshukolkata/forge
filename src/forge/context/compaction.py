"""Compaction building blocks (spec §10.4): turn splitting, pair validation, micro-compaction stubs,
summary prompts and emergency trimming. All pure functions over message lists; no LLM calls here."""

from __future__ import annotations

from importlib import resources

from forge.llm.base import Message
from forge.llm.tokens import count_text_tokens

REQUIRED_SECTIONS = [
    "## User instructions and preferences",
    "## Goal, phase, task and definition of done",
    "## Decisions and rationale",
    "## Files touched",
    "## Codebase findings",
    "## Errors and fixes",
    "## Current state and exact next step",
    "## Assumptions to verify",
    "## Open questions",
]
STUB_PREFIX = "[Output of "
TRANSCRIPT_TOOL_RESULT_CHARS = 6000
SHORTENED_MARKER = "\n[… output shortened for this summary only]"
TRANSCRIPT_TEXT_CHARS = 4000


def turn_starts(history: list[Message]) -> list[int]:
    """Indexes of user messages (a turn starts where the user speaks); index 0 is the system prompt."""
    return [index for index, message in enumerate(history) if message.role == "user"]


def step_starts(history: list[Message]) -> list[int]:
    """Indexes where a step starts: a user message or an assistant message (with its tool results).
    Cutting only here never separates a tool call from its results. One agent task is typically a
    single user turn with many steps, so compaction must be able to cut inside a turn (D-054)."""
    return [i for i, message in enumerate(history) if i > 0 and message.role in ("user", "assistant")]


def latest_user_index(history: list[Message]) -> int | None:
    return max((i for i, m in enumerate(history) if m.role == "user"), default=None)


def keep_from(history: list[Message], cut: int) -> list[Message]:
    """history[cut:], plus the latest user request when the cut falls after it: the task statement
    is always kept verbatim."""
    user = latest_user_index(history)
    kept = history[cut:]
    return [history[user], *kept] if user is not None and 0 < user < cut else kept


def pairs_are_valid(history: list[Message]) -> bool:
    """Every assistant tool call has exactly one result after it, and no result is orphaned."""
    open_calls: set[str] = set()
    for message in history:
        if message.role == "assistant":
            if open_calls:
                return False  # a new model turn began before all results arrived
            open_calls = {call.id for call in message.tool_calls}
        elif message.role == "tool":
            if message.tool_call_id not in open_calls:
                return False
            open_calls.discard(message.tool_call_id)
        elif open_calls:
            return False  # user/system message in the middle of a call/result group
    return not open_calls


def call_descriptions(history: list[Message]) -> dict[str, str]:
    """tool_call_id -> 'name(args…)' for stubs and transcripts."""
    descriptions = {}
    for message in history:
        for call in message.tool_calls:
            descriptions[call.id] = f"{call.name}({call.raw_arguments[:160]})"
    return descriptions


def micro_compact(history: list[Message], keep_recent: int, before: int | None = None) -> int:
    """Replaces tool results older than the last keep_recent (only those before index `before`, if
    given) with short stubs, and drops encrypted reasoning from old assistant messages. Pairs stay
    valid. Returns how many results were stubbed."""
    descriptions = call_descriptions(history)
    limit = len(history) if before is None else before
    tool_indexes = [i for i, m in enumerate(history) if m.role == "tool" and i < limit]
    stubbed = 0
    for index in tool_indexes[:-keep_recent] if len(tool_indexes) > keep_recent else []:
        message = history[index]
        if message.content.startswith(STUB_PREFIX):
            continue
        description = descriptions.get(message.tool_call_id or "", "a tool call")
        history[index] = message.model_copy(
            update={
                "content": (
                    f"{STUB_PREFIX}{description} removed to save context "
                    f"({count_text_tokens(message.content)} tokens). Call the tool again if you need it.]"
                )
            }
        )
        stubbed += 1
    last_assistant = max((i for i, m in enumerate(history) if m.role == "assistant"), default=-1)
    for index, message in enumerate(history):
        if message.role == "assistant" and message.provider_items and index != last_assistant:
            history[index] = message.model_copy(update={"provider_items": None, "provider_items_model": None})
    return stubbed


def split_for_summary(history: list[Message], keep_recent_steps: int) -> tuple[list[Message], list[Message]]:
    """(older, recent) with the system prompt excluded, cut at a step boundary. older is empty when there
    aren't enough steps to compact. The latest user request stays in recent even if it is older."""
    starts = step_starts(history)
    if len(starts) <= keep_recent_steps:
        return [], history[1:]
    cut = starts[-keep_recent_steps]
    return history[1:cut], keep_from(history, cut)


def render_transcript(messages: list[Message]) -> str:
    descriptions = call_descriptions(messages)
    lines = []
    for message in messages:
        if message.role == "user":
            lines.append(f"USER: {message.content[:TRANSCRIPT_TEXT_CHARS]}")
        elif message.role == "assistant":
            calls = ", ".join(f"{c.name}({c.raw_arguments[:200]})" for c in message.tool_calls)
            text = message.content[:TRANSCRIPT_TEXT_CHARS]
            lines.append(f"FORGE: {text}" + (f"\n  [called: {calls}]" if calls else ""))
        elif message.role == "tool":
            name = descriptions.get(message.tool_call_id or "", "tool").split("(")[0]
            content = message.content
            if len(content) > TRANSCRIPT_TOOL_RESULT_CHARS:
                # Say so explicitly: otherwise the summariser may report the file itself as truncated.
                content = content[:TRANSCRIPT_TOOL_RESULT_CHARS] + SHORTENED_MARKER
            lines.append(f"RESULT of {name}: {content}")
        else:
            lines.append(f"SYSTEM NOTE: {message.content[:TRANSCRIPT_TEXT_CHARS]}")
    return "\n\n".join(lines)


def chunk_transcript(messages: list[Message], max_tokens: int) -> list[str]:
    """Transcript pieces that each fit max_tokens (used when the older history is itself huge)."""
    chunks: list[str] = []
    current: list[Message] = []
    for message in messages:
        if current and count_text_tokens(render_transcript([*current, message])) > max_tokens:
            chunks.append(render_transcript(current))
            current = []
        current.append(message)
    if current:
        chunks.append(render_transcript(current))
    return chunks


def summary_prompt(transcript: str, previous_summary: str | None, focus: str | None) -> str:
    template = resources.files("forge").joinpath("context/prompts/compact.md").read_text(encoding="utf-8")
    return template.format(
        focus=f"The user asked to focus the summary on: {focus}\n" if focus else "",
        previous=(
            f"Summary of the part before this one (merge it into your summary):\n{previous_summary}\n"
            if previous_summary
            else ""
        ),
        transcript=transcript,
    )


FALLBACK_NOTE = (
    "(Written by DebCraft's code, not by the model, because the model's summary was incomplete twice. It holds facts "
    "only: treat all of it as unverified and check before relying on it. The full record is in the transcript.)"
)
NOT_CAPTURED = "Not captured (no model summary). Re-check by reading the files or running the tests again."
FALLBACK_USER_MESSAGES = 12
FALLBACK_MESSAGE_CHARS = 600
FALLBACK_STATE_CHARS = 1500
FALLBACK_MAX_CHARS = 14_000
FALLBACK_EARLIER_CHARS = 12_000


def fallback_summary(
    older: list[Message],
    previous_summary: str | None,
    files: list[str],
    phase_and_tasks: str | None,
    todos: str | None,
) -> str:
    """A summary made without the model, for when it fails twice (D-467): what the user asked, which files
    changed, the plan and todo list, the last thing said. Always has every required heading, so a later
    compaction can merge it like any other summary, and an earlier summary is kept whole."""

    def cut(text: str, limit: int) -> str:
        text = text.strip()
        return text if len(text) <= limit else text[:limit] + " [cut]"

    asked = [m.content for m in older if m.role == "user" and m.content.strip()][-FALLBACK_USER_MESSAGES:]
    last_said = next((m.content for m in reversed(older) if m.role == "assistant" and m.content.strip()), "")
    state = [cut(last_said, FALLBACK_STATE_CHARS)] if last_said else []
    if todos:
        state.append("Todo list:\n" + todos)
    asked_lines = "\n".join(f"- {cut(text, FALLBACK_MESSAGE_CHARS)}" for text in asked)
    file_lines = "\n".join(f"- {path}" for path in files)
    sections = {
        "## User instructions and preferences": asked_lines or "None.",
        "## Goal, phase, task and definition of done": phase_and_tasks or "See the pinned phase and tasks.",
        "## Decisions and rationale": NOT_CAPTURED,
        "## Files touched": file_lines or "None.",
        "## Codebase findings": NOT_CAPTURED,
        "## Errors and fixes": NOT_CAPTURED,
        "## Current state and exact next step": "\n\n".join(state)
        or "Not captured. Read the todo list and the latest files, then continue.",
        "## Assumptions to verify": "Everything in this summary: it was not written by the model.",
        "## Open questions": "None captured.",
    }
    body = "\n\n".join(f"{heading}\n{text}" for heading, text in sections.items())
    fresh = cut(f"{FALLBACK_NOTE}\n\n{body}", FALLBACK_MAX_CHARS)
    kept = (previous_summary or "")[
        :FALLBACK_EARLIER_CHARS
    ]  # a second fallback in a row must not grow without limit
    earlier = f"\n\n## Earlier summary (kept as it was)\n{kept}" if kept else ""
    return fresh + earlier


def summary_is_valid(summary: str) -> bool:
    return all(section in summary for section in REQUIRED_SECTIONS)


def emergency_trim(history: list[Message], keep_steps: int = 2) -> list[Message]:
    """System prompt + latest user request + the last keep_steps steps, older tool outputs stubbed."""
    starts = step_starts(history)
    cut = starts[-keep_steps] if len(starts) >= keep_steps else (starts[0] if starts else 1)
    trimmed = [history[0], *keep_from(history, cut)]
    micro_compact(trimmed, keep_recent=2)
    return trimmed

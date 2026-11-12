"""What may be saved as a topic about a repository (KU6, D-574).

A topic is read by every later project on the repository, so it must be true of the repository for any task. On the
office laptop five of six topics were about the task ("Minimal local runner for third party integration endpoint")
or about DebCraft itself. The cheap checks here run first; the reviewer model's judgement is the second step
(`tools/knowledge_tools.py`). Pure functions, no model call in this module."""

from __future__ import annotations

import json
import re

MAX_TITLE_CHARS = 80
FIRST_PERSON = re.compile(
    r"\b(I|we)\s+(did|fixed|added|changed|made|wrote|created|ran|tried|found|had to)\b", re.I
)
# DebCraft's own tools, variables and files: they belong in its instructions, not in knowledge of a repository.
OWN_NAMES = re.compile(
    r"\b(DebCraft|Forge|knowledge_write|knowledge_search|code_map|http_request|request_user_action|"
    r"request_app_secret|memory_write|tool_search|app\.env|DEVELOPMENT_INSTANCE_TOKEN)\b"
)

REVIEWER = (
    "You decide where a note belongs. A coding agent worked on a task in a software repository and wants to save "
    "the note below as a TOPIC ABOUT THE REPOSITORY, which every later project on this repository will read at "
    "its start, whatever its task.\n"
    "- `repository` when the note is true of the repository for any task: how it is structured, where things are, "
    "how a request or a run flows, what a setting or table means, how to run or test it.\n"
    "- `task` when it describes this one task: what was found while solving it, a workaround, a fix, a one-off "
    "script, the state of the user's environment, or what the agent did.\n"
    "When unsure, answer `repository`.\n"
    'Answer with JSON only: {"verdict": "repository" | "task", "reason": "one sentence"}'
)


def rule_problem(title: str, summary: str) -> str:
    """Empty when the title and summary look like knowledge of a repository; else what to change."""
    if len(title.strip()) > MAX_TITLE_CHARS:
        return (
            f"The title is {len(title.strip())} characters. Name the subject in a few words, like "
            "'How a request is authenticated', not a sentence about what you did."
        )
    if FIRST_PERSON.search(title) or FIRST_PERSON.search(summary):
        return (
            "The title or summary says what you did ('I fixed ...'). A topic describes the repository as it is, "
            "for any task; put what you did into your answer to the user, or into memory_write."
        )
    own = OWN_NAMES.search(title) or OWN_NAMES.search(summary)
    if own:
        return (
            f"The title or summary names {own.group(0)!r}, which is part of DebCraft, not of the repository. "
            "Write about the repository's own code and settings; how DebCraft is used does not belong here."
        )
    return ""


def verdict_of(text: str) -> tuple[str, str] | None:
    """('repository' or 'task', reason) from the reviewer's answer; None when it cannot be read."""
    found = re.search(r"\{.*\}", text, re.DOTALL)
    if not found:
        return None
    try:
        data = json.loads(found.group(0))
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get("verdict") not in ("repository", "task"):
        return None
    return str(data["verdict"]), str(data.get("reason", ""))

"""A second model reads the changes for investigation leftovers before the turn ends (WF2, D-622).

A change the model marks as temporary is kept out of the delivery (workspace/temporary_edits.py). The ones it
does not mark are the problem: in six live runs on the test bed it edited the application to tolerate a failing
dependency and never said so. The reviewer role's model gets the user's last messages and the diff of what
would be delivered, and names what looks like it was only there to get the application running or to watch it.
The working model then justifies each one, takes it out, or records it as temporary. Any failure of the review
means "nothing found": it must never hold a turn up.

Limits: only files changed through the write tools are read (a change made by a shell command is not in the
workspace's change log), and something the review named once is not named again.
"""

from __future__ import annotations

import asyncio
import difflib
import hashlib
import json
import re

from forge.llm.base import ChatRequest, Message
from forge.safety.redact import default_redactor
from forge.toolkit.base import ToolContext
from forge.workspace.output import FileChange, file_texts
from forge.workspace.workspace import Workspace

MAX_DIFF_CHARS = 60_000
MAX_LEFTOVERS = 8
REVIEWER = (
    "You check code changes before they are handed to the user. DebCraft is a coding agent that fixed or extended "
    "something in a copy of the user's repository. While investigating, such an agent often changes code only to "
    "get the application running or to see what happens, and forgets to take it out. Find those leftovers in the "
    "diff.\n\n"
    "A leftover is: a call, a check or a block that was commented out or deleted although the requirement does not "
    "ask for it; a function made to return a fixed value or to return early; an exception swallowed so that a "
    "failing dependency is ignored; a setting, an address or a credential name hard-coded or pointed at another "
    "environment; print or log lines that only trace the investigation; a skipped or weakened test.\n"
    "Not a leftover: anything the requirement asks for; logging that is part of the feature; error handling the fix "
    "needs and that still reports the error.\n"
    "When unsure, do not list it.\n\n"
    'Answer with JSON only: {"leftovers": [{"path": "...", "lines": "the changed lines, at most 3", '
    '"why": "one sentence"}]} with an empty list when there is none.'
)
FOUND_NOTE = (
    "Before you finish: a second model read your changes and found what may be leftovers of the investigation:\n"
    "{found}\n"
    "For each one: if it is part of the solution, say so in one line in your report. If it was only there to "
    "investigate, take it out now, or, when your check cannot run without it, record it with temporary_edits "
    "(action mark): it then stays in the copy, is taken out of the delivered files and is reported."
)


def delivery_diff(workspace: Workspace) -> str:
    """The unified diff of every file changed through the write tools, as it would be delivered (so without the
    changes already marked as temporary), secrets left out, the largest files cut when it is too long."""
    paths = sorted({change.path for change in workspace.changes()})
    parts: list[str] = []
    for path in paths:
        if workspace.is_secret(path):
            continue
        exists = (workspace.repo_dir / path).is_file()
        known = path in workspace.manifest.files
        if not exists and not known:
            continue
        status = "deleted" if not exists else ("modified" if known else "added")
        texts = file_texts(workspace, FileChange(path=path, status=status))  # type: ignore[arg-type]
        if texts is None or texts[0] == texts[1]:
            continue
        diff = "".join(
            difflib.unified_diff(
                texts[0].splitlines(keepends=True),
                texts[1].splitlines(keepends=True),
                f"a/{path}",
                f"b/{path}",
            )
        )
        parts.append(diff if diff.endswith("\n") else diff + "\n")
    room = MAX_DIFF_CHARS
    cut = 0
    order = sorted(range(len(parts)), key=lambda index: len(parts[index]))  # small files first, whole
    for position, index in enumerate(order):
        share = room // (len(order) - position)  # what is left, shared among the files still to come
        if len(parts[index]) > share:
            parts[index] = parts[index][:share] + "\n[this file's diff is cut here]\n"
            cut += 1
        room -= len(parts[index])
    text = "".join(parts)
    return text + (f"\n[{cut} large file(s) are shown in part]\n" if cut else "")


def _leftovers(text: str) -> list[dict[str, str]] | None:
    found = re.search(r"\{.*\}", text, re.DOTALL)
    if not found:
        return None
    try:
        data = json.loads(found.group(0))
    except ValueError:
        return None
    items = data.get("leftovers") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return None
    return [
        {key: str(item.get(key, "")).strip() for key in ("path", "lines", "why")}
        for item in items
        if isinstance(item, dict) and str(item.get("path", "")).strip()
    ][:MAX_LEFTOVERS]


async def review_leftovers(context: ToolContext) -> str | None:
    """None: nothing to say. Otherwise the message for the working model."""
    workspace = context.workspace
    if context.router is None or workspace is None or workspace.mode_b:
        return None
    try:
        diff = default_redactor.redact(await asyncio.to_thread(delivery_diff, workspace))
    except Exception:
        return None
    digest = hashlib.sha256(diff.encode("utf-8")).hexdigest()
    if not diff.strip() or digest == context.leftover_diff_hash:
        return None
    context.leftover_diff_hash = digest
    said = context.recent_user_messages() if context.recent_user_messages is not None else []
    question = "\n\n".join(
        [
            "What the user asked for (their last messages, oldest first):\n"
            + ("\n".join(f"- {text}" for text in said) or "- (not available)"),
            "The changes:\n" + diff,
        ]
    )
    await context.emit(
        "notice",
        {
            "kind": "leftover_review",
            "text": "A second model is reading the changes for investigation leftovers.",
        },
    )
    request = ChatRequest(
        messages=[Message(role="system", content=REVIEWER), Message(role="user", content=question)]
    )
    try:
        response = await context.ask_model("reviewer", request, "reading the changes for leftovers")
        found = _leftovers(str(response.text))
    except Exception:
        found = None
    if not found:
        return None
    fresh = [item for item in found if f"{item['path']}|{item['lines']}" not in context.leftovers_told]
    if not fresh:
        return None
    context.leftovers_told.update(f"{item['path']}|{item['lines']}" for item in fresh)
    listing = "\n".join(f"- {item['path']}: {item['lines'][:300]} ({item['why'][:300]})" for item in fresh)
    return FOUND_NOTE.format(found=listing)

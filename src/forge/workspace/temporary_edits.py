"""Changes made only to investigate: recorded here, kept in the copy, taken out of what is delivered (WF2, D-622).

To get the code under test running, a developer comments out a dependency that is not the cause, or adds log lines,
and takes both out again before committing. DebCraft's model does the first half by itself (it edits the
application to get past a failing dependency) and nothing did the second half: such an edit went into `output/`
like any other. A change marked as temporary is written down here with the exact text it replaced, so that the
delivery can be built without it while the copy keeps it for as long as the model still needs it.

Stored in `<project>/.forge/temporary_edits.json`. A hunk is one changed block: `new` is what stands in the file
now, `old` what stood there before, `before` and `after` up to three unchanged lines on each side. Taking a
change out is an exact replacement of `new` by `old` where `new` is found exactly once together with its
surrounding lines. The real fix is often a line or two away from the bypass, so when the surrounding lines have
changed since, fewer of them are required (down to none, if the changed lines alone are unique). A block whose
own lines were edited again is left alone and reported, never guessed at.
"""

from __future__ import annotations

import difflib
import json
import time
from typing import Any, Literal

from forge.workspace.workspace import Workspace

EDITS_FILE = "temporary_edits.json"
VERSION = 1
CONTEXT_LINES = 3
Kind = Literal["bypass", "logging"]
Entry = dict[str, Any]


# How many surrounding lines (before, after) must still match, tried in this order.
CONTEXT_TRIES = ((3, 3), (2, 2), (1, 1), (1, 0), (0, 1), (0, 0))


def hunks_between(before: str, after: str) -> list[dict[str, str]]:
    """The changed blocks between two texts: {"old", "new", "before", "after"}, the last two being the unchanged
    lines around the block as they stand in `after`."""
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    matcher = difflib.SequenceMatcher(None, before_lines, after_lines, autojunk=False)
    return [
        {
            "old": "".join(before_lines[i1:i2]),
            "new": "".join(after_lines[j1:j2]),
            "before": "".join(after_lines[max(0, j1 - CONTEXT_LINES) : j1]),
            "after": "".join(after_lines[j2 : j2 + CONTEXT_LINES]),
        }
        for tag, i1, i2, j1, j2 in matcher.get_opcodes()
        if tag != "equal"
    ]


def take_out(text: str, hunk: dict[str, str]) -> str | None:
    """`text` with one block set back, or None when the block cannot be found exactly once."""
    lines_before = hunk.get("before", "").splitlines(keepends=True)
    lines_after = hunk.get("after", "").splitlines(keepends=True)
    for keep_before, keep_after in CONTEXT_TRIES:
        head = "".join(lines_before[len(lines_before) - keep_before :]) if keep_before else ""
        tail = "".join(lines_after[:keep_after])
        wanted = head + hunk["new"] + tail
        if wanted and text.count(wanted) == 1:
            return text.replace(wanted, head + hunk["old"] + tail)
    return None


def normal_path(path: str) -> str:
    """The form the delivery uses for a file: forward slashes, no leading `./`."""
    return path.replace("\\", "/").removeprefix("./")


def describe(entry: Entry) -> str:
    return f"#{entry['id']} {entry['kind']} {entry['path']}: {entry['reason']}"


class TemporaryEdits:
    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.path = workspace.forge_dir / EDITS_FILE

    def load(self) -> dict[str, Any]:
        empty: dict[str, Any] = {"version": VERSION, "next_id": 1, "entries": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return empty
        if not isinstance(data, dict) or data.get("version") != VERSION:
            return empty
        if not isinstance(data.get("entries"), list) or not isinstance(data.get("next_id"), int):
            return empty
        return data

    def _save(self, data: dict[str, Any]) -> None:
        target = self.workspace.jail.check(self.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        scratch = target.with_name(target.name + ".tmp")
        scratch.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        scratch.replace(target)

    def add(
        self, path: str, kind: Kind, reason: str, op: Literal["edit", "create"], hunks: list[dict[str, str]]
    ) -> int:
        data = self.load()
        number = int(data["next_id"])
        data["entries"].append(
            {
                "id": number,
                "path": normal_path(path),
                "kind": kind,
                "reason": reason.strip(),
                "op": op,
                "hunks": hunks,
                "state": "active",
                "at": time.strftime("%Y-%m-%d"),
            }
        )
        data["next_id"] = number + 1
        self._save(data)
        return number

    def entries(self) -> list[Entry]:
        return list(self.load()["entries"])

    def active(self, path: str | None = None) -> list[Entry]:
        wanted = normal_path(path) if path is not None else None
        return [
            entry
            for entry in self.entries()
            if entry.get("state") == "active" and (wanted is None or entry.get("path") == wanted)
        ]

    def mark_removed(self, ids: list[int]) -> None:
        data = self.load()
        for entry in data["entries"]:
            if entry.get("id") in ids:
                entry["state"] = "removed"
        self._save(data)

    def without(
        self, path: str, text: str, ids: list[int] | None = None
    ) -> tuple[str, list[Entry], list[Entry]]:
        """`text` with the active changes of `path` taken out, newest first: (the text, the entries taken out, the
        entries that could not be). The hunks of one entry are taken out together or not at all. `ids` limits it
        to those entries. An entry that created the file is not handled here: the file itself is the change."""
        taken: list[Entry] = []
        left: list[Entry] = []
        for entry in reversed(self.active(path)):
            if entry.get("op") != "edit" or (ids is not None and entry["id"] not in ids):
                continue
            candidate: str | None = text
            for hunk in entry.get("hunks") or []:
                candidate = take_out(candidate, hunk) if candidate is not None else None
            if candidate is None:
                left.append(entry)
            else:
                text = candidate
                taken.append(entry)
        return text, taken, left

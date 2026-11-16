"""`temporary_edits`: the changes made only to investigate (WF2, D-622): list them, take them out, record one.

The edit tools record a change when the model marks it (`temporary`). This tool is the other half: the model takes
a change out of the copy when it no longer needs it, and it can record a change it made without marking it (the
review before the turn ends points at those)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools.files import PATH_HELP, save_marked, temporary_problem
from forge.workspace.temporary_edits import Entry, TemporaryEdits, describe, hunks_between, normal_path

TEMPORARY_NOTE = (
    "Temporary changes are still in the copy:\n{listing}\n"
    "For each: if you no longer need it, take it out (temporary_edits, action remove) and run your check again. If "
    "the check cannot run without it, leave it and write in your report: 'Proved with <what> bypassed; <what> was "
    "not exercised.' They are taken out of the delivered files either way."
)


def temporary_finish_note(context: ToolContext) -> str:
    """What to tell the model before the turn ends while temporary changes are in the copy; "" when there are
    none or when exactly these were named already (once per set, not once per turn)."""
    workspace = context.workspace
    if workspace is None or workspace.mode_b:
        return ""
    active = TemporaryEdits(workspace).active()
    numbers = frozenset(int(entry["id"]) for entry in active)
    if numbers == context.temporary_reported:
        return ""
    context.temporary_reported = numbers
    if not active:
        return ""
    return TEMPORARY_NOTE.format(listing="\n".join(describe(entry) for entry in active))


class TemporaryEditsTool(Tool):
    name = "temporary_edits"
    description = (
        "Lists, removes or records the temporary changes of this project (a bypassed dependency, added logging). "
        "`list`: what is recorded. `remove`: takes the changes with these `ids` (or all) out of the copy again. "
        "`mark`: records a change you already made without `temporary`: give `path`, `text` (the lines as they are "
        "in the file now), `original` (what stood there before; empty when the lines were only added), `kind` and "
        "`reason`."
    )

    class Args(ToolArgs):
        action: Literal["list", "remove", "mark"] = "list"
        ids: list[int] = Field(default_factory=list, description="For remove: the numbers; empty means all.")
        path: str = Field(default="", description="For mark: " + PATH_HELP)
        text: str = Field(default="", description="For mark: the lines as they are in the file now.")
        original: str = Field(
            default="", description="For mark: what stood there before; empty if only added."
        )
        kind: Literal["bypass", "logging"] = "bypass"
        reason: str = ""

    def summary(self, args: TemporaryEditsTool.Args) -> str:
        return f"temporary changes: {args.action}"

    async def run(self, args: TemporaryEditsTool.Args, context: ToolContext) -> ToolResult:
        edits = TemporaryEdits(context.workspace)
        if args.action == "list":
            entries = edits.entries()
            if not entries:
                return ToolResult(ok=True, content="No temporary changes are recorded.")
            return ToolResult(
                ok=True, content="\n".join(f"{describe(entry)} ({entry['state']})" for entry in entries)
            )
        if args.action == "mark":
            return self._mark(args, context, edits)
        return await self._remove(args, context, edits)

    @staticmethod
    def _mark(args: TemporaryEditsTool.Args, context: ToolContext, edits: TemporaryEdits) -> ToolResult:
        refused = temporary_problem(context, args.kind, args.reason)
        if not refused and not (args.path and args.text):
            refused = "mark needs `path` and `text` (the lines as they are in the file now)."
        if refused:
            return ToolResult(ok=False, content=refused)
        workspace = context.workspace
        if not workspace.path_of(args.path).is_file():
            return ToolResult(ok=False, content=f"{args.path} does not exist.")
        current = workspace.read_text(args.path)[0]
        found = current.count(args.text)
        if found != 1:
            return ToolResult(
                ok=False,
                content=f"`text` was found {found} times in {args.path}; it must be there exactly once. Give the "
                "lines exactly as they are in the file, with enough of them to be unique.",
            )
        hunks = hunks_between(current.replace(args.text, args.original), current)
        if not hunks:
            return ToolResult(
                ok=False, content="`text` and `original` are the same: there is nothing to record."
            )
        number = edits.add(args.path, args.kind, args.reason, "edit", hunks)
        return ToolResult(
            ok=True,
            content=f"Recorded as temporary change #{number} ({args.kind}) in {normal_path(args.path)}: it stays in "
            "the copy and will not be delivered.",
        )

    @staticmethod
    async def _remove(
        args: TemporaryEditsTool.Args, context: ToolContext, edits: TemporaryEdits
    ) -> ToolResult:
        workspace = context.workspace
        wanted = [entry for entry in edits.active() if not args.ids or entry["id"] in args.ids]
        if not wanted:
            return ToolResult(ok=True, content="No active temporary change with those numbers.")
        done: list[Entry] = []
        failed: list[str] = []
        for path in sorted({entry["path"] for entry in wanted}):
            mine = [entry for entry in wanted if entry["path"] == path]
            exists = workspace.path_of(path).is_file()
            for entry in [entry for entry in mine if entry["op"] == "create"]:
                if exists:  # the whole file was temporary: it goes
                    workspace.delete(path, reason=f"temporary change #{entry['id']} taken out")
                    context.note_edit(path)
                    await context.emit("file_changed", {"path": path, "op": "delete", "diff": ""})
                    exists = False
                done.append(entry)
            edited = [entry for entry in mine if entry["op"] == "edit"]
            if not edited:
                continue
            if not exists:
                done += edited  # the file is gone, and the change with it
                continue
            text, taken, left = edits.without(path, workspace.read_text(path)[0], [e["id"] for e in edited])
            if taken:
                numbers = ", ".join(f"#{entry['id']}" for entry in taken)
                saved = await save_marked(
                    context, path, text, f"temporary change {numbers} taken out", "edit"
                )
                if not saved.ok:
                    failed.append(f"{path}: {saved.content}")
                    continue
                done += taken
            failed += [
                f"{describe(entry)}: the lines were changed since; change the file by hand, then call remove again"
                for entry in left
            ]
        edits.mark_removed([entry["id"] for entry in done])
        lines = [f"Taken out: {describe(entry)}" for entry in done]
        lines += [f"Not taken out: {line}" for line in failed]
        if done:
            lines.append("Run your check again: the copy now runs without these changes.")
        return ToolResult(ok=not failed, content="\n".join(lines))

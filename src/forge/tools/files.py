"""File tools (spec §9.1). All writes go through the workspace gate (jail, checkpoint, baseline)."""

from __future__ import annotations

import difflib
import re
from pathlib import Path

from pydantic import Field

from forge.errors import ForgeError
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools.diagnostics import diagnose_file
from forge.workspace.text_format import detect_format

DEFAULT_READ_LIMIT = 2000
MAX_LINE_CHARS = 2000
REASON_HELP = "One line saying why; shown to the user in CHANGES.md."
PATH_HELP = "Path relative to the repository root, e.g. backend/app/routes.py"
_ENV_KEY = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_.-]*)\s*[=:]")


class ReadFile(Tool):
    name = "read_file"
    read_only = True
    description = (
        "Read a text file from the workspace copy of the repository. Returns numbered lines "
        f"(up to {DEFAULT_READ_LIMIT} by default); use offset/limit for large files. You must read a "
        "file before editing or overwriting it. Secret files (.env etc.) show key names only."
    )

    class Args(ToolArgs):
        path: str = Field(description=PATH_HELP)
        offset: int = Field(default=1, ge=1, description="First line to return (1-based).")
        limit: int = Field(default=DEFAULT_READ_LIMIT, ge=1, le=10_000, description="Number of lines.")

    def summary(self, args: ReadFile.Args) -> str:
        return f"read {args.path}"

    async def run(self, args: ReadFile.Args, context: ToolContext) -> ToolResult:
        workspace = context.workspace
        path = workspace.path_of(args.path)
        if not path.is_file():
            return ToolResult(
                ok=False, content=f"{args.path} does not exist.{_similar_hint(context, args.path)}"
            )
        data = path.read_bytes()
        context.reads.record(args.path, data)
        if workspace.is_secret(args.path):
            keys = [
                m.group(1)
                for line in data.decode("utf-8", "replace").splitlines()
                if (m := _ENV_KEY.match(line))
            ]
            return ToolResult(
                ok=True,
                content=f"{args.path} is a secret file; values are hidden. Keys: "
                + (", ".join(keys) or "(none)"),
            )
        file_format = detect_format(data)
        if file_format.binary:
            return ToolResult(ok=True, content=f"{args.path} is a binary file ({len(data)} bytes).")
        text, _ = workspace.read_text(args.path)
        lines = text.splitlines()
        if not lines:
            return ToolResult(ok=True, content=f"{args.path} is empty.")
        chosen = lines[args.offset - 1 : args.offset - 1 + args.limit]
        numbered = [f"{number:>6}\t{_clip(line)}" for number, line in enumerate(chosen, start=args.offset)]
        remaining = len(lines) - (args.offset - 1 + len(chosen))
        footer = (
            f"\n[{remaining} more lines; read again with offset={args.offset + len(chosen)}]"
            if remaining > 0
            else ""
        )
        return ToolResult(
            ok=True,
            content="\n".join(numbered) + footer,
            meta={"lines": len(lines), "newline": file_format.newline},
        )


class WriteFile(Tool):
    name = "write_file"
    description = (
        "Create a new file or completely replace an existing one (you must have read an existing file "
        "first). Prefer edit_file for changes to existing files. Encoding and line endings are preserved."
    )

    class Args(ToolArgs):
        path: str = Field(description=PATH_HELP)
        content: str
        reason: str = Field(default="", description=REASON_HELP)

    def summary(self, args: WriteFile.Args) -> str:
        return f"write {args.path} ({len(args.content.splitlines())} lines)"

    async def run(self, args: WriteFile.Args, context: ToolContext) -> ToolResult:
        path = context.workspace.path_of(args.path)
        if path.exists():
            problem = context.reads.check(args.path, path.read_bytes())
            if problem:
                return ToolResult(ok=False, content=problem)
        return await _save(context, args.path, args.content, args.reason, "write")


class EditFile(Tool):
    name = "edit_file"
    description = (
        "Replace an exact piece of text in a file you have read. old_string must match exactly once "
        "(include enough surrounding lines to make it unique) unless replace_all is true. Keep the "
        "file's indentation. Line endings are handled for you."
    )

    class Args(ToolArgs):
        path: str = Field(description=PATH_HELP)
        old_string: str
        new_string: str
        replace_all: bool = False
        reason: str = Field(default="", description=REASON_HELP)

    def summary(self, args: EditFile.Args) -> str:
        return f"edit {args.path}"

    async def run(self, args: EditFile.Args, context: ToolContext) -> ToolResult:
        loaded = _load_for_edit(context, args.path)
        if isinstance(loaded, ToolResult):
            return loaded
        try:
            text = apply_edit(loaded, args.old_string, args.new_string, args.replace_all)
        except EditError as error:
            return ToolResult(ok=False, content=str(error))
        return await _save(context, args.path, text, args.reason, "edit")


class MultiEdit(Tool):
    name = "multi_edit"
    description = (
        "Apply several edits to one file in order, all or nothing. Each edit follows edit_file's rules "
        "and sees the result of the previous one."
    )

    class Args(ToolArgs):
        class Edit(ToolArgs):
            old_string: str
            new_string: str
            replace_all: bool = False

        path: str = Field(description=PATH_HELP)
        edits: list[Edit] = Field(min_length=1)
        reason: str = Field(default="", description=REASON_HELP)

    def summary(self, args: MultiEdit.Args) -> str:
        return f"edit {args.path} ({len(args.edits)} edits)"

    async def run(self, args: MultiEdit.Args, context: ToolContext) -> ToolResult:
        loaded = _load_for_edit(context, args.path)
        if isinstance(loaded, ToolResult):
            return loaded
        text = loaded
        for number, edit in enumerate(args.edits, start=1):
            try:
                text = apply_edit(text, edit.old_string, edit.new_string, edit.replace_all)
            except EditError as error:
                return ToolResult(ok=False, content=f"Edit {number} failed, nothing was changed: {error}")
        return await _save(context, args.path, text, args.reason, "edit")


class DeleteFile(Tool):
    name = "delete_file"
    description = (
        "Delete a file from the workspace copy. Deleting the user's files always needs their approval; "
        "files you created in this workspace follow the normal approval rules."
    )

    class Args(ToolArgs):
        path: str = Field(description=PATH_HELP)
        reason: str = Field(default="", description=REASON_HELP)

    def summary(self, args: DeleteFile.Args) -> str:
        return f"delete {args.path}"

    def own_files_only(self, args: DeleteFile.Args, context: ToolContext) -> bool:
        # Not in the baseline manifest = Forge wrote it in this workspace; the user's files always ask.
        return args.path.replace("\\", "/") not in context.workspace.manifest.files

    async def run(self, args: DeleteFile.Args, context: ToolContext) -> ToolResult:
        under = context.write_only_under
        if under is not None and not args.path.replace("\\", "/").lstrip("./").startswith(under):
            return ToolResult(ok=False, content=f"You may only delete files below {under} (your own checks).")
        context.workspace.delete(args.path, reason=args.reason)
        context.last_edit_step = context.step
        await context.emit("file_changed", {"path": args.path, "op": "delete", "diff": ""})
        return ToolResult(ok=True, content=f"Deleted {args.path}.")


class MoveFile(Tool):
    name = "move_file"
    description = "Move or rename a file inside the workspace copy (used when restructuring)."

    class Args(ToolArgs):
        source: str = Field(description=PATH_HELP)
        destination: str = Field(description=PATH_HELP)
        reason: str = Field(default="", description=REASON_HELP)

    def summary(self, args: MoveFile.Args) -> str:
        return f"move {args.source} -> {args.destination}"

    async def run(self, args: MoveFile.Args, context: ToolContext) -> ToolResult:
        context.workspace.move(args.source, args.destination, reason=args.reason)
        context.last_edit_step = context.step
        await context.emit(
            "file_changed", {"path": args.destination, "op": "move", "from": args.source, "diff": ""}
        )
        return ToolResult(ok=True, content=f"Moved {args.source} to {args.destination}.")


def _clip(line: str) -> str:
    return line if len(line) <= MAX_LINE_CHARS else line[:MAX_LINE_CHARS] + " …[line clipped]"


class EditError(ForgeError):
    pass


def apply_edit(text: str, old: str, new: str, replace_all: bool) -> str:
    if old == new:
        raise EditError("old_string and new_string are identical.")
    if not old:
        raise EditError("old_string is empty; use write_file to create a file.")
    variants = [old, old.replace("\r\n", "\n"), old.replace("\n", "\r\n")]
    for candidate in dict.fromkeys(variants):
        count = text.count(candidate)
        if count == 0:
            continue
        if count > 1 and not replace_all:
            lines = [text.count("\n", 0, index) + 1 for index in _find_all(text, candidate)]
            raise EditError(
                f"old_string matches {count} places (lines {', '.join(map(str, lines[:10]))}). "
                "Add surrounding lines to make it unique, or set replace_all."
            )
        # The new text follows whichever line-ending form matched.
        replacement = new.replace("\r\n", "\n")
        if "\r\n" in candidate:
            replacement = replacement.replace("\n", "\r\n")
        return (
            text.replace(candidate, replacement) if replace_all else text.replace(candidate, replacement, 1)
        )
    raise EditError("old_string was not found." + _nearest_candidates(text, old))


def _find_all(text: str, needle: str) -> list[int]:
    positions, start = [], text.find(needle)
    while start != -1:
        positions.append(start)
        start = text.find(needle, start + len(needle))
    return positions


def _nearest_candidates(text: str, old: str) -> str:
    anchor = next((line.strip() for line in old.splitlines() if line.strip()), "")
    if not anchor:
        return ""
    scored = []
    for number, line in enumerate(text.splitlines(), start=1):
        ratio = difflib.SequenceMatcher(None, anchor, line.strip()).ratio()
        if ratio >= 0.6:
            scored.append((ratio, number, line))
    if not scored:
        return " No similar lines found; read the file again."
    best = sorted(scored, reverse=True)[:3]
    listing = "\n".join(f"  line {number}: {line.strip()[:160]}" for _, number, line in best)
    return f" Closest lines to its first line (check whitespace and exact text):\n{listing}"


def _load_for_edit(context: ToolContext, relative: str) -> str | ToolResult:
    path = context.workspace.path_of(relative)
    if not path.is_file():
        return ToolResult(ok=False, content=f"{relative} does not exist. Use write_file to create it.")
    problem = context.reads.check(relative, path.read_bytes())
    if problem:
        return ToolResult(ok=False, content=problem)
    text, _ = context.workspace.read_text(relative)
    return text


async def _save(context: ToolContext, relative: str, text: str, reason: str, op: str) -> ToolResult:
    workspace = context.workspace
    if context.write_only_under is not None and not relative.replace("\\", "/").lstrip("./").startswith(
        context.write_only_under
    ):
        return ToolResult(
            ok=False,
            content=f"You may only write below {context.write_only_under} (you are verifying, not "
            "changing the app). If the app is wrong, report it; the main agent fixes it.",
        )
    path = workspace.path_of(relative)
    before = workspace.read_text(relative)[0] if path.is_file() else ""
    if text.count("[REDACTED:") > before.count("[REDACTED:"):
        # Seen live: the model copied masked text it had been shown back into test files.
        return ToolResult(
            ok=False,
            content="Not saved: the content contains a [REDACTED:…] marker. That text was hidden from you "
            "because it looked like a secret; never write the marker into code. Use an obvious placeholder "
            "(e.g. 'test-api-key' in tests) or read the value from the environment/config.",
        )
    created = not path.is_file()
    workspace.write_text(relative, text, reason=reason)
    context.last_edit_step = context.step
    context.reads.record(relative, Path(path).read_bytes())  # the model now knows the current content
    diff = "".join(
        difflib.unified_diff(before.splitlines(True), text.splitlines(True), f"a/{relative}", f"b/{relative}")
    )
    await context.emit("file_changed", {"path": relative, "op": "create" if created else op, "diff": diff})
    message = f"{'Created' if created else 'Updated'} {relative}."
    problem = await diagnose_file(workspace, relative)
    return ToolResult(
        ok=True, content=message + (f"\n{problem}" if problem else ""), meta={"diagnostics_ok": not problem}
    )


def _similar_hint(context: ToolContext, relative: str) -> str:
    name = Path(relative).name
    matches = [
        p.relative_to(context.workspace.repo_dir).as_posix()
        for p in context.workspace.repo_dir.rglob(name)
        if p.is_file()
    ][:5]
    return (" Files with that name: " + ", ".join(matches)) if matches else ""

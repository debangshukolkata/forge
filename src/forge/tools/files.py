"""File tools (spec §9.1). All writes go through the workspace gate (jail, checkpoint, baseline)."""

from __future__ import annotations

import difflib
import re
from pathlib import Path

from pydantic import Field

from forge.errors import ForgeError
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools.baseline_gate import baseline_gate, rewrite_gate
from forge.tools.diagnostics import diagnose_file
from forge.workspace.text_format import decode_text, detect_format

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
        "file before editing or overwriting it. Secret files (.env etc.) show key names only. A full path "
        "works for places the user opened for reading (their message or a skill's folder names it)."
    )

    class Args(ToolArgs):
        path: str = Field(description=PATH_HELP)
        offset: int = Field(default=1, ge=1, description="First line to return (1-based).")
        limit: int = Field(default=DEFAULT_READ_LIMIT, ge=1, le=10_000, description="Number of lines.")

    def summary(self, args: ReadFile.Args) -> str:
        return f"read {args.path}"

    async def run(self, args: ReadFile.Args, context: ToolContext) -> ToolResult:
        workspace = context.workspace
        path = workspace.input_path(args.path) or workspace.path_of(args.path)
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
        text = decode_text(data, file_format)  # the bytes already read: the path may be an attachment (D-469)
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
        # Not in the baseline manifest = DebCraft wrote it in this workspace; the user's files always ask.
        return args.path.replace("\\", "/") not in context.workspace.manifest.files

    async def run(self, args: DeleteFile.Args, context: ToolContext) -> ToolResult:
        under = context.write_only_under
        if under is not None and not args.path.replace("\\", "/").lstrip("./").startswith(under):
            return ToolResult(ok=False, content=f"You may only delete files below {under} (your own checks).")
        context.workspace.delete(args.path, reason=args.reason)
        context.note_edit(args.path)
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
        under = context.write_only_under
        if under is not None:
            for path in (args.source, args.destination):
                if not path.replace("\\", "/").lstrip("./").startswith(under):
                    return ToolResult(ok=False, content=f"You may only move files below {under}.")
        context.workspace.move(args.source, args.destination, reason=args.reason)
        context.note_edit(args.source, args.destination)
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


UI_SUFFIXES = (
    ".html",
    ".css",
    ".scss",
    ".jsx",
    ".tsx",
    ".vue",
    ".svelte",
)  # files that decide how a page looks
CANDIDATES_REFUSALS = 3
DESIGN_GATE_ROUNDS = 4  # asked at most four times per session (no DESIGN.md, errors in it): a wrong refusal can never trap the model
DESIGN_NOTE = (
    "Before the first page or style file of a project: write its DESIGN.md in the TOKEN FORMAT: front matter between --- lines with name, colors "
    "(primary, neutral, ink, muted, surface, border), typography (display and body-md, each with fontFamily, fontSize, fontWeight, lineHeight), rounded, "
    "spacing and components, then prose sections (Overview, Colors, Typography, Layout, Components, Do's and Don'ts). Other key names (palette, type) "
    "are not read. find_asset (type design-system) has complete examples to start from; read_file on the recipe design-md-template.md shows the shape. "
    "In it, compactly: the product and who "
    "it is for in a sentence; 4 to 6 named colours with hex values; the type roles with family, size and weight; the layout of each screen "
    "as a small ASCII wireframe; one alignment and spacing rule; three design principles. Check it against the brief and replace every "
    "generic choice (a default blue, a default font, a row of three cards) with one that comes from the product. The ui-design-quality skill "
    "(sections 0c and 0d) has the details. Then write this file again."
)


def find_design_md(workspace: object, relative: str) -> Path | None:
    """The DESIGN.md in the file's folder or any folder above it up to the repository root (or docs/DESIGN.md at the root)."""
    repo = workspace.repo_dir.resolve()  # type: ignore[attr-defined]
    folder = workspace.path_of(relative).resolve().parent  # type: ignore[attr-defined]
    while True:
        for name in ("DESIGN.md", "design.md"):
            if (folder / name).is_file():
                return Path(folder / name)
        if folder == repo or repo not in folder.parents:
            break
        folder = folder.parent
    return next(
        ((repo / "docs" / name) for name in ("DESIGN.md", "design.md") if (repo / "docs" / name).is_file()),
        None,
    )


CANDIDATES_NOTE = (
    "Your DESIGN.md is a first draft. Before the first page, compare candidates (the ui-design-quality skill, section 0e): keep this file as "
    "candidate A (or copy it to .forge/candidates/a/DESIGN.md), write two more DESIGN.md files (.forge/candidates/b and c) that differ from it "
    "and from each other in at least three of: light or dark tone, accent hue, composition (name a layout from find_asset type section, tag composition, or for an application tag 'app screen'; write it as `composition: lay-...` or `composition: app-...` in the front matter), display font, corner style, density, layout energy; find_asset "
    "(type design-system) has tokenised starting points. Run design_candidates with the brief, apply the winner's fixes, design_md_import the "
    "winner as DESIGN.md (overwrite), and then write the page. Never make the three differ only in colour; each names a real display font and text font that suit the product, its mood and its language (find_asset type font-pairing, find_font), never the system stack."
)


def _rounds_file(context: ToolContext) -> Path:
    return Path(context.workspace.root) / ".forge" / "design-rounds.json"


def design_md_exists(workspace: object, relative: str) -> bool:
    return find_design_md(workspace, relative) is not None


def design_gate(context: ToolContext, relative: str) -> str:
    """D4 (D-312): the model skipped DESIGN.md in all three page-redesign speed runs although the skill asks for it first, so the first UI
    file of a project without one is refused with what to write. Twice at most; DESIGN.md itself and non-UI files pass. A DESIGN.md the
    model wrote itself must also have been compared with candidates once (D-352: the first design benchmark run skipped the whole
    design ladder, so it is a gate and not only advice); a file the user supplied is never questioned."""
    clean = relative.replace("\\", "/")
    if not clean.lower().endswith(UI_SUFFIXES):
        return ""
    found = find_design_md(context.workspace, relative)
    if (
        found is not None
        and context.design_md_written
        and context.design_candidates_refusals < CANDIDATES_REFUSALS
        and not _rounds_file(context).is_file()
    ):
        # The file is the model's own and no candidates were compared: refused three times, whatever else is wrong with it (the fifth benchmark
        # run spent its two other rounds writing pages before a DESIGN.md existed and then slipped through with a file that had an error).
        context.design_candidates_refusals += 1
        broken = _design_md_errors(found)
        errors_first = (
            f"The DESIGN.md has errors to fix first (design_md_lint shows them):\n{broken}\n\n"
            if broken
            else ""
        )
        return errors_first + CANDIDATES_NOTE
    if context.design_gate_rounds >= DESIGN_GATE_ROUNDS:
        return ""
    if found is not None:
        broken = _design_md_errors(found)
        if broken:
            context.design_gate_rounds += 1
            return f"The project's DESIGN.md has errors that must be fixed before pages are built (design_md_lint shows them):\n{broken}"
        return ""
    context.design_gate_rounds += 1
    return DESIGN_NOTE


def _design_md_errors(path: Path) -> str:
    """The lint errors of a DESIGN.md that uses the token format; a free-text file (a company brand guide) is accepted as it is."""
    from forge.designsystem.lint import describe_findings, lint_text

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if not text.lstrip().lstrip(chr(0xFEFF)).lstrip().startswith("---"):
        return ""
    errors = [f for f in lint_text(text) if f.severity == "error"]
    return describe_findings(errors) if errors else ""


ALLOWED_CONTROL = chr(9) + chr(10) + chr(13)


def control_character_problem(text: str, before: str = "") -> str | None:
    """A text file must not gain control characters. Seen live (D-379): the model's arguments carried an en dash and a curly apostrophe as U+0013 and U+0019, the
    file then held NUL bytes and every later write failed with 'is a binary file'. Said at once, with the place and the fix, the model repairs one line instead."""

    def control(value: str) -> list[int]:
        return [i for i, ch in enumerate(value) if ord(ch) < 32 and ch not in ALLOWED_CONTROL]

    found = control(text)
    if len(found) <= len(control(before)):
        return None
    first = found[0]
    line = text.count(chr(10), 0, first) + 1
    column = first - text.rfind(chr(10), 0, first)
    around = text[max(0, first - 30) : first + 30].replace(chr(10), " ")
    return (
        f"Not saved: the text has {len(found)} control character(s), the first U+{ord(text[first]):04X} at line {line}, column {column} (near: {around!r}). "
        "That is usually a mangled en dash, curly quote or other non-ASCII character. Write it as the plain character or an HTML entity (&ndash;, &rsquo;) "
        "and send the file again."
    )


def candidate_composition_note(text: str) -> str:
    """A candidate DESIGN.md that does not name its composition is refused later by design_candidates, which made the model rewrite all three files (seen in the night-1 design run).
    Said at once, the fix is one edit (D-386)."""
    from forge.designsystem.spec import DesignMdError, parse_design_md

    try:
        system = parse_design_md(text)
    except DesignMdError:
        return ""
    if str(system.extra.get("composition", "") or "").strip():
        return ""
    return (
        "This candidate does not name its composition yet. Add `composition: lay-<name>` (marketing page), `composition: app-<name>` (application screen) or `composition: custom <one line>` "
        "to its front matter with ONE small edit (multi_edit), not a rewrite: design_candidates refuses a candidate without it."
    )


async def _save(context: ToolContext, relative: str, text: str, reason: str, op: str) -> ToolResult:
    workspace = context.workspace
    if context.write_only_under is not None and not relative.replace("\\", "/").lstrip("./").startswith(
        context.write_only_under
    ):
        return ToolResult(
            ok=False,
            content=(
                f"You may only write below {context.write_only_under}: that folder is your piece of the work. "
                "A change outside it belongs to the main agent or another builder: say so in your report."
                if context.write_only_is_builder
                else f"You may only write below {context.write_only_under} (you are verifying, not "
                "changing the app). If the app is wrong, report it; the main agent fixes it."
            ),
        )
    if context.design_first and context.write_only_under is None:
        asked = design_gate(context, relative)
        if asked:
            return ToolResult(ok=False, content=asked)
    path = workspace.path_of(relative)
    if context.write_only_under is None:
        asked = baseline_gate(context, relative, path.is_file())
        if asked:
            return ToolResult(ok=False, content=asked)
    before = workspace.read_text(relative)[0] if path.is_file() else ""
    if op == "write" and context.write_only_under is None:
        refused = rewrite_gate(context, relative, before, text)
        if refused:
            return ToolResult(ok=False, content=refused)
    if text.count("[REDACTED:") > before.count("[REDACTED:"):
        # Seen live: the model copied masked text it had been shown back into test files.
        return ToolResult(
            ok=False,
            content="Not saved: the content contains a [REDACTED:…] marker. That text was hidden from you "
            "because it looked like a secret; never write the marker into code. Use an obvious placeholder "
            "(e.g. 'test-api-key' in tests) or read the value from the environment/config.",
        )
    mangled = control_character_problem(text, before)
    if mangled:
        return ToolResult(ok=False, content=mangled)
    created = not path.is_file()
    workspace.write_text(relative, text, reason=reason)
    context.note_edit(relative)
    context.reads.record(relative, Path(path).read_bytes())  # the model now knows the current content
    diff = "".join(
        difflib.unified_diff(before.splitlines(True), text.splitlines(True), f"a/{relative}", f"b/{relative}")
    )
    await context.emit("file_changed", {"path": relative, "op": "create" if created else op, "diff": diff})
    message = f"{'Created' if created else 'Updated'} {relative}."
    if Path(relative).name.lower() == "design.md" and not relative.replace("\\", "/").startswith(".forge/"):
        context.design_md_written = True
    if Path(relative).name.lower() == "design.md":
        from forge.designsystem.lint import describe_findings, lint_text

        message += "\n" + describe_findings([f for f in lint_text(text) if f.severity != "info"], 15)
        if ".forge/candidates/" in relative.replace("\\", "/"):
            note = candidate_composition_note(text)
            if note:
                message += "\n" + note
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

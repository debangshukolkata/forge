"""Builds the deliverable output/ folder (spec §6.2-6.4): only new and modified files, at the same
repository-relative paths, plus CHANGES.md, changes.patch, COPY_INSTRUCTIONS.md and MANIFEST.json."""

from __future__ import annotations

import difflib
import os
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from forge.safety.paths import os_path
from forge.workspace.copy_repo import iter_source_files
from forge.workspace.manifest import sha256_of
from forge.workspace.server_checks import load_checks, server_run_md
from forge.workspace.temporary_edits import Entry, TemporaryEdits
from forge.workspace.text_format import decode_text, detect_format, encode_text
from forge.workspace.workspace import Workspace

FileStatus = Literal["added", "modified", "deleted"]

# Data the app wrote while DebCraft ran it (a SQLite file with test rows): not code, so never delivered (D-222).
RUNTIME_DATA_SUFFIXES = (".sqlite", ".sqlite3", ".db", ".db-journal", ".db-wal", ".db-shm")


class FileChange(BaseModel):
    path: str
    status: FileStatus
    sha256: str | None = None
    secret: bool = False
    binary: bool = False
    moved_from: str | None = None
    reasons: list[str] = Field(default_factory=list)
    # Reasons of temporary changes that could not be taken out of this file (WF2): the user removes them by hand.
    temporary_left: list[str] = Field(default_factory=list)


class OutputManifest(BaseModel):
    """output/MANIFEST.json — machine-readable, used by Diagnose mode (M9)."""

    generated: str
    repository: str
    files: list[FileChange]
    temporary: list[dict[str, str]] = Field(default_factory=list)  # every temporary change, active or removed


def delivered_bytes(
    workspace: Workspace, relative: str, data: bytes, edits: TemporaryEdits
) -> tuple[bytes, list[Entry]]:
    """What is delivered for a file that holds temporary changes (WF2): its content with those changes taken out,
    in the file's own encoding and line endings, and the entries that could not be taken out."""
    marked = [entry for entry in edits.active(relative) if entry.get("op") == "edit"]
    if not marked:
        return data, []
    file_format = detect_format(data)
    if file_format.binary:
        return data, marked
    text, _, left = edits.without(relative, decode_text(data, file_format))
    return encode_text(text, file_format), left


def _marked_paths(edits: TemporaryEdits) -> tuple[set[str], set[str]]:
    """(files with a temporary edit, files that are temporary as a whole)."""
    active = edits.active()
    return (
        {entry["path"] for entry in active if entry.get("op") == "edit"},
        {entry["path"] for entry in active if entry.get("op") == "create"},
    )


def compute_changes(workspace: Workspace) -> list[FileChange]:
    manifest = workspace.manifest.files
    rules = workspace.ignore_rules()
    edits = TemporaryEdits(workspace)
    edited, created = _marked_paths(edits)
    current: dict[str, bytes] = {}
    for top in sorted(p.name for p in workspace.repo_dir.iterdir()):
        if (workspace.repo_dir / top).is_dir():
            for relative, path, is_link in iter_source_files(workspace.repo_dir, top, rules):
                if not is_link:
                    current[relative] = Path(path).read_bytes()
        elif not rules.is_ignored(top, is_dir=False):
            current[top] = (workspace.repo_dir / top).read_bytes()

    changes: dict[str, FileChange] = {}
    for relative, data in current.items():
        entry = manifest.get(relative)
        if relative.lower().endswith(RUNTIME_DATA_SUFFIXES):
            continue
        if entry is None and relative in created:
            continue  # a file written only to investigate is not delivered
        left: list[Entry] = []
        if relative in edited:
            data, left = delivered_bytes(workspace, relative, data, edits)
        if entry is None or entry.sha256 != sha256_of(data):
            changes[relative] = FileChange(
                path=relative,
                status="added" if entry is None else "modified",
                sha256=sha256_of(data),
                secret=workspace.is_secret(relative),
                binary=detect_format(data).binary,
                temporary_left=[str(item["reason"]) for item in left],
            )
    for relative, entry in manifest.items():
        if relative not in current:
            changes[relative] = FileChange(path=relative, status="deleted", secret=entry.secret)

    for change in workspace.changes():
        if change.path in changes and change.reason:
            changes[change.path].reasons.append(change.reason)
        if change.op == "move" and change.path in changes and changes.get(change.from_path or ""):
            changes[change.path].moved_from = change.from_path
    return [changes[key] for key in sorted(changes)]


def changes_of(workspace: Workspace, names: set[str]) -> list[FileChange]:
    """`compute_changes` for the named files only (a path, or its end), without reading the whole copy (D-672)."""
    manifest = workspace.manifest.files
    edits = TemporaryEdits(workspace)
    edited, _ = _marked_paths(edits)
    found: list[FileChange] = []
    for name in sorted(names):
        candidates = [name] if (workspace.repo_dir / name).is_file() or name in manifest else []
        candidates += [key for key in manifest if key.endswith("/" + name) and key not in candidates]
        for relative in candidates:
            path = workspace.repo_dir / relative
            entry = manifest.get(relative)
            if not path.is_file():
                if entry is not None:
                    found.append(FileChange(path=relative, status="deleted", secret=entry.secret))
                continue
            data = path.read_bytes()
            if relative in edited:
                data, _ = delivered_bytes(workspace, relative, data, edits)
            if entry is None or entry.sha256 != sha256_of(data):
                found.append(
                    FileChange(
                        path=relative,
                        status="added" if entry is None else "modified",
                        sha256=sha256_of(data),
                        secret=workspace.is_secret(relative),
                    )
                )
    return found


def build_output(workspace: Workspace) -> OutputManifest:
    changes = compute_changes(workspace)
    edits = TemporaryEdits(workspace)
    edited, _ = _marked_paths(edits)
    _clear_output(workspace)
    for change in changes:
        if change.status != "deleted" and not change.secret:
            target = workspace.jail.check(workspace.output_dir / change.path)
            os.makedirs(os_path(target.parent, force=True), exist_ok=True)
            source = workspace.repo_dir / change.path
            if change.path in edited:  # delivered without its temporary changes; the copy keeps them
                data, _ = delivered_bytes(workspace, change.path, source.read_bytes(), edits)
                Path(os_path(target)).write_bytes(data)
            else:
                shutil.copy2(source, os_path(target))

    report = OutputManifest(
        generated=datetime.now().isoformat(timespec="seconds"),
        repository=workspace.info.repo_path,
        files=changes,
        temporary=[
            {key: str(entry.get(key, "")) for key in ("id", "kind", "path", "reason", "state")}
            for entry in edits.entries()
        ],
    )
    _write(workspace, "MANIFEST.json", report.model_dump_json(indent=1))
    _write(workspace, "changes.patch", build_patch(workspace, changes))
    _write(workspace, "CHANGES.md", build_changes_md(workspace, changes))
    db_changes = build_db_changes(workspace, changes)
    if db_changes:
        _write(workspace, "DB_CHANGES.sql", db_changes)
    checks = load_checks(workspace)
    if checks:
        _write(workspace, "SERVER_RUN.md", server_run_md(checks, workspace.info.app_subfolder))
    _write(workspace, "COPY_INSTRUCTIONS.md", build_copy_instructions(workspace, changes))
    return report


def sql_changes(changes: list[FileChange]) -> list[FileChange]:
    """New or modified .sql scripts, in run order (the repo's naming convention sorts them: V004 < V005)."""
    scripts = [
        c for c in changes if c.status != "deleted" and not c.secret and c.path.lower().endswith(".sql")
    ]
    return sorted(scripts, key=lambda c: (c.path.rsplit("/", 1)[0], c.path.rsplit("/", 1)[-1].lower()))


def build_db_changes(workspace: Workspace, changes: list[FileChange]) -> str | None:
    """Spec §9.5: every new/changed SQL script, concatenated in run order, for whoever applies them."""
    scripts = sql_changes(changes)
    if not scripts:
        return None
    parts = [
        f"-- DB changes for {workspace.info.name}: run these scripts in this order.",
        "-- Each one is also delivered as its own file at the same path in output/.",
        *[f"--   {number}. {c.path} ({c.status})" for number, c in enumerate(scripts, 1)],
        "",
    ]
    for c in scripts:
        text = _decoded(workspace.repo_dir / c.path).rstrip()
        parts += [f"-- ===== {c.path} =====", text, ""]
    return "\n".join(parts)


def build_patch(workspace: Workspace, changes: list[FileChange]) -> str:
    chunks = []
    for change in changes:
        if change.secret:
            continue
        if change.binary:
            chunks.append(f"Binary file {change.path} {change.status}\n")
            continue
        texts = file_texts(workspace, change)
        if texts is None:  # binary before or after (a deleted or replaced binary file is not flagged as one)
            chunks.append(f"Binary file {change.path} {change.status}\n")
            continue
        before, after = texts
        chunks.append(
            "".join(
                difflib.unified_diff(
                    before.splitlines(keepends=True),
                    after.splitlines(keepends=True),
                    fromfile="/dev/null" if change.status == "added" else f"a/{change.path}",
                    tofile="/dev/null" if change.status == "deleted" else f"b/{change.path}",
                )
            )
        )
    return "".join(chunk if chunk.endswith("\n") else chunk + "\n" for chunk in chunks if chunk)


def build_changes_md(workspace: Workspace, changes: list[FileChange]) -> str:
    lines = [f"# Changes — {workspace.info.name}", "", "All paths are relative to the repository root.", ""]
    lines += temporary_section(TemporaryEdits(workspace).entries())
    for change in changes:
        lines += [f"## {change.path}", "", f"**Status:** {change.status}"]
        for reason in change.temporary_left:
            lines.append(TEMPORARY_LEFT.format(reason=reason))
        if change.moved_from:
            lines.append(f"**Moved from:** `{change.moved_from}`")
        for reason in change.reasons:
            lines.append(f"- {reason}")
        lines.append("")
        if change.secret:
            lines += ["Secret/config file: contents are not shown or exported. Apply the change by hand.", ""]
        elif change.binary:
            lines += ["Binary file: copy it from `output/`.", ""]
        elif change.status != "deleted":
            texts = file_texts(workspace, change)
            if texts is None:
                lines += [
                    "Binary file: no text diff. Copy it from `output/`, or delete it if the status is deleted.",
                    "",
                ]
                continue
            before, after = texts
            diff = "".join(
                difflib.unified_diff(before.splitlines(True), after.splitlines(True), "before", "after")
            )
            lines += ["```diff", diff.rstrip("\n"), "```", ""]
    return "\n".join(lines) + "\n"


TEMPORARY_LEFT = (
    "**This file still holds a temporary change DebCraft could not take out: {reason}. Remove it by hand before "
    "you copy the file.**"
)


def temporary_section(entries: list[Entry]) -> list[str]:
    """What was changed only to investigate (WF2). A bypass that was still in place at the end means the part
    it bypasses never ran: the user must know that the proof does not cover it."""
    if not entries:
        return []
    lines = ["## Temporary changes (not in these files)", ""]
    for entry in entries:
        line = f"- {entry['kind']}, `{entry['path']}`: {str(entry['reason']).rstrip('.')}."
        if entry.get("state") != "active":
            line += " Taken out again during the work."
        elif entry["kind"] == "bypass":
            line += " The solution was proved with this in place; what it bypasses was not exercised."
        lines.append(line)
    return [*lines, ""]


def build_copy_instructions(workspace: Workspace, changes: list[FileChange]) -> str:
    states = repository_states(workspace, changes)
    already = [c for c in changes if states.get(c.path) in ("same", "applied") and not c.secret]
    changes = [
        c for c in changes if c not in already
    ]  # nothing to do for what the repository already has (D-672)
    added = [c for c in changes if c.status == "added" and not c.secret]
    modified = [c for c in changes if c.status == "modified" and not c.secret]
    deleted = [
        c for c in changes if c.status == "deleted" and not c.secret and not _is_move_source(c, changes)
    ]
    secret = [c for c in changes if c.secret]
    repo = workspace.info.repo_path
    lines = [
        f"# Copy instructions — {workspace.info.name}",
        "",
        f"Repository: `{repo}`. All paths are relative to the repository root; copy each file from "
        "`output/` to the same path in your repository.",
        "",
        f"## 1. Add new files ({len(added)})",
        "",
        *_file_table(added, "new"),
        f"## 2. Replace modified files ({len(modified)})",
        "",
        "If you have local edits in one of these files, paste only the changed sections shown in CHANGES.md.",
        "",
        *_file_table(modified, "replace"),
        f"## 3. Delete files ({len(deleted)})",
        "",
        *([f"- Delete `{c.path}`" for c in deleted] or ["None."]),
        "",
    ]
    if already:
        lines += [
            f"## Already in your repository ({len(already)}): nothing to do",
            "",
            *[
                f"- `{c.path}`"
                + (
                    " (the same file)"
                    if states[c.path] == "same"
                    else " (every changed line is there; order or comments may differ)"
                )
                for c in already
            ],
            "",
        ]
    if secret:
        lines += ["## Secret/config files changed (not exported — apply by hand)", ""]
        lines += [f"- `{c.path}` ({c.status})" for c in secret] + [""]
    lines += [
        "## 4. Registrations",
        "",
        "None recorded.",
        "",
        "## 5. Dependencies, SQL and environment variables",
        "",
        *_extras(workspace, changes),
        "",
        "## 6. Verify",
        "",
        f"From `{workspace.info.app_subfolder}` with your venv active: `python -m pytest -q`",
        "",
    ]
    checks = load_checks(workspace)
    if checks:
        lines += [
            f"DebCraft could not run {len(checks)} DB-dependent check(s): see SERVER_RUN.md for the exact "
            "commands, and run them once you're connected.",
            "",
        ]
    return "\n".join(lines)


def _extras(workspace: Workspace, changes: list[FileChange]) -> list[str]:
    lines = []
    scripts = sql_changes(changes)
    if scripts:
        lines.append(
            f"- SQL: run {len(scripts)} script(s) in the order listed at the top of DB_CHANGES.sql "
            "(same content as the .sql files above), on each database that needs them."
        )
    for name, what in (("NEW_DEPENDENCIES.md", "packages"), ("ENV_CHANGES.md", "environment variables")):
        if (workspace.output_dir / name).exists():
            lines.append(f"- New {what}: see {name}.")
    return lines or ["None for this change."]


def _file_table(changes: list[FileChange], kind: str) -> list[str]:
    if not changes:
        return ["None.", ""]
    rows = ["| # | File | Notes |", "|---|---|---|"]
    for number, change in enumerate(changes, start=1):
        note = f"moved from `{change.moved_from}` (delete the old file)" if change.moved_from else kind
        for reason in change.temporary_left:
            note += ". " + TEMPORARY_LEFT.format(reason=reason)
        rows.append(f"| {number} | `{change.path}` | {note} |")
    return [*rows, ""]


def _is_move_source(change: FileChange, changes: list[FileChange]) -> bool:
    return any(other.moved_from == change.path for other in changes)


def file_texts(workspace: Workspace, change: FileChange) -> tuple[str, str] | None:
    """The text before and after a change, or None when either side is binary (no text diff exists)."""
    saved = workspace.forge_dir / "baseline" / change.path
    # Files changed outside the writer (e.g. by a formatter run in the shell) have no saved baseline;
    # the untouched original in the user's repository is then the "before".
    original = saved if saved.exists() else Path(workspace.info.repo_path) / change.path
    try:
        before = _decoded(original) if change.status != "added" else ""
        after = ""
        if change.status != "deleted":  # the delivered text: without the temporary changes (WF2)
            current = workspace.repo_dir / change.path
            data = current.read_bytes() if current.exists() else b""
            data, _ = delivered_bytes(workspace, change.path, data, TemporaryEdits(workspace))
            after = decode_text(data, detect_format(data))
    except ValueError:  # decode_text refuses binary content
        return None
    return before, after


COMMENT_LINE = ("#", "//", "--", "<!--", "/*", "*")


def _plain_lines(text: str) -> list[str]:
    """The lines that carry code: stripped, without blank and comment-only lines."""
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith(COMMENT_LINE)
    ]


def repository_state(workspace: Workspace, change: FileChange) -> str | None:
    """Is this change already in the user's repository as it is NOW (D-672)? "same": the file there is the delivered
    one; "applied": every changed code line is there (order, spacing or comments may differ, as when the user pasted
    only the line that matters); "differs": something is still to copy; "missing": the file is not there. None in
    Mode B, where there is no repository to compare with. The baseline is the copy made when the project started; the
    user applies changes after that, so a list of changes against the baseline alone asked the user to copy again
    what was copied the day before (office, 2026-11-27)."""
    if workspace.mode_b or not workspace.info.repo_path:
        return None
    original = Path(workspace.info.repo_path) / change.path
    if change.status == "deleted":
        return "same" if not original.exists() else "differs"
    if not original.is_file():
        return "missing"
    texts = file_texts(workspace, change)
    if texts is None:
        return "differs"
    before, after = texts
    theirs = _decoded(original)
    if theirs == after or theirs.replace("\r\n", "\n") == after.replace("\r\n", "\n"):
        return "same"
    before_lines, after_lines, their_lines = (
        Counter(_plain_lines(before)),
        Counter(_plain_lines(after)),
        Counter(_plain_lines(theirs)),
    )
    added = after_lines - before_lines
    removed = before_lines - after_lines
    if not added and not removed:  # only comments or spacing changed: nothing that runs is missing there
        return "applied"
    has_added = all(their_lines[line] >= count for line, count in added.items())
    lacks_removed = all(their_lines[line] <= after_lines[line] for line in removed)
    return "applied" if has_added and lacks_removed else "differs"


def repository_states(workspace: Workspace, changes: list[FileChange]) -> dict[str, str]:
    """`repository_state` of every change that has one."""
    states = {change.path: repository_state(workspace, change) for change in changes}
    return {path: state for path, state in states.items() if state is not None}


def _decoded(path: Path) -> str:
    if not path.exists():
        return ""
    data = path.read_bytes()
    return decode_text(data, detect_format(data))


def _clear_output(workspace: Workspace) -> None:
    for child in workspace.output_dir.iterdir():
        target = workspace.jail.check(child)
        shutil.rmtree(target) if target.is_dir() else target.unlink()


def _write(workspace: Workspace, name: str, text: str) -> None:
    workspace.jail.check(workspace.output_dir / name).write_text(text, encoding="utf-8")

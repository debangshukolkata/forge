"""Builds the deliverable output/ folder (spec §6.2-6.4): only new and modified files, at the same
repository-relative paths, plus CHANGES.md, changes.patch, COPY_INSTRUCTIONS.md and MANIFEST.json."""

from __future__ import annotations

import difflib
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from forge.safety.paths import os_path
from forge.workspace.copy_repo import iter_source_files
from forge.workspace.manifest import sha256_of
from forge.workspace.server_checks import load_checks, server_run_md
from forge.workspace.text_format import decode_text, detect_format
from forge.workspace.workspace import Workspace

FileStatus = Literal["added", "modified", "deleted"]

# Data the app wrote while Forge ran it (a SQLite file with test rows): not code, so never delivered (D-222).
RUNTIME_DATA_SUFFIXES = (".sqlite", ".sqlite3", ".db", ".db-journal", ".db-wal", ".db-shm")


class FileChange(BaseModel):
    path: str
    status: FileStatus
    sha256: str | None = None
    secret: bool = False
    binary: bool = False
    moved_from: str | None = None
    reasons: list[str] = Field(default_factory=list)


class OutputManifest(BaseModel):
    """output/MANIFEST.json — machine-readable, used by Diagnose mode (M9)."""

    generated: str
    repository: str
    files: list[FileChange]


def compute_changes(workspace: Workspace) -> list[FileChange]:
    manifest = workspace.manifest.files
    rules = workspace.ignore_rules()
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
        if entry is None or entry.sha256 != sha256_of(data):
            changes[relative] = FileChange(
                path=relative,
                status="added" if entry is None else "modified",
                sha256=sha256_of(data),
                secret=workspace.is_secret(relative),
                binary=detect_format(data).binary,
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


def build_output(workspace: Workspace) -> OutputManifest:
    changes = compute_changes(workspace)
    _clear_output(workspace)
    for change in changes:
        if change.status != "deleted" and not change.secret:
            target = workspace.jail.check(workspace.output_dir / change.path)
            os.makedirs(os_path(target.parent, force=True), exist_ok=True)
            shutil.copy2(workspace.repo_dir / change.path, os_path(target))

    report = OutputManifest(
        generated=datetime.now().isoformat(timespec="seconds"),
        repository=workspace.info.repo_path,
        files=changes,
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
        before, after = file_texts(workspace, change)
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
    for change in changes:
        lines += [f"## {change.path}", "", f"**Status:** {change.status}"]
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
            before, after = file_texts(workspace, change)
            diff = "".join(
                difflib.unified_diff(before.splitlines(True), after.splitlines(True), "before", "after")
            )
            lines += ["```diff", diff.rstrip("\n"), "```", ""]
    return "\n".join(lines) + "\n"


def build_copy_instructions(workspace: Workspace, changes: list[FileChange]) -> str:
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
            f"Forge could not run {len(checks)} DB-dependent check(s): see SERVER_RUN.md for the exact "
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
        rows.append(f"| {number} | `{change.path}` | {note} |")
    return [*rows, ""]


def _is_move_source(change: FileChange, changes: list[FileChange]) -> bool:
    return any(other.moved_from == change.path for other in changes)


def file_texts(workspace: Workspace, change: FileChange) -> tuple[str, str]:
    saved = workspace.forge_dir / "baseline" / change.path
    # Files changed outside the writer (e.g. by a formatter run in the shell) have no saved baseline;
    # the untouched original in the user's repository is then the "before".
    original = saved if saved.exists() else Path(workspace.info.repo_path) / change.path
    before = _decoded(original) if change.status != "added" else ""
    after = _decoded(workspace.repo_dir / change.path) if change.status != "deleted" else ""
    return before, after


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

"""The structure index of one repository (KL1, D-563): a record per source file with a fingerprint of its
content, kept under DebCraft Home by repository (never in the user's repository). A refresh reads every
file's bytes, which is fast, and parses only the files whose fingerprint changed, so a repository that a
hundred people change every day costs seconds, not a rebuild."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from forge.knowledge.python_file import describe as describe_python

STRUCTURE_VERSION = 2  # raise it when a record's shape changes: every file is then parsed again
STRUCTURE_FILE = "structure.json"
SKIPPED_FOLDERS = {
    ".git",
    ".forge",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    "site-packages",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".angular",
    "coverage",
}
SUFFIXES = (".py", ".sql", ".ts")
MAX_FILE_BYTES = 800_000
MAX_CHANGES_KEPT = 200
CREATE_TABLE = re.compile(r"(?im)^\s*create\s+table\s+(?:if\s+not\s+exists\s+)?\"?([A-Za-z_][\w.]*)\"?")
TS_SYMBOL = re.compile(
    r"(?m)^\s*export\s+(?:default\s+)?(?:abstract\s+)?(class|interface|function|const|enum)\s+(\w+)"
)
TS_SELECTOR = re.compile(r"selector:\s*['\"]([^'\"]+)['\"]")
TS_HTTP = re.compile(r"\.(get|post|put|delete|patch)\s*(?:<[^>(]*>)?\(\s*[`'\"]([^`'\"]+)[`'\"]")


@dataclass
class Refresh:
    """What a refresh found, for the report to the user and the model."""

    added: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    unchanged: int = 0
    seconds: float = 0.0

    @property
    def touched(self) -> list[str]:
        return [*self.added, *self.changed, *self.removed]

    def line(self) -> str:
        if not self.touched:
            return f"nothing changed ({self.unchanged} files, {self.seconds:.1f}s)"
        return (
            f"{len(self.added)} new, {len(self.changed)} changed, {len(self.removed)} removed, "
            f"{self.unchanged} unchanged ({self.seconds:.1f}s)"
        )


def fingerprint(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:20]


def module_name(root: Path, path: Path) -> tuple[str, bool]:
    """The dotted name Python code imports this file by: the chain of package folders (those with an
    __init__.py) above it, then the file. Returns (name, is a package's __init__)."""
    is_package = path.name == "__init__.py"
    parts = [] if is_package else [path.stem]
    folder = path.parent
    while folder != root and (folder / "__init__.py").is_file():
        parts.append(folder.name)
        folder = folder.parent
    return ".".join(reversed(parts)) or path.stem, is_package


def _describe(root: Path, path: Path, data: bytes) -> dict[str, Any]:
    text = data.decode("utf-8", errors="replace")
    if path.suffix == ".py":
        module, is_package = module_name(root, path)
        return {"kind": "python", **describe_python(text, module, is_package)}
    if path.suffix == ".sql":
        return {"kind": "sql", "tables": sorted(set(CREATE_TABLE.findall(text)))}
    symbols = [
        {"name": match.group(2), "kind": match.group(1), "line": text.count("\n", 0, match.start()) + 1}
        for match in TS_SYMBOL.finditer(text)
    ]
    calls = [
        {
            "method": match.group(1).upper(),
            "path": match.group(2),
            "line": text.count("\n", 0, match.start()) + 1,
        }
        for match in TS_HTTP.finditer(text)
        if "/" in match.group(2)
    ]
    selector = TS_SELECTOR.search(text)
    return {
        "kind": "ts",
        "symbols": symbols,
        "http": calls,
        "selector": selector.group(1) if selector else "",
    }


def source_files(root: Path, skip: Callable[[str], bool] | None = None) -> Iterable[tuple[str, Path]]:
    """(path relative to the root with '/', file) for every source file the index covers."""
    for folder, folders, files in os.walk(root):
        folders[:] = sorted(
            name for name in folders if name not in SKIPPED_FOLDERS and not name.endswith(".egg-info")
        )
        for name in sorted(files):
            if not name.endswith(SUFFIXES) or name.endswith((".d.ts", ".spec.ts", ".min.js")):
                continue
            path = Path(folder) / name
            relative = path.relative_to(root).as_posix()
            if skip is None or not skip(relative):
                yield relative, path


def load(store: Path) -> dict[str, Any]:
    """The stored index, or an empty one when there is none, it is unreadable or its version is old."""
    try:
        data = json.loads((store / STRUCTURE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict) or data.get("version") != STRUCTURE_VERSION:
        return {"version": STRUCTURE_VERSION, "files": {}}
    return data


def save(store: Path, structure: dict[str, Any]) -> None:
    store.mkdir(parents=True, exist_ok=True)
    target = store / STRUCTURE_FILE
    scratch = target.with_suffix(".tmp")
    scratch.write_text(json.dumps(structure, separators=(",", ":")), encoding="utf-8")
    os.replace(scratch, target)  # never a half-written index


def refresh(
    root: Path,
    store: Path,
    skip: Callable[[str], bool] | None = None,
    frozen: Iterable[str] = (),
    as_of: str = "",
    keep: bool = True,
) -> tuple[dict[str, Any], Refresh]:
    """Brings the stored index in line with the files under `root` and saves it.

    `frozen`: files this project itself has changed. The index describes the user's repository, not
    DebCraft's unfinished work on a copy of it, so their stored records are kept as they are.
    `as_of`: when the copy under `root` was taken (ISO time). A copy older than the one the stored index was
    last built from still gets a correct answer for itself, but is not saved: an old project that is reopened
    must not push the repository's index back in time.
    `keep=False`: only answer for `root`, save nothing (a project's copy, when the index was just brought up
    to date from the user's own folder)."""
    started = time.perf_counter()
    structure = load(store)
    old: dict[str, Any] = structure["files"]
    kept_as_is = set(frozen)
    new: dict[str, Any] = {}
    report = Refresh()
    for relative, path in source_files(root, skip):
        if relative in kept_as_is:
            if relative in old:
                new[relative] = old[relative]
                report.unchanged += 1
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            data = path.read_bytes()
        except OSError:
            continue
        mark = fingerprint(data)
        before = old.get(relative)
        if before is not None and before.get("fingerprint") == mark:
            new[relative] = before
            report.unchanged += 1
            continue
        new[relative] = {"fingerprint": mark, **_describe(root, path, data)}
        (report.changed if before is not None else report.added).append(relative)
    for relative in old:
        if relative not in new:
            if relative in kept_as_is:  # deleted by this project only: still part of the user's repository
                new[relative] = old[relative]
            else:
                report.removed.append(relative)
    structure["files"] = new
    structure["refreshed"] = time.strftime("%Y-%m-%d %H:%M")
    report.seconds = time.perf_counter() - started
    stored_as_of = str(structure.get("as_of", ""))
    if not keep or (as_of and stored_as_of and as_of < stored_as_of):
        return structure, report  # an older copy: answered from memory, the newer index on disk stays
    first_build = not old
    if report.touched or as_of > stored_as_of or not (store / STRUCTURE_FILE).is_file():
        structure["as_of"] = max(as_of, stored_as_of)
        if report.touched and not first_build:  # what the repository's developers changed since last time
            structure["last_changes"] = {
                "at": structure["refreshed"],
                "paths": report.touched[:MAX_CHANGES_KEPT],
                "count": len(report.touched),
            }
        save(store, structure)
    return structure, report

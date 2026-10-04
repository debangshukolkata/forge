"""Search tools (spec §9.2): glob, list_dir, grep. Paths are relative to the repository root."""

from __future__ import annotations

import asyncio
import fnmatch
import os
import re
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from pydantic import Field

from forge.safety.paths import is_within
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.workspace.copy_repo import iter_source_files
from forge.workspace.ignore import IgnoreRules
from forge.workspace.workspace import Workspace

MAX_GLOB_RESULTS = 200
MAX_LIST_ENTRIES = 500
MAX_GREP_FILE_BYTES = 5 * 1024 * 1024
SECRET_HIDDEN = "[secret file: content hidden]"


def workspace_files(workspace: Workspace, under: str = ".") -> Iterator[str]:
    """Every non-ignored file in the workspace copy, as repo-relative POSIX paths."""
    external = workspace.resolve_readable(under)
    if external is not None:
        yield from _external_files(external)
        return
    rules = workspace.ignore_rules()
    base = workspace.path_of(under) if under not in (".", "") else workspace.repo_dir
    root = _root_for(workspace, base)
    prefix = "" if base == root else base.relative_to(root).as_posix()
    if base.is_file():
        yield prefix
        return
    for child in sorted(base.iterdir()) if base.is_dir() else []:
        relative = f"{prefix}/{child.name}" if prefix else child.name
        if child.is_dir():
            if not rules.is_ignored(relative, is_dir=True):
                for path, _, is_link in iter_source_files(root, relative, rules):
                    if not is_link:
                        yield path
        elif not rules.is_ignored(relative, is_dir=False):
            yield relative


MAX_EXTERNAL_FILES = 20_000


def _external_files(base: Path) -> Iterator[str]:
    """Files of a granted folder as absolute POSIX paths (their own folder is the root for ignore rules)."""
    if base.is_file():
        yield base.as_posix()
        return
    rules = IgnoreRules(base)
    count = 0
    for directory, subdirectories, filenames in os.walk(base, followlinks=False):
        relative_dir = Path(os.path.relpath(directory, base)).as_posix().removeprefix(".").lstrip("/")
        subdirectories[:] = sorted(
            name
            for name in subdirectories
            if not rules.is_ignored(f"{relative_dir}/{name}".lstrip("/"), is_dir=True)
        )
        for name in sorted(filenames):
            relative = f"{relative_dir}/{name}".lstrip("/")
            if rules.is_ignored(relative, is_dir=False):
                continue
            yield (Path(directory) / name).as_posix()
            count += 1
            if count >= MAX_EXTERNAL_FILES:
                return


def _root_for(workspace: Workspace, path: Path) -> Path:
    """Paths are shown relative to the repository copy; Mode B's _harness/ sits beside project/, so its
    paths are relative to the workspace root (which is how path_of resolves them)."""
    if is_within(path, workspace.repo_dir):
        return workspace.repo_dir
    return workspace.root if is_within(path, workspace.root) else path  # a granted folder is its own root


class Glob(Tool):
    name = "glob"
    read_only = True
    description = (
        "Find files by glob pattern, e.g. '**/*.py' or 'backend/**/routes.py'. Newest first. "
        "Ignored folders (venv, caches, .git) are skipped."
    )

    class Args(ToolArgs):
        pattern: str
        path: str = Field(default=".", description="Folder to search in, relative to the repository root.")

    def summary(self, args: Glob.Args) -> str:
        return f"glob {args.pattern} in {args.path}"

    async def run(self, args: Glob.Args, context: ToolContext) -> ToolResult:
        workspace = context.workspace
        pattern = (
            args.pattern if args.pattern.startswith("**/") or "/" in args.pattern else f"**/{args.pattern}"
        )
        matches = [p for p in workspace_files(workspace, args.path) if _glob_match(p, pattern, args.path)]
        matches.sort(key=lambda p: workspace.path_of(p).stat().st_mtime, reverse=True)
        if not matches:
            return ToolResult(ok=True, content="No files matched.")
        shown = matches[:MAX_GLOB_RESULTS]
        more = f"\n[{len(matches) - len(shown)} more not shown]" if len(matches) > len(shown) else ""
        return ToolResult(ok=True, content="\n".join(shown) + more, meta={"count": len(matches)})


class ListDir(Tool):
    name = "list_dir"
    read_only = True
    description = "List a folder of the workspace copy (folders end with '/'). Ignored folders are hidden."

    class Args(ToolArgs):
        path: str = Field(default=".", description="Folder relative to the repository root.")

    def summary(self, args: ListDir.Args) -> str:
        return f"list {args.path}"

    async def run(self, args: ListDir.Args, context: ToolContext) -> ToolResult:
        workspace = context.workspace
        folder = workspace.path_of(args.path) if args.path not in (".", "") else workspace.repo_dir
        if not folder.is_dir():
            return ToolResult(ok=False, content=f"{args.path} is not a folder.")
        rules = workspace.ignore_rules()
        entries = []
        for child in sorted(folder.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
            relative = child.relative_to(_root_for(workspace, folder)).as_posix()
            if rules.is_ignored(relative, is_dir=child.is_dir()):
                continue
            entries.append(
                f"{child.name}/" if child.is_dir() else f"{child.name}  ({child.stat().st_size} bytes)"
            )
        shown = entries[:MAX_LIST_ENTRIES]
        return ToolResult(ok=True, content="\n".join(shown) or "(empty folder)")


class Grep(Tool):
    name = "grep"
    read_only = True
    description = (
        "Search file contents with a regular expression. output_mode: files_with_matches (default), "
        "content (matching lines with line numbers) or count. Use glob to filter files, e.g. '*.py'."
    )

    class Args(ToolArgs):
        pattern: str
        path: str = Field(default=".", description="File or folder relative to the repository root.")
        glob: str | None = Field(default=None, description="Only files matching this pattern, e.g. '*.py'.")
        output_mode: Literal["files_with_matches", "content", "count"] = "files_with_matches"
        case_insensitive: bool = False
        context_lines: int = Field(default=0, ge=0, le=10)
        head_limit: int = Field(default=100, ge=1, le=1000, description="Maximum lines/files to return.")

    def summary(self, args: Grep.Args) -> str:
        return f"grep {args.pattern!r} in {args.path}"

    async def run(self, args: Grep.Args, context: ToolContext) -> ToolResult:
        try:
            regex = re.compile(args.pattern, re.IGNORECASE if args.case_insensitive else 0)
        except re.error as error:
            return ToolResult(ok=False, content=f"Invalid regular expression: {error}")
        files = [p for p in workspace_files(context.workspace, args.path) if _file_filter(p, args.glob)]
        # Pure Python, threaded (DECISIONS D-043): ripgrep may not exist on the office laptop and
        # can't apply Forge's ignore and secret-file rules; one code path behaves the same everywhere.
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = await asyncio.gather(
                *(
                    loop.run_in_executor(pool, _search_file, context.workspace, p, regex, args.context_lines)
                    for p in files
                )
            )
        hits = [(path, lines) for path, lines in zip(files, results, strict=True) if lines]
        return ToolResult(
            ok=True,
            content=_format(hits, context.workspace, args) or "No matches.",
            meta={"files": len(hits)},
        )


def _search_file(
    workspace: Workspace, relative: str, regex: re.Pattern[str], context_lines: int
) -> list[str]:
    path = workspace.path_of(relative)
    try:
        if path.stat().st_size > MAX_GREP_FILE_BYTES:
            return []
        data = path.read_bytes()
    except OSError:
        return []
    if b"\x00" in data[:8192]:
        return []
    lines = data.decode("utf-8", errors="replace").splitlines()
    matched = [index for index, line in enumerate(lines) if regex.search(line)]
    if not matched:
        return []
    wanted: set[int] = set()
    for index in matched:
        wanted.update(range(max(0, index - context_lines), min(len(lines), index + context_lines + 1)))
    marker = set(matched)
    return [f"{i + 1}{':' if i in marker else '-'}{lines[i]}" for i in sorted(wanted)]


def _format(hits: list[tuple[str, list[str]]], workspace: Workspace, args: Grep.Args) -> str:
    if args.output_mode == "files_with_matches":
        rows = [path for path, _ in hits]
    elif args.output_mode == "count":
        rows = [f"{path}:{sum(_is_match(line) for line in lines)}" for path, lines in hits]
    else:
        rows = []
        for path, lines in hits:
            if workspace.is_secret(path):
                rows.append(f"{path}: {SECRET_HIDDEN}")
            else:
                rows.extend(f"{path}:{line}" for line in lines)
    shown = rows[: args.head_limit]
    more = (
        f"\n[{len(rows) - len(shown)} more not shown; raise head_limit or narrow the search]"
        if len(rows) > len(shown)
        else ""
    )
    return "\n".join(shown) + more


def _is_match(line: str) -> bool:
    number, _, _ = line.partition(":")
    return number.isdigit()


def _file_filter(relative: str, pattern: str | None) -> bool:
    if not pattern:
        return True
    return fnmatch.fnmatch(Path(relative).name, pattern) or fnmatch.fnmatch(relative, pattern)


def _glob_match(relative: str, pattern: str, under: str) -> bool:
    under = under.replace("\\", "/")
    base = "" if under in (".", "") else under.rstrip("/") + "/"
    candidate = relative[len(base) :] if base and relative.startswith(base) else relative
    return Path(candidate).match(pattern) or fnmatch.fnmatch(candidate, pattern.removeprefix("**/"))

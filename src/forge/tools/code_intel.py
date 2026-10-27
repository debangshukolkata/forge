"""find_definition, find_references, list_symbols: exact Python code intelligence through the `jedi` library (design doc section 3, option B).

grep is imprecise for names that several modules share, and reading whole files is slow on a large repository. jedi resolves names the way the interpreter would, in
process, with no server to run and no stored index (D-156): every call parses on demand. `jedi` is an optional dependency, imported lazily; without it each tool says
how to install it and points at code_outline and grep. Read-only: the project is the workspace folder, so results never leave it; secret files and files over 600 KB
are skipped; output is capped. Lines are 1-based and columns 1-based, as editors and grep show them."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from pydantic import Field

from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult

MAX_FILE_BYTES = 600_000
MAX_HITS = 60
CONTEXT_LINES = 3
INSTALL_HINT = (
    "Code intelligence needs the optional package jedi: run `pip install jedi` (or `pip install forge[intel]`). "
    "Until then use code_outline (structure, callers) and grep."
)


def _load_jedi() -> Any | None:
    try:
        import jedi
    except ImportError:
        return None
    return jedi


class _Located:
    """The workspace root plus the checks every result passes before it is shown."""

    def __init__(self, root: Path, context: ToolContext) -> None:
        self.root = root.resolve()
        self.context = context

    def relative(self, path: Path | None) -> str | None:
        """Workspace-relative path, or None when the file is outside the workspace, too big, or a secret."""
        if path is None:
            return None
        try:
            resolved = Path(path).resolve()
            relative = resolved.relative_to(self.root).as_posix()
            if not resolved.is_file() or resolved.stat().st_size > MAX_FILE_BYTES:
                return None
        except (OSError, ValueError):
            return None
        if self.context.workspace.is_secret(relative):
            return None
        return relative

    def line_text(self, relative: str, line: int) -> str:
        try:
            lines = (self.root / relative).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return ""
        return lines[line - 1].strip()[:200] if 0 < line <= len(lines) else ""

    def snippet(self, relative: str, line: int) -> str:
        try:
            lines = (self.root / relative).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return ""
        start = max(1, line - 1)
        end = min(len(lines), line + CONTEXT_LINES)
        return "\n".join(f"  {number}: {lines[number - 1][:200]}" for number in range(start, end + 1))


class _PositionArgs(ToolArgs):
    path: str = Field(description="The Python file, relative to the workspace.")
    line: int = Field(ge=1, description="Line of the name (1-based, as read_file shows it).")
    column: int = Field(
        ge=1, description="Column inside the name (1-based): any character of the name works."
    )


def _prepare(path_text: str, context: ToolContext) -> tuple[Any, _Located, Path] | ToolResult:
    """The jedi module, the location helper and the file; a ToolResult when something is missing."""
    jedi = _load_jedi()
    if jedi is None:
        return ToolResult(ok=False, content=INSTALL_HINT)
    workspace = context.workspace
    root = workspace.path_of(".")
    file_path = workspace.input_path(path_text) or workspace.path_of(path_text)
    located = _Located(root, context)
    if not file_path.is_file():
        return ToolResult(ok=False, content=f"{path_text} is not a file in the workspace.")
    if located.relative(file_path) is None:
        return ToolResult(
            ok=False,
            content=f"{path_text} is outside the workspace, too large (over 600 KB) or a secret file.",
        )
    return jedi, located, file_path


def _script(jedi: Any, located: _Located, file_path: Path) -> Any:
    project = jedi.Project(path=str(located.root))
    return jedi.Script(path=str(file_path), project=project)


class FindDefinition(Tool):
    name = "find_definition"
    read_only = True
    description = (
        "Where the Python name at a position is defined, resolved like the interpreter would (follows imports across files), with a few lines of context. "
        "Give path, line and column of any character of the name. More exact than grep when several modules share a name. Needs the optional package jedi. Read-only."
    )

    class Args(_PositionArgs):
        pass

    def summary(self, args: FindDefinition.Args) -> str:
        return f"{args.path}:{args.line}:{args.column}"

    async def run(self, args: FindDefinition.Args, context: ToolContext) -> ToolResult:
        prepared = _prepare(args.path, context)
        if isinstance(prepared, ToolResult):
            return prepared
        jedi, located, file_path = prepared
        try:
            names = await asyncio.to_thread(
                lambda: _script(jedi, located, file_path).goto(
                    args.line, args.column - 1, follow_imports=True
                )
            )
        except (
            Exception
        ) as error:  # jedi raises plain ValueError for positions outside the file and more for odd code
            return ToolResult(ok=False, content=f"jedi could not resolve that position: {str(error)[:200]}")
        out: list[str] = []
        for name in names[:MAX_HITS]:
            relative = located.relative(name.module_path)
            if relative is None or name.line is None:
                out.append(
                    f"{name.full_name or name.name} ({name.type}): defined outside the workspace or in a built-in module."
                )
                continue
            out.append(
                f"{relative}:{name.line}  {name.type} {name.name}\n{located.snippet(relative, name.line)}"
            )
        if not out:
            return ToolResult(
                ok=True,
                content="No definition found at that position. Check the line and column, or use grep.",
            )
        return ToolResult(ok=True, content="\n\n".join(out))


class FindReferences(Tool):
    name = "find_references"
    read_only = True
    description = (
        "Every place inside the workspace where the Python name at a position is used (definition included), as file:line with the line text. "
        "Give path, line and column of any character of the name. Skips other things with the same name. Needs the optional package jedi. Read-only."
    )

    class Args(_PositionArgs):
        pass

    def summary(self, args: FindReferences.Args) -> str:
        return f"{args.path}:{args.line}:{args.column}"

    async def run(self, args: FindReferences.Args, context: ToolContext) -> ToolResult:
        prepared = _prepare(args.path, context)
        if isinstance(prepared, ToolResult):
            return prepared
        jedi, located, file_path = prepared
        try:
            names = await asyncio.to_thread(
                lambda: _script(jedi, located, file_path).get_references(
                    args.line, args.column - 1, include_builtins=False
                )
            )
        except Exception as error:
            return ToolResult(ok=False, content=f"jedi could not resolve that position: {str(error)[:200]}")
        seen: set[tuple[str, int]] = set()
        out: list[str] = []
        capped = False
        for name in names:
            relative = located.relative(name.module_path)
            if relative is None or name.line is None or (relative, name.line) in seen:
                continue
            if len(out) >= MAX_HITS:
                capped = True
                break
            seen.add((relative, name.line))
            out.append(f"{relative}:{name.line}  {located.line_text(relative, name.line)}")
        if not out:
            return ToolResult(
                ok=True, content="No references found inside the workspace. Check the position, or use grep."
            )
        if capped:
            out.append(f"... stopped at {MAX_HITS} hits; search a narrower name with grep.")
        return ToolResult(ok=True, content=f"{len(out)} reference(s):\n" + "\n".join(out))


class ListSymbols(Tool):
    name = "list_symbols"
    read_only = True
    description = (
        "Python symbols with kind and line. Give `path` for the classes, functions and variables defined in that file (methods indented under their class), "
        "or `query` to search names across the whole workspace project. Needs the optional package jedi; for other languages use code_outline. Read-only."
    )

    class Args(ToolArgs):
        path: str = Field(default="", description="A Python file of the workspace to list.")
        query: str = Field(
            default="",
            description="A name or part of one to search across the project (used when path is empty).",
        )

    def summary(self, args: ListSymbols.Args) -> str:
        return args.path or f"search {args.query}"

    async def run(self, args: ListSymbols.Args, context: ToolContext) -> ToolResult:
        if not args.path.strip() and not args.query.strip():
            return ToolResult(
                ok=False, content="Give `path` (list one file) or `query` (search the project)."
            )
        if args.path.strip():
            return await self._file(args.path.strip(), context)
        return await self._search(args.query.strip(), context)

    async def _file(self, path_text: str, context: ToolContext) -> ToolResult:
        prepared = _prepare(path_text, context)
        if isinstance(prepared, ToolResult):
            return prepared
        jedi, located, file_path = prepared
        try:
            names = await asyncio.to_thread(
                lambda: _script(jedi, located, file_path).get_names(
                    all_scopes=True, definitions=True, references=False
                )
            )
        except Exception as error:
            return ToolResult(ok=False, content=f"jedi could not read {path_text}: {str(error)[:200]}")
        out: list[str] = []
        for name in names:
            if name.type not in {"class", "function", "statement"} or name.line is None:
                continue
            parent = name.parent()
            depth = 0
            while parent is not None and parent.type in {"class", "function"} and depth < 6:
                depth += 1
                parent = parent.parent()
            if name.type == "statement" and depth > 0:
                continue  # locals inside functions are noise; class attributes and module variables stay
            out.append(f"{'  ' * min(depth, 4)}{name.line}: {name.type} {name.name}")
            if len(out) >= MAX_HITS * 5:
                out.append("... stopped; use query for a narrower search.")
                break
        if not out:
            return ToolResult(ok=True, content=f"No symbols found in {path_text}.")
        return ToolResult(ok=True, content=f"{path_text}\n" + "\n".join(out))

    async def _search(self, query: str, context: ToolContext) -> ToolResult:
        jedi = _load_jedi()
        if jedi is None:
            return ToolResult(ok=False, content=INSTALL_HINT)
        located = _Located(context.workspace.path_of("."), context)

        def search() -> list[Any]:
            project = jedi.Project(path=str(located.root))
            found: list[Any] = []
            for name in project.search(query):
                found.append(name)
                if (
                    len(found) >= MAX_HITS * 3
                ):  # secret and oversized files are filtered below, so read a few extra
                    break
            return found

        try:
            names = await asyncio.to_thread(search)
        except Exception as error:
            return ToolResult(ok=False, content=f"jedi search failed: {str(error)[:200]}")
        out: list[str] = []
        for name in names:
            relative = located.relative(name.module_path)
            if relative is None or name.line is None:
                continue  # dependencies in a venv and built-ins are outside the workspace
            if relative.startswith((".venv/", "venv/", "node_modules/", ".forge/")):
                continue
            out.append(f"{relative}:{name.line}  {name.type} {name.full_name or name.name}")
            if len(out) >= MAX_HITS:
                out.append(f"... stopped at {MAX_HITS} hits; use a longer query.")
                break
        if not out:
            return ToolResult(ok=True, content=f"No symbols matching `{query}` in the workspace.")
        return ToolResult(ok=True, content="\n".join(out))


def code_intel_tools() -> list[Tool]:
    return [FindDefinition(), FindReferences(), ListSymbols()]

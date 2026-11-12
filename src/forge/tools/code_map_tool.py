"""`code_map`: answers about the repository from its stored structure index (KL1, D-563).

The index belongs to the repository, not to one project: it lives under DebCraft Home by repository path, so the
second project on the same repository starts with what the first one indexed. Every call first brings it up to
date (only files whose content changed are parsed again), so the model always gets the current code."""

from __future__ import annotations

import asyncio
import os
import re
import threading
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from forge.config import forge_home
from forge.knowledge.code_map import BY_NAME, CodeMap, cap
from forge.knowledge.structure import SKIPPED_FOLDERS, STRUCTURE_FILE, Refresh, fingerprint, load, refresh
from forge.knowledge.topics import all_topics, index_lines
from forge.knowledge.usage import load_usage
from forge.memory.scope import project_dir, scope_of
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.workspace.workspace import Workspace

Action = Literal[
    "overview", "find", "file", "endpoints", "endpoint", "callers", "callees", "tables", "table", "env"
]
_VIEW_LOCK = threading.RLock()
SLOW_UPDATE_SECONDS = 1.0
OVERVIEW_FOLDERS = 30
CHANGES_SHOWN = 15


def knowledge_store(workspace: Workspace) -> Path:
    """<DebCraft Home>/memory/scopes/<repository>/knowledge: shared by every project on this repository."""
    return project_dir(forge_home(), scope_of(workspace)) / "knowledge"


def live_root(workspace: Workspace) -> Path | None:
    """The user's own repository folder, when it is still where it was (it is only ever read, never written)."""
    try:
        folder = Path(workspace.info.repo_path)
        return folder if folder.is_dir() and folder.resolve() != workspace.repo_dir.resolve() else None
    except OSError:
        return None


def update_from_live(workspace: Workspace) -> Refresh | None:
    """Brings the stored index up to date from the user's own folder (D-566): what a hundred developers changed
    since last time is picked up without creating a project. None when the folder cannot be read."""
    folder = live_root(workspace)
    if folder is None:
        return None
    try:
        _, report = refresh(
            folder,
            knowledge_store(workspace),
            workspace.is_secret,
            as_of=datetime.now(UTC).isoformat(timespec="seconds"),
        )
    except OSError:
        return None
    return report


def project_view(workspace: Workspace) -> tuple[dict[str, Any], Refresh]:
    """The index as it is true for this project's copy of the repository, plus what to tell the model about
    an update. With the user's folder in reach the stored index follows that folder and the copy is only
    answered for (nothing saved); without it the copy itself keeps the index up to date. Files this project
    has changed keep their stored record: the index describes the user's repository, not unfinished work."""
    store = knowledge_store(workspace)
    changes = workspace.changes()
    own = {change.path for change in changes} | {change.from_path for change in changes if change.from_path}
    with _VIEW_LOCK:  # calls in one batch run in threads: one update at a time, the next one finds it done
        shown = Refresh()
        live = live_root(workspace)
        if live is not None and not (store / STRUCTURE_FILE).is_file():
            shown = update_from_live(workspace) or shown
        structure, report = refresh(
            workspace.repo_dir,
            store,
            workspace.is_secret,
            own,
            as_of=workspace.info.created,
            keep=live is None,
        )
    return structure, (report if live is None else shown)


async def project_view_async(workspace: Workspace) -> tuple[dict[str, Any], Refresh]:
    """`project_view` off the event loop: walking a repository must not stop the web server (KP7, D-573)."""
    return await asyncio.to_thread(project_view, workspace)


def refreshed_map(workspace: Workspace) -> tuple[CodeMap, Refresh]:
    structure, report = project_view(workspace)
    return CodeMap(structure), report


def current_marks(workspace: Workspace, structure: dict[str, Any], paths: Iterable[str]) -> dict[str, str]:
    """The fingerprint of each path as this project sees it: from the index for source files, from the file
    itself for anything else (a YAML file, a README); a missing file has none."""
    marks: dict[str, str] = {}
    for path in paths:
        record = structure["files"].get(path)
        if record is not None:
            marks[path] = record["fingerprint"]
            continue
        try:
            target = workspace.repo_dir / path
            if target.is_file() and not workspace.is_secret(path):
                marks[path] = fingerprint(target.read_bytes())
        except OSError:
            continue
    return marks


def overview(code_map: CodeMap, report: Refresh | None = None) -> str:
    """A short map of the repository: what is in which folder, how many endpoints and tables."""
    folders: dict[str, list[int]] = {}
    for path, record in code_map.files.items():
        folder = path.rsplit("/", 1)[0] if "/" in path else "."
        counts = folders.setdefault(folder, [0, 0, 0])
        counts[0] += 1
        counts[1] += len(record.get("symbols", []))
        counts[2] += len(record.get("endpoints", []))
    lines = [
        f"{len(code_map.files)} source files, {len(code_map.symbols)} Python classes and functions, "
        f"{len(code_map.endpoints())} web endpoints, {len(code_map.tables())} tables."
        + (f" Index: {report.line()}." if report is not None else "")
    ]
    ranked = sorted(folders.items(), key=lambda item: (-item[1][1], item[0]))
    for folder, (files, symbols, endpoints) in sorted(ranked[:OVERVIEW_FOLDERS]):
        routes = f", {endpoints} endpoints" if endpoints else ""
        lines.append(f"- {folder}/: {files} files, {symbols} symbols{routes}")
    if len(folders) > OVERVIEW_FOLDERS:
        lines.append(f"- ... and {len(folders) - OVERVIEW_FOLDERS} smaller folders")
    return "\n".join(lines)


def repository_map_pin(
    workspace: Workspace, live: bool = True, structure: dict[str, Any] | None = None
) -> str | None:
    """The pinned 'Codebase essentials' of a project on an existing repository: the short map, what changed in
    the repository since the map was last updated, and the index of topic notes. `live`: first bring the
    index up to date from the user's own folder (at session start). `structure`: a view the caller just made,
    so the repository is not walked again (KP3). None for an empty repository."""
    try:
        latest = update_from_live(workspace) if live else None
        report = None
        if structure is None:
            structure, report = project_view(workspace)
    except OSError:
        return None
    code_map = CodeMap(structure)
    if not code_map.files:
        return None
    parts = [
        "Map of this repository, kept between projects (ask `code_map` for details before searching: where a name "
        "is defined, an endpoint's payload, auth and tables, who calls a function):\n"
        + overview(code_map, latest or report)
    ]
    changes = load(knowledge_store(workspace)).get("last_changes")
    if changes:
        names = ", ".join(changes["paths"][:CHANGES_SHOWN])
        more = f" and {changes['count'] - CHANGES_SHOWN} more" if changes["count"] > CHANGES_SHOWN else ""
        parts.append(
            f"Changed in the repository when the map was last updated ({changes['at']}): {names}{more}."
        )
    notes = all_topics(knowledge_store(workspace))
    if notes:
        marks = current_marks(workspace, structure, {path for topic in notes for path in topic.sources})
        parts.append(
            "What is already written down about this repository (read one with knowledge_search before exploring "
            "that area again; correct it with knowledge_write when the code says otherwise):\n"
            + "\n".join(index_lines(notes, marks, usage=load_usage(knowledge_store(workspace))))
        )
    else:
        parts.append(
            "Nothing is written down about this repository yet: record what you work out with knowledge_write, "
            "so the next project does not have to work it out again."
        )
    return "\n\n".join(parts)


class CodeMapTool(Tool):
    name = "code_map"
    read_only = True
    description = (
        "The map of this repository, kept between projects and brought up to date on every call. Ask it BEFORE "
        "searching or reading around. action: `overview` (folders, counts); `find` (query = a class or function "
        "name, or part of one: where it is defined, with its signature); `file` (query = a path: what the file "
        "holds); `endpoints` (every web endpoint with its full path, handler and auth; query filters by text); "
        "`endpoint` (query = a path or part of it: the payload it needs with its fields, the auth check and the "
        "environment names that check reads, the tables it reaches and through which calls); `callers` and "
        "`callees` (query = a function or Class.method: who calls it, what it calls, across files); `tables` "
        "(every table and where it is declared); `table` (query = a table name: its model and fields, the code "
        "that touches it, the endpoints that reach it); `env` (every environment variable the code reads, where, "
        "whether the code has a default, and whether the project's env files set it: names only, never values; use "
        "it first when an app does not start or says its configuration is wrong). Links marked 'by name' are likely, not proven: read the code before relying on one."
    )

    class Args(ToolArgs):
        action: Action
        query: str = ""

    def summary(self, args: CodeMapTool.Args) -> str:
        return f"code_map {args.action} {args.query}".strip()

    async def run(self, args: CodeMapTool.Args, context: ToolContext) -> ToolResult:
        if context.workspace.mode_b:
            return ToolResult(
                ok=False, content="code_map describes an existing repository; this project has none."
            )
        structure, report = await project_view_async(context.workspace)
        code_map = CodeMap(structure)
        query = args.query.strip()
        if args.action != "overview" and args.action not in ("endpoints", "tables", "env") and not query:
            return ToolResult(ok=False, content=f"`{args.action}` needs a `query`.")
        if args.action == "env":
            lines = settings_report(context.workspace, code_map, query)
        else:
            lines = getattr(self, f"_{args.action}")(code_map, query)
        slow = report.seconds >= SLOW_UPDATE_SECONDS  # a slow update must be visible, not guessed at
        note = f"\n\n[index updated: {report.line()}]" if report.touched or slow else ""
        return ToolResult(ok=True, content=(cap(lines) if lines else f"Nothing found for {query!r}.") + note)

    def _overview(self, code_map: CodeMap, query: str) -> list[str]:
        return overview(code_map).split("\n")

    def _find(self, code_map: CodeMap, query: str) -> list[str]:
        return [_symbol_line(code_map, key) for key in code_map.named(query)]

    def _file(self, code_map: CodeMap, query: str) -> list[str]:
        wanted = query.replace("\\", "/").strip("/")
        paths = [path for path in code_map.files if path == wanted] or [
            path for path in code_map.files if path.endswith(wanted) or wanted in path
        ]
        if len(paths) != 1:
            return sorted(paths)
        record = code_map.files[paths[0]]
        lines = [f"{paths[0]}" + (f": {record['doc']}" if record.get("doc") else "")]
        for symbol in record.get("symbols", []):
            detail = symbol.get("signature") or (
                f"({', '.join(symbol['bases'])})" if symbol.get("bases") else ""
            )
            lines.append(f"  {symbol['line']}: {symbol['kind']} {symbol['name']}{detail}")
        lines += [f"  table: {table}" for table in record.get("tables", [])]
        lines += [
            f"  calls the API: {call['method']} {call['path']} (line {call['line']})"
            for call in record.get("http", [])
        ]
        return lines

    def _endpoints(self, code_map: CodeMap, query: str) -> list[str]:
        lines = []
        for endpoint in code_map.endpoints():
            auth = f" [auth: {', '.join(endpoint['auth'])}]" if endpoint["auth"] else ""
            line = (
                f"{endpoint['method']} {endpoint['full_path']} -> {endpoint['handler']} "
                f"({endpoint['file']}:{endpoint['line']}){auth}"
            )
            if query.lower() in line.lower():
                lines.append(line)
        return lines

    def _endpoint(self, code_map: CodeMap, query: str) -> list[str]:
        matches = [
            endpoint
            for endpoint in code_map.endpoints()
            if query.lower() in f"{endpoint['method']} {endpoint['full_path']} {endpoint['handler']}".lower()
        ]
        if len(matches) > 4:
            return [f"{len(matches)} endpoints match; narrow the query:", *self._endpoints(code_map, query)]
        lines: list[str] = []
        for endpoint in matches:
            lines.append(
                f"{endpoint['method']} {endpoint['full_path']} -> {endpoint['handler']} "
                f"({endpoint['file']}:{endpoint['line']})"
                + (f": {endpoint['doc']}" if endpoint["doc"] else "")
            )
            lines += [f"  needs: {line}" for line in code_map.payload(endpoint)] or [
                "  needs: no body or parameters found"
            ]
            if endpoint["response"]:
                lines.append(f"  returns: {endpoint['response']}")
            lines += [f"  auth: {line}" for line in code_map.auth_of(endpoint)] or [
                "  auth: none found on the handler (a check on the whole router or in middleware is not seen)"
            ]
            for table, (chain, sure) in code_map.tables_of(endpoint["key"]).items():
                lines.append(f"  table {table}: {chain}" + (" (by name)" if sure == BY_NAME else ""))
        return lines

    def _callers(self, code_map: CodeMap, query: str) -> list[str]:
        return self._links(code_map, query, code_map.callers(), "is called or used by")

    def _callees(self, code_map: CodeMap, query: str) -> list[str]:
        return self._links(code_map, query, code_map.edges(), "calls or uses")

    def _links(self, code_map: CodeMap, query: str, links: dict[str, Any], verb: str) -> list[str]:
        keys = code_map.named(query)
        if len(keys) > 3:
            return [f"{len(keys)} symbols match; name one exactly:"] + [
                _symbol_line(code_map, key) for key in keys
            ]
        lines: list[str] = []
        for key in keys:
            lines.append(f"{key.partition(':')[2]} ({code_map.where(key)}) {verb}:")
            found = links.get(key, [])
            lines += [
                f"  {other.partition(':')[2]} ({code_map.where(other)}) [{kind}"
                + (", by name]" if sure == BY_NAME else "]")
                for other, kind, sure in found
            ] or ["  nothing found in the repository"]
        return lines

    def _tables(self, code_map: CodeMap, query: str) -> list[str]:
        return [
            f"{table}: {'; '.join(places[:3])}" + (f"; and {len(places) - 3} more" if len(places) > 3 else "")
            for table, places in code_map.tables().items()
            if query.lower() in table.lower()
        ]

    def _table(self, code_map: CodeMap, query: str) -> list[str]:
        tables = code_map.tables()
        names = [name for name in tables if name.lower() == query.lower()] or [
            name for name in tables if query.lower() in name.lower()
        ]
        if len(names) != 1:
            return [f"{name}: {tables[name][0]}" for name in names]
        table = names[0]
        lines = [f"table {table}:"] + [f"  {place}" for place in tables[table]]
        for key, (_, symbol) in code_map.symbols.items():
            if symbol.get("table") == table and symbol.get("fields"):
                fields = ", ".join(f"{name}: {kind}" for name, kind in symbol["fields"])
                lines.append(f"  fields ({key.partition(':')[2]}): {fields}")
        reaching = [
            f"  {endpoint['method']} {endpoint['full_path']} ({chain})"
            for endpoint in code_map.endpoints()
            for name, (chain, _) in code_map.tables_of(endpoint["key"]).items()
            if name == table
        ]
        return lines + (["endpoints that reach it:", *reaching] if reaching else [])

    def _env(self, code_map: CodeMap, query: str) -> list[str]:
        return settings_report(None, code_map, query)


ENV_KEY = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_.-]*)\s*[=:]\s*(.*)$")
ENV_FILE_DEPTH = 3


def env_files(workspace: Workspace) -> dict[str, dict[str, bool]]:
    """The project's env files (`.env`, `.env.local`, `app.env` ...) near the top of the repository:
    path -> {key: has a value}. Only whether a value is there is looked at, never the value itself."""
    found: dict[str, dict[str, bool]] = {}
    root = workspace.repo_dir
    candidates: list[Path] = []
    for folder, folders, names in os.walk(root):  # pruned: never descends into libraries or deep trees
        depth = len(Path(folder).relative_to(root).parts)
        folders[:] = (
            [] if depth + 1 >= ENV_FILE_DEPTH else sorted(f for f in folders if f not in SKIPPED_FOLDERS)
        )
        candidates += [
            Path(folder) / name
            for name in names
            if name == ".env" or name.startswith(".env.") or name.endswith(".env")
        ]
    for path in sorted(candidates):
        relative = path.relative_to(root)
        name = path.name
        if name.endswith((".example", ".sample", ".template", ".dist")):
            continue  # a list of names for people to fill in, not what the app reads
        keys: dict[str, bool] = {}
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                match = ENV_KEY.match(line)
                if match and not line.lstrip().startswith("#"):
                    keys[match.group(1)] = bool(match.group(2).strip().strip("\"'"))
        except OSError:
            continue
        found[relative.as_posix()] = keys
    return found


def settings_report(workspace: Workspace | None, code_map: CodeMap, query: str = "") -> list[str]:
    """Each environment name the code reads: where, whether the code has a default for it, and whether the
    project's env files set it. A name read without a default that no env file sets is the usual reason an
    app copied from somewhere else does not start."""
    reads: dict[str, list[tuple[str, int, bool]]] = {}
    for path, record in code_map.files.items():
        required = set(record.get("env_required", []))
        for name in record.get("env", []):
            if query.lower() in name.lower():
                line = int(record.get("env_lines", {}).get(name, 0))
                reads.setdefault(name, []).append((path, line, name in required))
    files = env_files(workspace) if workspace is not None else {}
    lines = [f"env file {path}: {', '.join(keys) or 'no keys'}" for path, keys in files.items()]
    if workspace is not None and not files:
        lines.append("No env file found near the top of the project.")
    missing: list[str] = []
    for name, places in sorted(reads.items()):
        where = ", ".join(f"{path}:{line}" for path, line, _ in places[:3])
        needed = any(required for _, _, required in places)
        state = ""
        if workspace is not None:
            holders = [path for path, keys in files.items() if name in keys]
            if not holders:
                state = "; NOT SET in any env file"
                if needed:
                    missing.append(name)
            elif not any(files[path][name] for path in holders):
                state = f"; set but EMPTY in {holders[0]}"
                if needed:
                    missing.append(name)
            else:
                state = f"; set in {holders[0]}"
        lines.append(f"{name}: read in {where} ({'no default' if needed else 'has a default'}){state}")
    if missing:
        lines.insert(
            0,
            "Read without a default and not set (the code cannot work until these have values): "
            + ", ".join(missing)
            + ". Something outside the env files may set them (the shell, a start script, a secrets store): check before you say so.",
        )
    return lines


def _symbol_line(code_map: CodeMap, key: str) -> str:
    path, symbol = code_map.symbols[key]
    detail = symbol.get("signature") or (f"({', '.join(symbol['bases'])})" if symbol.get("bases") else "")
    doc = f"  # {symbol['doc']}" if symbol.get("doc") else ""
    return f"{path}:{symbol['line']}: {symbol['kind']} {symbol['name']}{detail}{doc}"

"""Answers from the structure index (KL1, D-563): where a name is defined, who calls whom across files,
every web endpoint with its full path, payload, auth and the tables it reaches, and the tables themselves.

Links are resolved from imports, so most are exact. A call on an object whose type is not known statically
(`repo.save()` where `repo` is a parameter) is linked only when one function in the repository has that name,
and such a link is labelled "by name": the reader must be able to tell a proven link from a likely one."""

from __future__ import annotations

import re
from collections import deque
from typing import Any

MODEL_BASES = ("BaseModel", "Schema", "SQLModel", "BaseSettings", "TypedDict")
FRAMEWORK_TYPES = {"Request", "Response", "WebSocket", "BackgroundTasks", "HTTPConnection"}
COMMON_NAMES = {
    "get",
    "set",
    "run",
    "add",
    "post",
    "put",
    "delete",
    "save",
    "load",
    "close",
    "open",
    "read",
    "write",
}
HOPS = 8  # how far a trace follows calls from an endpoint's handler
MAX_VISITED = 600
MAX_LINES = 60
EXACT, BY_NAME = "exact", "by name"


def _join(*parts: str) -> str:
    path = "/".join(part.strip("/") for part in parts if part and part.strip("/"))
    return "/" + path


class CodeMap:
    def __init__(self, structure: dict[str, Any]) -> None:
        self.files: dict[str, Any] = {
            path: record for path, record in structure.get("files", {}).items() if "error" not in record
        }
        self.broken = [path for path, record in structure.get("files", {}).items() if "error" in record]
        self.modules: dict[str, str] = {}
        self.symbols: dict[str, tuple[str, dict[str, Any]]] = {}
        self.by_name: dict[str, list[str]] = {}
        for path, record in self.files.items():
            if record.get("kind") != "python":
                continue
            self.modules[record["module"]] = path
            for symbol in record["symbols"]:
                key = f"{record['module']}:{symbol['name']}"
                self.symbols[key] = (path, symbol)
                self.by_name.setdefault(symbol["name"].rsplit(".", 1)[-1], []).append(key)
        self._edges: dict[str, list[tuple[str, str, str]]] | None = None
        self._callers: dict[str, list[tuple[str, str, str]]] | None = None

    # --- resolving names ---

    def _dotted(self, target: str, depth: int = 0) -> str | None:
        """The symbol a fully dotted name stands for, following re-exports through package __init__ files."""
        parts = target.split(".")
        for size in range(len(parts), 0, -1):
            module = ".".join(parts[:size])
            if module not in self.modules:
                continue
            rest = parts[size:]
            if not rest:
                return None
            for length in range(len(rest), 0, -1):
                key = f"{module}:{'.'.join(rest[:length])}"
                if key in self.symbols:
                    return key
            alias = self.files[self.modules[module]]["imports"].get(rest[0])
            if alias and depth < 6:
                return self._dotted(".".join([alias, *rest[1:]]), depth + 1)
            return None
        return None

    def _method(self, class_key: str, name: str, depth: int = 0) -> str | None:
        """`name` on a class or, failing that, on the first base class that has it."""
        module, _, class_name = class_key.partition(":")
        if (key := f"{module}:{class_name}.{name}") in self.symbols:
            return key
        entry = self.symbols.get(class_key)
        if entry is None or depth > 5:
            return None
        for base in entry[1].get("bases", []):
            resolved = self.resolve(base, entry[0], "")
            if resolved and (found := self._method(resolved[0], name, depth + 1)):
                return found
        return None

    def resolve(self, name: str, path: str, owner: str) -> tuple[str, str] | None:
        """(symbol key, 'exact' or 'by name') for a name used in `path` inside the symbol `owner`."""
        record = self.files[path]
        module = record["module"]
        parts = name.split(".")
        root = parts[0]
        if root in ("self", "cls") and len(parts) > 1:
            class_name = owner.rsplit(".", 1)[0] if "." in owner else ""
            found = self._method(f"{module}:{class_name}", parts[1]) if class_name else None
            return (found, EXACT) if found else self._unique(parts[-1])
        scopes = [owner.rsplit(".", count)[0] + "." for count in range(1, owner.count(".") + 1)] + [""]
        for scope in scopes:  # a function defined inside the calling function, then the module's own names
            for length in range(len(parts), 0, -1):
                key = f"{module}:{scope}{'.'.join(parts[:length])}"
                if key in self.symbols:
                    if length < len(parts) and self.symbols[key][1]["kind"] == "class":
                        return (self._method(key, parts[length]) or key, EXACT)
                    return key, EXACT
        if root in record["imports"]:
            found = self._dotted(".".join([record["imports"][root], *parts[1:]]))
            if found and self.symbols[found][1]["kind"] == "class" and not found.endswith("." + parts[-1]):
                found = self._method(found, parts[-1]) or found
            return (found, EXACT) if found else None
        return self._unique(parts[-1]) if len(parts) > 1 else None

    def _unique(self, last: str) -> tuple[str, str] | None:
        matches = self.by_name.get(last, [])
        if len(matches) == 1 and len(last) > 3 and last not in COMMON_NAMES and not last.startswith("__"):
            return matches[0], BY_NAME
        return None

    def edges(self) -> dict[str, list[tuple[str, str, str]]]:
        """symbol -> [(symbol it calls or uses, 'calls' or 'uses', 'exact' or 'by name')]."""
        if self._edges is None:
            self._edges = {}
            self._callers = {}
            for key, (path, symbol) in self.symbols.items():
                seen: set[str] = set()
                for kind in ("calls", "refs"):
                    for name in symbol.get(kind, []):
                        resolved = self.resolve(name, path, symbol["name"])
                        if resolved is None or resolved[0] == key or resolved[0] in seen:
                            continue
                        seen.add(resolved[0])
                        verb = "calls" if kind == "calls" else "uses"
                        self._edges.setdefault(key, []).append((resolved[0], verb, resolved[1]))
                        self._callers.setdefault(resolved[0], []).append((key, verb, resolved[1]))
        return self._edges

    def callers(self) -> dict[str, list[tuple[str, str, str]]]:
        self.edges()
        assert self._callers is not None
        return self._callers

    def where(self, key: str) -> str:
        path, symbol = self.symbols[key]
        return f"{path}:{symbol['line']}"

    def named(self, name: str) -> list[str]:
        """Symbol keys for what the model typed: a key, a dotted name, `Class.method` or a bare name."""
        wanted = name.strip().replace("::", ":")
        if wanted in self.symbols:
            return [wanted]
        if found := self._dotted(wanted):
            return [found]
        tail = wanted.replace(":", ".")
        exact = [key for key in self.symbols if key.endswith((":" + tail, "." + tail))]
        return exact or sorted(key for key in self.symbols if tail.lower() in key.lower())

    # --- endpoints ---

    def _variable(self, name: str, path: str, depth: int = 0) -> str | None:
        """`module:variable` for a router or blueprint variable named in `path`, following imports."""
        record = self.files[path]
        if name in record.get("prefixes", {}):
            return f"{record['module']}:{name}"
        parts = (record["imports"].get(name.split(".")[0], "") + name[len(name.split(".")[0]) :]).split(".")
        if not parts[0]:
            return None
        for size in range(len(parts) - 1, 0, -1):
            module = ".".join(parts[:size])
            if module in self.modules and depth < 6:
                return self._variable(".".join(parts[size:]), self.modules[module], depth + 1)
        return None

    def _prefix(self, variable: str, seen: frozenset[str] = frozenset()) -> str:
        """The path in front of a router's own routes: where it is mounted, then its own prefix."""
        module, _, name = variable.partition(":")
        own = str(self.files[self.modules[module]].get("prefixes", {}).get(name, ""))
        if variable in seen:
            return own
        for path, record in self.files.items():
            for mount in record.get("mounts", []):
                if self._variable(mount["target"], path) != variable:
                    continue
                parent = self._variable(mount["onto"], path)
                above = self._prefix(parent, seen | {variable}) if parent else ""
                return _join(above, mount["prefix"], own)
        return own

    def endpoints(self) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        for path, record in self.files.items():
            for endpoint in record.get("endpoints", []):
                variable = self._variable(endpoint["owner"], path)
                prefix = self._prefix(variable) if variable else ""
                found.append(
                    {
                        **endpoint,
                        "file": path,
                        "full_path": _join(prefix, endpoint["path"]),
                        "key": f"{record['module']}:{endpoint['handler']}",
                    }
                )
        return sorted(found, key=lambda item: (item["full_path"], item["method"]))

    def _is_model(self, key: str, depth: int = 0) -> bool:
        path, symbol = self.symbols[key]
        for base in symbol.get("bases", []):
            if base.rsplit(".", 1)[-1] in MODEL_BASES:
                return True
            resolved = self.resolve(base, path, "")
            if resolved and depth < 5 and self._is_model(resolved[0], depth + 1):
                return True
        return False

    def payload(self, endpoint: dict[str, Any]) -> list[str]:
        """What the caller must send: the schema or model with its fields, plain parameters, request keys."""
        lines: list[str] = []
        path = endpoint["file"]
        if endpoint["payload"]:
            name, _, location = endpoint["payload"].partition(" ")
            lines += self._model_lines(name, path, f"schema {location}".strip())
        for param in endpoint["params"]:
            if param["default"].startswith(("Depends(", "Security(")) or "Depends(" in param["annotation"]:
                continue
            if param["annotation"].rsplit(".", 1)[-1] in FRAMEWORK_TYPES:
                continue  # the framework passes these in; the caller does not send them
            models = [
                name
                for name in re.findall(r"[A-Za-z_][\w.]*", param["annotation"])
                if (resolved := self.resolve(name, path, endpoint["handler"]))
                and self.symbols[resolved[0]][1]["kind"] == "class"
                and self._is_model(resolved[0])
            ]
            if models:
                lines += self._model_lines(models[0], path, f"body `{param['name']}`")
            elif not endpoint["payload"]:
                default = f" = {param['default']}" if param["default"] else ""
                lines.append(f"parameter {param['name']}: {param['annotation'] or 'untyped'}{default}")
        if endpoint["payload_keys"]:
            lines.append("keys read from the request: " + ", ".join(endpoint["payload_keys"]))
        return lines

    def _model_lines(self, name: str, path: str, label: str) -> list[str]:
        resolved = self.resolve(name, path, "")
        if resolved is None:
            return [f"{label}: {name} (defined outside the repository)"]
        _, symbol = self.symbols[resolved[0]]
        fields = (
            ", ".join(f"{field}: {kind}" for field, kind in symbol.get("fields", [])) or "no fields found"
        )
        return [f"{label}: {name} ({self.where(resolved[0])}): {fields}"]

    def reach(self, start: str) -> dict[str, tuple[int, str | None, str]]:
        """Every symbol reachable from `start` by calls and uses: key -> (hops, the symbol before it, how sure)."""
        seen: dict[str, tuple[int, str | None, str]] = {start: (0, None, EXACT)}
        queue = deque([start])
        edges = self.edges()
        while queue and len(seen) < MAX_VISITED:
            current = queue.popleft()
            hops, _, sure = seen[current]
            if hops >= HOPS:
                continue
            for target, _, how in edges.get(current, []):
                if target not in seen:
                    seen[target] = (hops + 1, current, BY_NAME if BY_NAME in (how, sure) else EXACT)
                    queue.append(target)
        return seen

    def chain(self, reached: dict[str, tuple[int, str | None, str]], key: str) -> str:
        names: list[str] = []
        current: str | None = key
        while current is not None:
            names.append(current.partition(":")[2])
            current = reached[current][1]
        return " -> ".join(reversed(names))

    def tables_of(self, start: str) -> dict[str, tuple[str, str]]:
        """table -> (the call chain that reaches it, how sure) for everything `start` reaches."""
        if start not in self.symbols:
            return {}
        reached = self.reach(start)
        found: dict[str, tuple[int, str, str]] = {}
        for key, (hops, _, sure) in reached.items():
            symbol = self.symbols[key][1]
            names = list(symbol.get("sql", [])) + ([symbol["table"]] if symbol.get("table") else [])
            for table in names:
                if table not in found or hops < found[table][0]:
                    found[table] = (hops, self.chain(reached, key), sure)
        return {table: (chain, sure) for table, (_, chain, sure) in sorted(found.items())}

    def auth_of(self, endpoint: dict[str, Any]) -> list[str]:
        """Each auth check on the endpoint, where it is defined and which environment names it reads."""
        lines: list[str] = []
        for mark in endpoint["auth"]:
            inner = re.search(r"\(([\w.]+)", mark)
            name = inner.group(1) if inner else mark
            resolved = self.resolve(name, endpoint["file"], endpoint["handler"])
            if resolved is None:
                lines.append(f"{mark} (defined outside the repository)")
                continue
            reached = self.reach(resolved[0])
            env = sorted({name for key in reached for name in self.symbols[key][1].get("env", [])})
            reads = f"; reads environment: {', '.join(env)}" if env else ""
            lines.append(f"{mark} ({self.where(resolved[0])}){reads}")
        return lines

    # --- tables ---

    def tables(self) -> dict[str, list[str]]:
        """table -> where it is declared (model classes, SQL files, SQL text in functions)."""
        found: dict[str, list[str]] = {}
        for path, record in self.files.items():
            if record.get("kind") == "sql":
                for table in record["tables"]:
                    found.setdefault(table, []).append(f"created in {path}")
        for key, (path, symbol) in self.symbols.items():
            if symbol.get("table"):
                found.setdefault(symbol["table"], []).insert(
                    0, f"model {symbol['name']} ({path}:{symbol['line']})"
                )
            for table in symbol.get("sql", []):
                found.setdefault(table, []).append(
                    f"SQL in {key.partition(':')[2]} ({path}:{symbol['line']})"
                )
        return dict(sorted(found.items()))


def cap(lines: list[str], limit: int = MAX_LINES) -> str:
    if len(lines) <= limit:
        return "\n".join(lines)
    return "\n".join(lines[:limit]) + f"\n... {len(lines) - limit} more (narrow the question)"

"""What one Python file declares, read with `ast` (no model, nothing run): symbols with signatures, the names
each function calls and uses, web endpoints (FastAPI and Flask), tables, SQL text and environment variable
names. The result is a plain dict so it can be stored as JSON and compared between runs (KL1, D-563)."""

from __future__ import annotations

import ast
import re
from collections.abc import Sequence
from typing import Any

HTTP_VERBS = {"get", "post", "put", "delete", "patch", "head", "options", "websocket"}
AUTH_WORDS = re.compile(
    r"(?i)(jwt|login|auth|token|permission|role_required|secure|protected|current_user|api_key|oauth|verify)"
)
# A string counts as SQL only when it has a statement's shape ("select ... from", "update x set"), not just a
# keyword: "Update the node from memory" in a message is not SQL.
SQL_VERB = re.compile(
    r"(?is)\b(select\s.+?\sfrom\s|insert\s+into\s|update\s+[\w.\"]+\s+set\s|delete\s+from\s"
    r"|create\s+table\s|alter\s+table\s|merge\s+into\s)"
)
SQL_TABLE = re.compile(
    r"(?i)\b(?:from|join|into|update|table(?:\s+if\s+not\s+exists)?)\s+\"?([A-Za-z_][\w.]*)\"?"
)
SQL_NOISE = {"select", "set", "values", "where", "only", "lateral", "unnest", "dual", "if", "exists"}
ROUTER_MAKERS = {"APIRouter": "prefix", "Blueprint": "url_prefix", "FastAPI": "root_path"}
MOUNT_CALLS = {"include_router": "prefix", "register_blueprint": "url_prefix"}
MAX_FIELDS = 40
MAX_NAMES = 120


def dotted(node: ast.AST | None) -> str:
    """`a.b.c` for a name or attribute chain (a call in the chain is passed through); '' for anything else."""
    parts: list[str] = []
    while True:
        if isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        elif isinstance(node, ast.Call):
            node = node.func
        elif isinstance(node, ast.Name):
            parts.append(node.id)
            return ".".join(reversed(parts))
        else:
            return ""


def _text(node: ast.AST | None, limit: int = 80) -> str:
    if node is None:
        return ""
    try:
        text = " ".join(ast.unparse(node).split())
    except Exception:  # an unusual node must not stop the file from being indexed
        return ""
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _string(node: ast.AST | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _keyword(call: ast.Call, name: str) -> ast.AST | None:
    return next((keyword.value for keyword in call.keywords if keyword.arg == name), None)


def _strings(node: ast.AST | None) -> list[str]:
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return [value for item in node.elts if (value := _string(item)) is not None]
    return [value] if (value := _string(node)) is not None else []


def module_imports(tree: ast.Module, module: str, is_package: bool) -> dict[str, str]:
    """Local name -> the dotted thing it stands for (`from a.b import c as d` gives d -> a.b.c)."""
    package = module if is_package else module.rpartition(".")[0]
    found: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found[alias.asname or alias.name.split(".")[0]] = (
                    alias.name if alias.asname else alias.name.split(".")[0]
                )
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = package.split(".") if package else []
                parts = parts[: len(parts) - (node.level - 1)] if node.level > 1 else parts
                base = ".".join([*parts, base] if base else parts)
            for alias in node.names:
                if alias.name != "*":
                    found[alias.asname or alias.name] = f"{base}.{alias.name}" if base else alias.name
    return found


class _Body(ast.NodeVisitor):
    """The names one function body calls and uses, its SQL tables, request keys and environment names.
    Nested functions and classes are separate symbols, so they are not entered."""

    def __init__(self, known_roots: set[str]) -> None:
        self.known = known_roots
        self.calls: dict[str, None] = {}
        self.refs: dict[str, None] = {}
        self.sql: dict[str, None] = {}
        self.env: dict[str, None] = {}
        self.payload_keys: dict[str, None] = {}
        self._payload_names: set[str] = set()
        self._depth = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._enter(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._enter(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._enter(node)

    def _enter(self, node: ast.AST) -> None:
        if self._depth == 0:
            self._depth = 1
            self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = dotted(node.func)
        if name:
            self.calls[name] = None
            tail = name.rsplit(".", 1)[-1]
            first = _string(node.args[0]) if node.args else None
            if first and (name in ("os.getenv", "getenv") or name.endswith("environ.get")):
                self.env[first] = None
            if first and tail == "get" and self._is_payload(node.func):
                self.payload_keys[first] = None
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        source = dotted(node.value)
        if source in ("request.get_json", "request.json", "request.form", "request.args"):
            self._payload_names.update(target.id for target in node.targets if isinstance(target, ast.Name))
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        key = _string(node.slice)
        if key and dotted(node.value).endswith("environ"):
            self.env[key] = None
        elif key and self._is_payload(node):
            self.payload_keys[key] = None
        self.generic_visit(node)

    def _is_payload(self, node: ast.AST) -> bool:
        value = getattr(node, "value", None)
        name = dotted(value)
        return name in ("request.json", "request.form", "request.args", "request.get_json") or (
            isinstance(value, ast.Name) and value.id in self._payload_names
        )

    def visit_Attribute(self, node: ast.Attribute) -> None:
        name = dotted(node)
        if name and name.split(".")[0] in self.known:
            self.refs[name] = None
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load) and node.id in self.known:
            self.refs[node.id] = None

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and len(node.value) > 12 and SQL_VERB.search(node.value):
            for table in SQL_TABLE.findall(node.value):
                if table.lower() not in SQL_NOISE:
                    self.sql[table.strip('"')] = None


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    returns = f" -> {_text(node.returns, 60)}" if node.returns else ""
    return f"({_text(node.args, 200)}){returns}"


def _params(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[dict[str, str]]:
    arguments = [*node.args.posonlyargs, *node.args.args]
    defaults: list[ast.AST | None] = [None] * (len(arguments) - len(node.args.defaults)) + list(
        node.args.defaults
    )
    pairs = list(zip(arguments, defaults, strict=True)) + list(
        zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True)
    )
    return [
        {"name": argument.arg, "annotation": _text(argument.annotation, 100), "default": _text(default, 100)}
        for argument, default in pairs
        if argument.arg not in ("self", "cls")
    ]


def _class_fields(node: ast.ClassDef) -> tuple[list[list[str]], str]:
    """(fields as [name, type or maker], table name) of a model, schema or settings class."""
    fields: list[list[str]] = []
    table = ""
    for item in node.body:
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            fields.append([item.target.id, _text(item.annotation, 60)])
        elif (
            isinstance(item, ast.Assign) and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name)
        ):
            name = item.targets[0].id
            if name == "__tablename__":
                table = _string(item.value) or ""
            elif isinstance(item.value, ast.Call) and not name.startswith("_"):
                fields.append([name, _text(item.value, 60)])
    return fields[:MAX_FIELDS], table


def _route(decorator: ast.AST) -> tuple[str, str, list[str]] | None:
    """(owner variable, path, HTTP methods) when the decorator declares a route; methods [] = decided by the class."""
    if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
        return None
    verb = decorator.func.attr
    path = _string(decorator.args[0]) if decorator.args else _string(_keyword(decorator, "path"))
    owner = dotted(decorator.func.value)
    if path is None or not owner:
        return None
    if verb in HTTP_VERBS:
        return owner, path, [verb.upper()]
    if verb in ("route", "api_route"):
        return owner, path, [method.upper() for method in _strings(_keyword(decorator, "methods"))]
    return None


def _auth_marks(decorators: Sequence[ast.AST], params: list[dict[str, str]]) -> list[str]:
    marks = [name for item in decorators if (name := dotted(item)) and AUTH_WORDS.search(name)]
    for param in params:
        default = param["default"]
        if default.startswith(("Depends(", "Security(")) and AUTH_WORDS.search(default):
            marks.append(default)
        elif AUTH_WORDS.search(param["annotation"]) and "Depends" in param["annotation"]:
            marks.append(param["annotation"])
    return marks


def _smorest(decorators: Sequence[ast.AST]) -> tuple[str, str]:
    """(payload schema with its location, response schema) from flask-smorest decorators."""
    payload = response = ""
    for item in decorators:
        if not isinstance(item, ast.Call) or not isinstance(item.func, ast.Attribute) or not item.args:
            continue
        if item.func.attr == "arguments":
            location = _string(_keyword(item, "location")) or "json"
            payload = f"{dotted(item.args[0])} ({location})"
        elif item.func.attr == "response" and len(item.args) > 1:
            response = dotted(item.args[1])
    return payload, response


class _File:
    def __init__(self, tree: ast.Module, module: str, is_package: bool) -> None:
        self.imports = module_imports(tree, module, is_package)
        top = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }
        assigned = {
            target.id
            for node in tree.body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        self.known = set(self.imports) | top | assigned | {"self", "cls"}
        self.symbols: list[dict[str, Any]] = []
        self.endpoints: list[dict[str, Any]] = []
        self.prefixes: dict[str, str] = {}
        self.mounts: list[dict[str, str]] = []
        self.tables: dict[str, None] = {}
        self.env: dict[str, None] = {}
        self._walk(tree.body, "", None)
        self._module_level(tree)

    def _walk(
        self, body: list[ast.stmt], prefix: str, class_route: tuple[str, str] | None, in_class: bool = False
    ) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                self._class(node, prefix)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._function(node, prefix, class_route, in_class)

    def _class(self, node: ast.ClassDef, prefix: str) -> None:
        name = prefix + node.name
        fields, table = _class_fields(node)
        if table:
            self.tables[table] = None
        self.symbols.append(
            {
                "name": name,
                "kind": "class",
                "line": node.lineno,
                "end": node.end_lineno or node.lineno,
                "bases": [base for item in node.bases if (base := dotted(item))],
                "decorators": [text for item in node.decorator_list if (text := dotted(item))],
                "doc": (ast.get_docstring(node) or "").strip().split("\n")[0][:160],
                "fields": fields,
                "table": table,
            }
        )
        routes = [route for item in node.decorator_list if (route := _route(item)) is not None]
        self._walk(node.body, name + ".", (routes[0][0], routes[0][1]) if routes else None, in_class=True)

    def _function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        prefix: str,
        class_route: tuple[str, str] | None,
        in_class: bool,
    ) -> None:
        name = prefix + node.name
        body = _Body(self.known)
        body.visit(node)
        params = _params(node)
        self.env.update(body.env)
        self.symbols.append(
            {
                "name": name,
                "kind": "method" if in_class else "function",
                "line": node.lineno,
                "end": node.end_lineno or node.lineno,
                "signature": _signature(node),
                "decorators": [text for item in node.decorator_list if (text := dotted(item))],
                "doc": (ast.get_docstring(node) or "").strip().split("\n")[0][:160],
                "calls": list(body.calls)[:MAX_NAMES],
                "refs": [ref for ref in body.refs if ref not in body.calls][:MAX_NAMES],
                "sql": list(body.sql),
                "env": list(body.env),
            }
        )
        routes = [route for item in node.decorator_list if (route := _route(item)) is not None]
        if (
            class_route is not None and node.name in HTTP_VERBS
        ):  # a Flask MethodView: the class holds the route
            routes.append((class_route[0], class_route[1], [node.name.upper()]))
        payload, response = _smorest(node.decorator_list)
        for owner, path, methods in routes:
            for method in methods or ["GET"]:
                self.endpoints.append(
                    {
                        "method": method,
                        "path": path,
                        "owner": owner,
                        "handler": name,
                        "line": node.lineno,
                        "params": params,
                        "payload": payload,
                        "payload_keys": list(body.payload_keys),
                        "response": response or _text(_keyword_of(node, "response_model"), 80),
                        "auth": _auth_marks(node.decorator_list, params),
                        "doc": (ast.get_docstring(node) or "").strip().split("\n")[0][:160],
                    }
                )
        self._walk(node.body, name + ".", None)  # routes declared inside a factory function

    def _module_level(self, tree: ast.Module) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                maker = dotted(node.value.func).rsplit(".", 1)[-1]
                if maker in ROUTER_MAKERS:
                    prefix = _string(_keyword(node.value, ROUTER_MAKERS[maker])) or ""
                    for target in node.targets:
                        if name := dotted(target):
                            self.prefixes[name] = prefix
                elif maker == "Table" and node.value.args and (table := _string(node.value.args[0])):
                    self.tables[table] = None
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            attr = node.func.attr
            if attr in MOUNT_CALLS and node.args:
                self.mounts.append(
                    {
                        "onto": dotted(node.func.value),
                        "target": dotted(node.args[0]),
                        "prefix": _string(_keyword(node, MOUNT_CALLS[attr])) or "",
                    }
                )
            elif attr in ("add_url_rule", "add_api_route") and node.args and (path := _string(node.args[0])):
                handler = dotted(_keyword(node, "view_func") or _keyword(node, "endpoint")) or (
                    dotted(node.args[1]) if len(node.args) > 1 else ""
                )
                for method in _strings(_keyword(node, "methods")) or ["GET"]:
                    self.endpoints.append(
                        _bare_endpoint(method.upper(), path, dotted(node.func.value), handler, node)
                    )
            elif attr == "add_resource" and len(node.args) > 1 and (path := _string(node.args[1])):
                self.endpoints.append(
                    _bare_endpoint("*", path, dotted(node.func.value), dotted(node.args[0]), node)
                )


def _keyword_of(node: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> ast.AST | None:
    for item in node.decorator_list:
        if isinstance(item, ast.Call) and (value := _keyword(item, name)) is not None:
            return value
    return None


def _bare_endpoint(method: str, path: str, owner: str, handler: str, node: ast.Call) -> dict[str, Any]:
    return {
        "method": method,
        "path": path,
        "owner": owner,
        "handler": handler,
        "line": node.lineno,
        "params": [],
        "payload": "",
        "payload_keys": [],
        "response": "",
        "auth": [],
        "doc": "",
    }


def describe(source: str, module: str, is_package: bool = False) -> dict[str, Any]:
    """The record of one Python file; a file that does not parse gives {'error': ...} and nothing else."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError) as error:
        return {"module": module, "error": f"{type(error).__name__}: {error}"[:200]}
    parsed = _File(tree, module, is_package)
    settings = env_reads(tree)
    return {
        "module": module,
        "doc": (ast.get_docstring(tree) or "").strip().split("\n")[0][:200],
        "imports": parsed.imports,
        "symbols": parsed.symbols,
        "endpoints": parsed.endpoints,
        "prefixes": parsed.prefixes,
        "mounts": parsed.mounts,
        "tables": list(parsed.tables),
        "env": list(settings),
        "env_required": [name for name, line in settings.items() if line[1]],
        "env_lines": {name: line[0] for name, line in settings.items()},
    }


def env_reads(tree: ast.Module) -> dict[str, tuple[int, bool]]:
    """Every environment variable the file reads, anywhere in it (module level and class bodies too, where
    settings usually live): name -> (line of the first read, read without a default). A name read without a
    default (`os.environ["X"]`, `os.getenv("X")`) has to be set for the code to work; that is what a failed
    start is usually about. Only names are recorded, never a value."""
    found: dict[str, tuple[int, bool]] = {}

    def note(name: str, line: int, required: bool) -> None:
        first, needed = found.get(name, (line, False))
        found[name] = (min(first, line), needed or required)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and node.args and (name := _string(node.args[0])):
            called = dotted(node.func)
            if called in ("os.getenv", "getenv") or called.endswith("environ.get"):
                has_default = len(node.args) > 1 or _keyword(node, "default") is not None
                note(name, node.lineno, not has_default)
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.ctx, ast.Load)
            and (key := _string(node.slice))
            and dotted(node.value).endswith("environ")
        ):
            note(key, node.lineno, True)
    return found

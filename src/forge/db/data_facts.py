"""Finds the code that reads credentials from a database table into environment variables (spec §9.5.1),
so Forge can refuse to read those tables (D-160). Kept from the retired knowledge base: it is a safety
function, not knowledge."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

from forge.db.python_index import ModuleFacts, dotted, string_value

_SQL_START = re.compile(r"^\s*(SELECT|INSERT|UPDATE|DELETE|WITH|CREATE|ALTER|DROP|MERGE|TRUNCATE)\b", re.I)
_TABLE_REF = re.compile(
    r"\b(?:FROM|JOIN|INTO|UPDATE|TABLE(?:\s+IF\s+(?:NOT\s+)?EXISTS)?)\s+([A-Za-z_][\w.\"]*)", re.I
)
_ENV_READ = {"os.environ.get", "os.getenv", "environ.get", "getenv", "os.environ.setdefault"}


@dataclass
class SqlUsage:
    module: str
    function: str
    operation: str
    tables: list[str]
    schema_qualified: bool
    path: str
    line: int
    snippet: str
    in_tests: bool = False


@dataclass
class BootstrapFact:
    """Code that reads credentials from a DB table into environment variables (spec §9.5.1)."""

    module: str
    function: str
    tables: list[str]
    env_names: list[str]
    path: str
    line: int


# --- raw SQL and the bootstrap ---


def extract_sql_usage(modules: list[ModuleFacts]) -> tuple[list[SqlUsage], list[BootstrapFact]]:
    usages: list[SqlUsage] = []
    bootstraps: list[BootstrapFact] = []
    for facts in modules:
        for function in [
            n for n in ast.walk(facts.tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
        ]:
            found = _sql_in(function, facts)
            usages += found
            env_names = _env_assignments(function, facts)
            if found and env_names and not is_test_path(facts.path):
                tables = sorted({t for usage in found for t in usage.tables})
                bootstraps.append(
                    BootstrapFact(facts.module, function.name, tables, env_names, facts.path, function.lineno)
                )
    return usages, bootstraps


def _sql_in(function: ast.FunctionDef | ast.AsyncFunctionDef, facts: ModuleFacts) -> list[SqlUsage]:
    found = []
    seen: set[int] = set()
    for node in ast.walk(function):
        text = (
            string_value(node, facts.constants)
            if isinstance(node, ast.Constant | ast.JoinedStr | ast.BinOp)
            else None
        )
        if not text or not _SQL_START.match(text) or id(node) in seen:
            continue
        seen.add(id(node))
        for child in ast.walk(node):
            seen.add(id(child))
        tables = sorted({t.strip('"') for t in _TABLE_REF.findall(text)})
        found.append(
            SqlUsage(
                module=facts.module,
                function=function.name,
                operation=_SQL_START.match(text).group(1).upper(),  # type: ignore[union-attr]
                tables=[t.split(".")[-1] for t in tables],
                schema_qualified=any("." in t for t in tables),
                path=facts.path,
                line=getattr(node, "lineno", function.lineno),
                snippet=" ".join(text.split())[:160],
                in_tests=is_test_path(facts.path),
            )
        )
    return found


def _env_assignments(function: ast.FunctionDef | ast.AsyncFunctionDef, facts: ModuleFacts) -> list[str]:
    """Names the function writes into os.environ. When the name is a variable (os.environ[name] = ...),
    the module's env-name mapping (e.g. {"db_host": "DB_HOST"}) supplies the candidates."""
    names: list[str] = []
    dynamic = False
    for node in ast.walk(function):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Subscript) and dotted(target.value) in ("os.environ", "environ"):
                constant = string_value(target.slice, facts.constants)
                if constant:
                    names.append(constant)
                else:
                    dynamic = True
    if dynamic:
        names += module_level_env_maps(facts)
    return sorted(set(names))


def _assignment(item: ast.stmt) -> tuple[str | None, ast.expr | None]:
    if isinstance(item, ast.Assign) and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name):
        return item.targets[0].id, item.value
    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
        return item.target.id, item.value
    return None, None


def module_level_env_maps(facts: ModuleFacts) -> list[str]:
    names = []
    for node in facts.tree.body:
        _, value = _assignment(node)
        if isinstance(value, ast.Dict):
            names += [
                v.value
                for v in value.values
                if isinstance(v, ast.Constant)
                and isinstance(v.value, str)
                and v.value.isupper()
                and "_" in v.value
            ]
    return names


def is_test_path(path: str) -> bool:
    parts = path.split("/")
    return "tests" in parts or "test" in parts or parts[-1].startswith("test_") or parts[-1] == "conftest.py"


# --- numbered SQL scripts ---

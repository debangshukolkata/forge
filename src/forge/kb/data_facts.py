"""Data-layer extractors (spec §11.3): SQLAlchemy models, raw SQL usage, the credentials bootstrap
(spec §9.5.1), numbered SQL scripts, and environment/config keys."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

from forge.kb.python_index import ModuleFacts, dotted, string_value

_SQL_START = re.compile(r"^\s*(SELECT|INSERT|UPDATE|DELETE|WITH|CREATE|ALTER|DROP|MERGE|TRUNCATE)\b", re.I)
_TABLE_REF = re.compile(
    r"\b(?:FROM|JOIN|INTO|UPDATE|TABLE(?:\s+IF\s+(?:NOT\s+)?EXISTS)?)\s+([A-Za-z_][\w.\"]*)", re.I
)
_CREATE_TABLE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([\w.\"]+)\s*\((.*?)\)\s*;", re.I | re.S
)
_SCRIPT_NAME = re.compile(r"^V(\d+)__(.+)\.sql$", re.I)
_ENV_READ = {"os.environ.get", "os.getenv", "environ.get", "getenv", "os.environ.setdefault"}


@dataclass
class ModelColumn:
    name: str
    type: str
    primary_key: bool = False
    foreign_key: str | None = None
    nullable: bool | None = None


@dataclass
class ModelFact:
    class_name: str
    table: str
    columns: list[ModelColumn]
    path: str
    line: int


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


@dataclass
class ScriptTable:
    script: str
    table: str
    columns: list[str]


@dataclass
class SqlScripts:
    folder: str | None
    naming: str | None
    scripts: list[str] = field(default_factory=list)
    tables: list[ScriptTable] = field(default_factory=list)
    next_name_example: str | None = None


# --- SQLAlchemy models ---


def extract_models(modules: list[ModuleFacts]) -> list[ModelFact]:
    models = []
    for facts in modules:
        for node in ast.walk(facts.tree):
            if not isinstance(node, ast.ClassDef):
                continue
            table = None
            columns = []
            for item in node.body:
                target, value = _assignment(item)
                if target == "__tablename__":
                    table = string_value(value, facts.constants)
                elif (
                    target
                    and isinstance(value, ast.Call)
                    and dotted(value.func).split(".")[-1] in ("mapped_column", "Column")
                ):
                    columns.append(_column(target, value, item))
            if table:
                models.append(ModelFact(node.name, table, columns, facts.path, node.lineno))
    return models


def _assignment(item: ast.stmt) -> tuple[str | None, ast.expr | None]:
    if isinstance(item, ast.Assign) and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name):
        return item.targets[0].id, item.value
    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
        return item.target.id, item.value
    return None, None


def _column(name: str, call: ast.Call, item: ast.stmt) -> ModelColumn:
    column = ModelColumn(name=name, type="")
    for argument in call.args:
        text = ast.unparse(argument)
        if isinstance(argument, ast.Call) and dotted(argument.func).endswith("ForeignKey") and argument.args:
            column.foreign_key = string_value(argument.args[0]) or ast.unparse(argument.args[0])
        elif not column.type:
            column.type = text
    if not column.type and isinstance(item, ast.AnnAssign):
        # Mapped[int] with the type only in the annotation (e.g. a ForeignKey-only mapped_column)
        annotation = item.annotation
        if isinstance(annotation, ast.Subscript) and dotted(annotation.value).endswith("Mapped"):
            annotation = annotation.slice
        column.type = ast.unparse(annotation)
    for keyword in call.keywords:
        if keyword.arg == "primary_key":
            column.primary_key = ast.unparse(keyword.value) == "True"
        elif keyword.arg == "nullable":
            column.nullable = ast.unparse(keyword.value) == "True"
    return column


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


# --- environment and config keys ---


def extract_env_keys(modules: list[ModuleFacts]) -> dict[str, list[str]]:
    keys: dict[str, list[str]] = {}
    for facts in modules:
        for node in ast.walk(facts.tree):
            key = None
            if isinstance(node, ast.Call) and dotted(node.func) in _ENV_READ and node.args:
                key = string_value(node.args[0], facts.constants)
            elif isinstance(node, ast.Subscript) and dotted(node.value) in ("os.environ", "environ"):
                key = string_value(node.slice, facts.constants)
            if key:
                keys.setdefault(key, []).append(f"{facts.path}:{getattr(node, 'lineno', 0)}")
    return dict(sorted(keys.items()))


# --- numbered SQL scripts ---


def parse_sql_scripts(repo_dir: Path, app_subfolder: str) -> SqlScripts:
    candidates = sorted(
        {p.parent for p in (repo_dir / app_subfolder).rglob("*.sql")}, key=lambda p: len(p.parts)
    )
    if not candidates:
        return SqlScripts(folder=None, naming=None)
    folder = max(candidates, key=lambda p: len(list(p.glob("*.sql"))))
    names = sorted(p.name for p in folder.glob("*.sql"))
    result = SqlScripts(folder=folder.relative_to(repo_dir).as_posix(), naming=None, scripts=names)
    numbers = [int(m.group(1)) for n in names if (m := _SCRIPT_NAME.match(n))]
    if numbers and len(numbers) == len(names):
        width = len(_SCRIPT_NAME.match(names[0]).group(1))  # type: ignore[union-attr]
        result.naming = f"V<{'n' * width}>__<description>.sql"
        result.next_name_example = f"V{max(numbers) + 1:0{width}d}__<description>.sql"
    for name in names:
        text = (folder / name).read_text(encoding="utf-8", errors="replace")
        for table, body in _CREATE_TABLE.findall(text):
            columns = [
                line.strip().split()[0]
                for line in _split_columns(body)
                if line.strip()
                and not line.strip()
                .upper()
                .startswith(("PRIMARY", "FOREIGN", "UNIQUE", "CONSTRAINT", "CHECK"))
            ]
            result.tables.append(ScriptTable(name, table.strip('"').split(".")[-1], columns))
    return result


def _split_columns(body: str) -> list[str]:
    parts, depth, current = [], 0, ""
    for char in body:
        depth += char == "("
        depth -= char == ")"
        if char == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += char
    return [*parts, current]

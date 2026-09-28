#!/usr/bin/env python3
"""forge_structure_export.py — describe a Python codebase's STRUCTURE for Forge's Mode B, without its code.

Run it yourself, on the machine that has the code (Forge never runs it and never sees the path):

    python forge_structure_export.py <app folder> [--out structure_export] [--depth 8]
        [--include PATH ...] [--exclude PATH ...] [--mask terms.txt] [--docstrings]

It writes <out>.json (for `/profile import`) and <out>.md (for you to read first).

What it outputs: the folder tree; pinned package versions from requirements*.txt / pyproject.toml; per module:
imports, classes (bases, decorators), function/method signatures (parameter names, type hints; defaults shown
as ...), flask-smorest/Flask blueprints (name, url_prefix, routes, methods, schema names), SQLAlchemy model
columns, SQL script file names, LangGraph node/edge names, and environment/config KEY NAMES.

What it never outputs: function bodies, string literals, constant/config values, comments, .env contents,
data files. Docstrings only with --docstrings. --mask replaces listed words everywhere, consistently.

Standard library only; Python 3.10+.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path

EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".env",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    "dist",
    "build",
    ".idea",
    ".vscode",
    "site-packages",
    ".eggs",
}
DATA_SUFFIXES = {".csv", ".xlsx", ".xls", ".parquet", ".db", ".sqlite", ".pkl", ".json", ".jsonl", ".pdf"}
SECRET_NAMES = re.compile(r"(^|[._-])(env|secret|credential|key|token|password)s?([._-]|$)", re.IGNORECASE)
ENV_CALL = re.compile(r"""(?:environ(?:\.get)?|getenv)\s*[\[(]\s*["']([A-Za-z_][A-Za-z0-9_]*)["']""")
VERSION_VERSION = 1


class Masker:
    def __init__(self, terms: list[str]) -> None:
        self.terms = sorted({t.strip() for t in terms if t.strip()}, key=len, reverse=True)
        self.placeholders = {t: f"TERM{i + 1}" for i, t in enumerate(self.terms)}

    def __call__(self, text: str) -> str:
        for term in self.terms:
            text = re.sub(re.escape(term), self.placeholders[term], text, flags=re.IGNORECASE)
        return text


def _annotation(node: ast.expr | None) -> str | None:
    if node is None:
        return None
    try:
        text = ast.unparse(node)
    except Exception:
        return None
    # Annotations can contain string literals (Literal["x"]): keep the shape, drop the values.
    return re.sub(r"(['\"]).*?\1", "'…'", text)


def _decorator(node: ast.expr) -> str:
    target = node.func if isinstance(node, ast.Call) else node
    try:
        name = ast.unparse(target)
    except Exception:
        return "?"
    return name + ("(…)" if isinstance(node, ast.Call) else "")


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, object]:
    args = node.args
    params = []
    positional = [*args.posonlyargs, *args.args]
    defaults_start = len(positional) - len(args.defaults)
    for index, arg in enumerate(positional):
        params.append(
            {"name": arg.arg, "type": _annotation(arg.annotation), "default": index >= defaults_start}
        )
    if args.vararg:
        params.append(
            {"name": "*" + args.vararg.arg, "type": _annotation(args.vararg.annotation), "default": False}
        )
    for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=True):
        params.append(
            {
                "name": arg.arg,
                "type": _annotation(arg.annotation),
                "default": default is not None,
                "kwonly": True,
            }
        )
    if args.kwarg:
        params.append(
            {"name": "**" + args.kwarg.arg, "type": _annotation(args.kwarg.annotation), "default": False}
        )
    rendered = ", ".join(
        ("*, " if p.get("kwonly") and p is next(q for q in params if q.get("kwonly")) else "")
        + str(p["name"])
        + (f": {p['type']}" if p["type"] else "")
        + (" = …" if p["default"] else "")
        for p in params
    )
    returns = _annotation(node.returns)
    return {
        "name": node.name,
        "async": isinstance(node, ast.AsyncFunctionDef),
        "signature": f"{node.name}({rendered})" + (f" -> {returns}" if returns else ""),
        "decorators": [_decorator(d) for d in node.decorator_list],
    }


def _call_name(node: ast.expr) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def _string_arg(call: ast.Call, index: int, keyword: str) -> str | None:
    """Blueprint names/prefixes and route paths are structure, not data: kept (and masked if asked)."""
    value = (
        call.args[index]
        if len(call.args) > index
        else next((k.value for k in call.keywords if k.arg == keyword), None)
    )
    return value.value if isinstance(value, ast.Constant) and isinstance(value.value, str) else None


def describe_module(source: str, include_docstrings: bool) -> dict[str, object]:
    tree = ast.parse(source)
    module: dict[str, object] = {
        "imports": [],
        "classes": [],
        "functions": [],
        "blueprints": [],
        "models": [],
        "graph": {"nodes": [], "edges": []},
        "env_keys": sorted(set(ENV_CALL.findall(source))),
    }
    imports: list[str] = module["imports"]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = "." * node.level + (node.module or "")
            imports += [f"{base}.{alias.name}" if base else alias.name for alias in node.names]
    blueprints: dict[str, dict[str, object]] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            callee = _call_name(node.value.func)
            if (
                callee.split(".")[-1] == "Blueprint"
                and node.targets
                and isinstance(node.targets[0], ast.Name)
            ):
                blueprints[node.targets[0].id] = {
                    "variable": node.targets[0].id,
                    "name": _string_arg(node.value, 0, "name"),
                    "url_prefix": next(
                        (
                            k.value.value
                            for k in node.value.keywords
                            if k.arg == "url_prefix" and isinstance(k.value, ast.Constant)
                        ),
                        None,
                    ),
                    "routes": [],
                }
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            entry = _signature(node)
            if include_docstrings and ast.get_docstring(node):
                entry["doc"] = ast.get_docstring(node)
            module["functions"].append(entry)
            _routes_of(node, blueprints, [])
        elif isinstance(node, ast.ClassDef):
            bases = [_call_name(b) for b in node.bases]
            entry = {
                "name": node.name,
                "bases": bases,
                "decorators": [_decorator(d) for d in node.decorator_list],
                "methods": [
                    _signature(m) for m in node.body if isinstance(m, ast.FunctionDef | ast.AsyncFunctionDef)
                ],
            }
            if include_docstrings and ast.get_docstring(node):
                entry["doc"] = ast.get_docstring(node)
            module["classes"].append(entry)
            methods = [
                m.name.upper()
                for m in node.body
                if isinstance(m, ast.FunctionDef | ast.AsyncFunctionDef)
                and m.name in ("get", "post", "put", "patch", "delete")
            ]
            _routes_of(node, blueprints, methods)
            columns = _model_columns(node)
            if columns:
                table = next(
                    (
                        _string_value(s.value)
                        for s in node.body
                        if isinstance(s, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == "__tablename__" for t in s.targets)
                    ),
                    None,
                )
                module["models"].append({"class": node.name, "table": table, "columns": columns})
    module["blueprints"] = list(blueprints.values())
    _graph_of(tree, module["graph"])
    return module


def _string_value(node: ast.expr) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _routes_of(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    blueprints: dict[str, dict[str, object]],
    methods: list[str],
) -> None:
    schemas: list[str] = []
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
            owner = _call_name(decorator.func.value)
            if decorator.func.attr in ("arguments", "response", "paginate"):
                schemas += [_call_name(a) for a in decorator.args[:1]]
            if decorator.func.attr == "route" and owner in blueprints:
                path = _string_arg(decorator, 0, "rule")
                kw_methods = next((k.value for k in decorator.keywords if k.arg == "methods"), None)
                listed = (
                    [e.value for e in kw_methods.elts if isinstance(e, ast.Constant)]
                    if isinstance(kw_methods, ast.List)
                    else []
                )
                blueprints[owner]["routes"].append(
                    {"path": path, "handler": node.name, "methods": listed or methods or ["GET"]}
                )
    if isinstance(node, ast.ClassDef):
        for method in node.body:
            if isinstance(method, ast.FunctionDef | ast.AsyncFunctionDef):
                for decorator in method.decorator_list:
                    if (
                        isinstance(decorator, ast.Call)
                        and isinstance(decorator.func, ast.Attribute)
                        and decorator.func.attr in ("arguments", "response", "paginate")
                    ):
                        schemas += [_call_name(a) for a in decorator.args[:1]]
    for blueprint in blueprints.values():
        for route in blueprint["routes"]:
            if route["handler"] == node.name:
                route["schemas"] = sorted({s for s in schemas if s})


def _model_columns(node: ast.ClassDef) -> list[dict[str, str]]:
    columns = []
    for statement in node.body:
        target = (
            statement.target
            if isinstance(statement, ast.AnnAssign)
            else (statement.targets[0] if isinstance(statement, ast.Assign) and statement.targets else None)
        )
        value = statement.value if isinstance(statement, ast.AnnAssign | ast.Assign) else None
        if not isinstance(target, ast.Name) or not isinstance(value, ast.Call):
            continue
        callee = _call_name(value.func).split(".")[-1]
        if callee in ("Column", "mapped_column"):
            kind = next((_call_name(a) for a in value.args if not isinstance(a, ast.Constant)), "")
            annotation = _annotation(statement.annotation) if isinstance(statement, ast.AnnAssign) else None
            columns.append({"name": target.id, "type": kind or annotation or "?"})
    return columns


def _graph_of(tree: ast.Module, graph: dict[str, list[str]]) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            args = [_string_value(a) or _call_name(a) for a in node.args[:2]]
            if node.func.attr == "add_node" and args:
                graph["nodes"].append(args[0])
            elif node.func.attr == "add_edge" and len(args) == 2:
                graph["edges"].append(f"{args[0]} -> {args[1]}")
            elif node.func.attr == "add_conditional_edges" and args:
                graph["edges"].append(f"{args[0]} -> (conditional)")


def pinned_versions(root: Path) -> dict[str, str]:
    versions: dict[str, str] = {}
    for file in sorted(root.glob("requirements*.txt")):
        for line in file.read_text(encoding="utf-8", errors="replace").splitlines():
            match = re.match(
                r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?\s*(==|>=|~=|<=|>|<)?\s*([^\s;#]*)", line
            )
            if match and not line.strip().startswith(("#", "-")):
                versions[match.group(1)] = f"{match.group(2) or ''}{match.group(3) or ''}" or "*"
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        block = re.search(
            r"dependencies\s*=\s*\[(.*?)\]", pyproject.read_text(encoding="utf-8", errors="replace"), re.S
        )
        for item in re.findall(r"['\"]([^'\"]+)['\"]", block.group(1) if block else ""):
            match = re.match(r"([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?\s*(.*)", item)
            if match:
                versions.setdefault(match.group(1), match.group(2).strip() or "*")
    return versions


def export(
    root: Path, depth: int, includes: list[str], excludes: list[str], docstrings: bool, mask: Masker
) -> dict[str, object]:
    tree: list[str] = []
    modules: dict[str, object] = {}
    sql_scripts: list[str] = []
    skipped: list[str] = []
    for directory, subdirectories, files in os.walk(root):
        relative_dir = Path(directory).relative_to(root)
        subdirectories[:] = sorted(
            d
            for d in subdirectories
            if d not in EXCLUDED_DIRS
            and not d.startswith(".")
            and not _excluded(relative_dir / d, excludes)
            and len((relative_dir / d).parts) <= depth
        )
        for name in sorted(files):
            relative = (relative_dir / name).as_posix()
            if _excluded(Path(relative), excludes) or (
                includes and not any(relative.startswith(i.rstrip("/")) for i in includes)
            ):
                continue
            suffix = Path(name).suffix.lower()
            if name.startswith(".env") or (SECRET_NAMES.search(Path(name).stem) and suffix not in (".py",)):
                skipped.append(relative)  # never even listed with content: secrets
                continue
            tree.append(relative)
            if suffix == ".sql":
                sql_scripts.append(relative)
            elif suffix == ".py":
                try:
                    modules[relative] = describe_module(
                        (Path(directory) / name).read_text(encoding="utf-8", errors="replace"), docstrings
                    )
                except SyntaxError as error:
                    modules[relative] = {"error": f"could not parse (line {error.lineno})"}
            elif suffix in DATA_SUFFIXES:
                continue
    result = {
        "format": "forge-structure-export",
        "version": VERSION_VERSION,
        "tree": tree,
        "packages": pinned_versions(root),
        "modules": modules,
        "sql_scripts": sql_scripts,
        "not_exported": skipped,
    }
    return json.loads(mask(json.dumps(result))) if mask.terms else result


def _excluded(path: Path, excludes: list[str]) -> bool:
    text = path.as_posix()
    return any(text == e.rstrip("/") or text.startswith(e.rstrip("/") + "/") for e in excludes)


def to_markdown(data: dict[str, object]) -> str:
    lines = [
        "# Structure export (review before importing into Forge)",
        "",
        "Contains names and signatures only — no function bodies, literals, values, comments or .env contents.",
        "",
        "## Packages",
        *[f"- {k} {v}" for k, v in data["packages"].items()],
        "",
        "## SQL scripts",
        *[f"- {s}" for s in data["sql_scripts"]],
        "",
        "## Modules",
    ]
    for path, module in data["modules"].items():
        lines.append(f"### {path}")
        if "error" in module:
            lines.append(f"- {module['error']}")
            continue
        lines += [
            f"- class {c['name']}({', '.join(c['bases'])})"
            + "".join(f"\n  - {m['signature']}" for m in c["methods"])
            for c in module["classes"]
        ]
        lines += [f"- def {f['signature']}" for f in module["functions"]]
        lines += [
            f"- blueprint {b['name']} {b['url_prefix'] or ''}: "
            + ", ".join(f"{'/'.join(r['methods'])} {r['path']}" for r in b["routes"])
            for b in module["blueprints"]
        ]
        lines += [
            f"- model {m['class']} (table {m['table']}): "
            + ", ".join(f"{c['name']} {c['type']}" for c in m["columns"])
            for m in module["models"]
        ]
        if module["env_keys"]:
            lines.append("- env keys: " + ", ".join(module["env_keys"]))
        if module["graph"]["nodes"]:
            lines.append(
                "- graph nodes: "
                + ", ".join(module["graph"]["nodes"])
                + "; edges: "
                + ", ".join(module["graph"]["edges"])
            )
    if data["not_exported"]:
        lines += [
            "",
            "## Not exported (secret-looking files; only counted)",
            f"- {len(data['not_exported'])} file(s)",
        ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export a codebase's structure (no code) for Forge Mode B.")
    parser.add_argument("root", type=Path)
    parser.add_argument("--out", default="structure_export")
    parser.add_argument("--depth", type=int, default=8)
    parser.add_argument("--include", action="append", default=[])
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--mask", type=Path, help="file with one sensitive term per line")
    parser.add_argument("--docstrings", action="store_true")
    args = parser.parse_args(argv)
    terms = args.mask.read_text(encoding="utf-8").splitlines() if args.mask else []
    data = export(args.root.resolve(), args.depth, args.include, args.exclude, args.docstrings, Masker(terms))
    data["not_exported"] = (
        [f"<{len(data['not_exported'])} secret-looking file(s)>"] if data["not_exported"] else []
    )
    Path(f"{args.out}.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
    Path(f"{args.out}.md").write_text(to_markdown(data), encoding="utf-8")
    print(
        f"Wrote {args.out}.json and {args.out}.md — review them, then /profile import {args.out}.json in Forge."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

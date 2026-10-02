"""Python AST index (spec §11.3): modules, symbols, signatures, decorators, imports, references."""

from __future__ import annotations

import ast
import contextlib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath


@dataclass
class Symbol:
    kind: str  # class | function | method
    name: str
    qualname: str
    module: str
    path: str
    line: int
    end_line: int
    signature: str = ""
    decorators: list[str] = field(default_factory=list)
    bases: list[str] = field(default_factory=list)
    doc: str = ""


@dataclass
class ImportFact:
    module: str  # where it is imported from ("" for plain `import x`)
    name: str
    alias: str
    line: int


@dataclass
class ModuleFacts:
    module: str  # dotted, importable from the app folder
    path: str  # repository-relative POSIX path
    source: str
    tree: ast.Module
    symbols: list[Symbol] = field(default_factory=list)
    imports: list[ImportFact] = field(default_factory=list)
    references: list[tuple[str, int]] = field(default_factory=list)  # called/used names
    constants: dict[str, str] = field(default_factory=dict)  # module-level string constants

    def imported_as(self, alias: str) -> ImportFact | None:
        return next((item for item in self.imports if item.alias == alias), None)


def module_name(repo_relative: str, app_subfolder: str) -> str:
    path = PurePosixPath(repo_relative)
    with contextlib.suppress(ValueError):
        path = path.relative_to(app_subfolder)
    parts = list(path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def parse_module(repo_dir: Path, relative: str, app_subfolder: str) -> ModuleFacts | None:
    try:
        source = (repo_dir / relative).read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=relative)
    except (SyntaxError, ValueError, OSError):
        return None
    facts = ModuleFacts(module=module_name(relative, app_subfolder), path=relative, source=source, tree=tree)
    _collect(facts)
    return facts


def dotted(node: ast.AST) -> str:
    """'a.b.c' for Name/Attribute chains, the unparsed source otherwise."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{dotted(node.value)}.{node.attr}"
    if isinstance(node, ast.Call):
        return dotted(node.func)
    return ast.unparse(node)


def string_value(node: ast.AST | None, constants: dict[str, str] | None = None) -> str | None:
    """A literal string, a module constant, or an f-string with constants filled in (others as {…})."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and constants and node.id in constants:
        return constants[node.id]
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value))
            elif isinstance(value, ast.FormattedValue):
                parts.append(string_value(value.value, constants) or "{…}")
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = string_value(node.left, constants), string_value(node.right, constants)
        if left is not None and right is not None:
            return left + right
    return None


def _collect(facts: ModuleFacts) -> None:
    for statement in facts.tree.body:
        target = (
            statement.targets[0]
            if isinstance(statement, ast.Assign) and len(statement.targets) == 1
            else None
        )
        if isinstance(statement, ast.Assign) and isinstance(target, ast.Name):
            value = string_value(statement.value, facts.constants)
            if value is not None:
                facts.constants[target.id] = value
    for node in ast.walk(facts.tree):
        if isinstance(node, ast.Import):
            facts.imports += [ImportFact("", a.name, a.asname or a.name, node.lineno) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = ("." * node.level) + (node.module or "")
            facts.imports += [ImportFact(base, a.name, a.asname or a.name, node.lineno) for a in node.names]
        elif isinstance(node, ast.Call):
            facts.references.append((dotted(node.func), node.lineno))
    _symbols(facts, facts.tree.body, prefix="", in_class=False)


def _symbols(facts: ModuleFacts, body: list[ast.stmt], prefix: str, in_class: bool) -> None:
    for node in body:
        if isinstance(node, ast.ClassDef):
            qualname = f"{prefix}{node.name}"
            facts.symbols.append(
                Symbol(
                    kind="class",
                    name=node.name,
                    qualname=qualname,
                    module=facts.module,
                    path=facts.path,
                    line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    decorators=[ast.unparse(d) for d in node.decorator_list],
                    bases=[ast.unparse(b) for b in node.bases],
                    doc=_first_line(ast.get_docstring(node)),
                )
            )
            _symbols(facts, node.body, prefix=f"{qualname}.", in_class=True)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            asynchronous = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
            returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
            facts.symbols.append(
                Symbol(
                    kind="method" if in_class else "function",
                    name=node.name,
                    qualname=f"{prefix}{node.name}",
                    module=facts.module,
                    path=facts.path,
                    line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    signature=f"{asynchronous}def {node.name}({ast.unparse(node.args)}){returns}",
                    decorators=[ast.unparse(d) for d in node.decorator_list],
                    doc=_first_line(ast.get_docstring(node)),
                )
            )
            # Nested functions (e.g. graph node functions inside a builder) are indexed too.
            _symbols(facts, node.body, prefix=f"{prefix}{node.name}.", in_class=False)


def _first_line(doc: str | None) -> str:
    return doc.strip().splitlines()[0] if doc and doc.strip() else ""

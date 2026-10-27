"""code_outline: the structure of a file or folder, and who calls a name (TODO C11, D-498).

Reading whole files to find where something lives is slow on a large repository, and D-156 says no built index. This tool is the cheap middle: it parses on demand
and returns signatures and line numbers only (Python with the `ast` module, other languages with a few regular expressions), and `callers` lists the places where a
name is called or referenced. Read-only; secret files are skipped; nothing is stored."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Literal

from pydantic import Field

from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult

SKIPPED_FOLDERS = {
    ".git",
    ".forge",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
}
SOURCE_SUFFIXES = (".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".go", ".java", ".rs", ".rb", ".php", ".cs")
MAX_FILE_BYTES = 600_000
MAX_FILES = 60
MAX_LINES = 400

# One pattern per family; group "name" is the symbol. Order of the tuples is the order of the label shown.
GENERIC_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "class",
        re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?(?:public\s+)?class\s+(?P<name>\w+)"),
    ),
    (
        "interface",
        re.compile(r"^\s*(?:export\s+)?(?:public\s+)?(?:interface|type|enum|struct|trait)\s+(?P<name>\w+)"),
    ),
    (
        "function",
        re.compile(
            r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:pub\s+)?(?:fn|func|function)\s+(?:\([^)]*\)\s*)?(?P<name>\w+)\s*[<(]"
        ),
    ),
    (
        "function",
        re.compile(
            r"^\s*(?:export\s+)?(?:const|let|var)\s+(?P<name>\w+)\s*(?::[^=]+)?=\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*=>"
        ),
    ),
    ("function", re.compile(r"^\s*def\s+(?P<name>\w+)")),  # ruby
)


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    try:
        arguments = ast.unparse(node.args)
    except Exception:  # an odd tree never stops an outline
        arguments = "..."
    returns = f" -> {ast.unparse(node.returns)}" if node.returns is not None else ""
    return f"({arguments}){returns}"


def _first_doc_line(node: ast.AST) -> str:
    doc = (
        ast.get_docstring(node)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Module)
        else None
    )
    return doc.strip().splitlines()[0][:90] if doc and doc.strip() else ""


def python_outline(text: str) -> list[str]:
    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        return [f"(does not parse: line {error.lineno}: {error.msg})"]
    lines: list[str] = []

    def visit(body: list[ast.stmt], depth: int) -> None:
        for node in body:
            pad = "  " * depth
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
                doc = _first_doc_line(node)
                lines.append(
                    f"{pad}{node.lineno}: {prefix} {node.name}{_signature(node)}"
                    + (f"  # {doc}" if doc else "")
                )
            elif isinstance(node, ast.ClassDef):
                bases = ", ".join(ast.unparse(base) for base in node.bases)
                doc = _first_doc_line(node)
                lines.append(
                    f"{pad}{node.lineno}: class {node.name}"
                    + (f"({bases})" if bases else "")
                    + (f"  # {doc}" if doc else "")
                )
                visit(node.body, depth + 1)
            elif isinstance(node, ast.Assign) and depth == 0:
                names = [t.id for t in node.targets if isinstance(t, ast.Name) and t.id.isupper()]
                if names:
                    lines.append(f"{pad}{node.lineno}: {', '.join(names)} = ...")

    visit(tree.body, 0)
    return lines


def generic_outline(text: str) -> list[str]:
    lines: list[str] = []
    for number, line in enumerate(text.splitlines(), 1):
        if len(line) > 300:
            continue
        for label, pattern in GENERIC_PATTERNS:
            match = pattern.match(line)
            if match:
                lines.append(f"{number}: {label} {match.group('name')}")
                break
    return lines


def outline_of(path: Path, text: str) -> list[str]:
    return python_outline(text) if path.suffix == ".py" else generic_outline(text)


def python_callers(text: str, name: str) -> list[tuple[int, str]]:
    """Calls and attribute uses of `name` in a Python file, with the enclosing function."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    found: list[tuple[int, str]] = []

    def walk(node: ast.AST, scope: str) -> None:
        for child in ast.iter_child_nodes(node):
            inner = (
                child.name
                if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
                else scope
            )
            if isinstance(child, ast.Call):
                target = child.func
                called = (
                    target.id
                    if isinstance(target, ast.Name)
                    else target.attr
                    if isinstance(target, ast.Attribute)
                    else ""
                )
                if called == name:
                    found.append((child.lineno, scope or "<module>"))
            walk(child, inner)

    walk(tree, "")
    return found


def generic_callers(text: str, name: str) -> list[tuple[int, str]]:
    pattern = re.compile(rf"\b{re.escape(name)}\s*\(")
    return [(number, "") for number, line in enumerate(text.splitlines(), 1) if pattern.search(line)]


class CodeOutline(Tool):
    name = "code_outline"
    read_only = True
    description = (
        "The structure of a source file or folder without reading it all: classes, functions and methods with signatures and line numbers "
        "(Python in full detail, JavaScript/TypeScript/Go/Java/Rust/Ruby/PHP/C# by pattern). Use it to find where something lives in a large repository, "
        "then read_file just that range. action 'callers' lists where a function or method NAME is called (the enclosing function for Python), "
        "searched through the given folder. Read-only."
    )

    class Args(ToolArgs):
        action: Literal["outline", "callers"] = Field(default="outline")
        path: str = Field(default=".", description="A source file or a folder of the workspace.")
        name: str = Field(default="", description="callers: the function or method name to look for.")

    def summary(self, args: CodeOutline.Args) -> str:
        return f"{args.action} {args.path}" + (f" {args.name}" if args.name else "")

    async def run(self, args: CodeOutline.Args, context: ToolContext) -> ToolResult:
        workspace = context.workspace
        root = workspace.input_path(args.path) or workspace.path_of(args.path)
        if not root.exists():
            return ToolResult(ok=False, content=f"{args.path} does not exist.")
        files = self._files(root, context)
        if not files:
            return ToolResult(ok=True, content=f"No source files found under {args.path}.")
        if args.action == "callers":
            if not args.name.strip():
                return ToolResult(ok=False, content="Give `name`: the function or method to look for.")
            return self._callers(files, root, args.name.strip(), context)
        return self._outline(files, root, context)

    @staticmethod
    def _files(root: Path, context: ToolContext) -> list[Path]:
        if root.is_file():
            return [root]
        found: list[Path] = []
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root)
            if any(part in SKIPPED_FOLDERS for part in relative.parts[:-1]) or not path.is_file():
                continue
            if path.suffix not in SOURCE_SUFFIXES or path.stat().st_size > MAX_FILE_BYTES:
                continue
            if context.workspace.is_secret(str(path)):
                continue
            found.append(path)
        return found

    @staticmethod
    def _label(path: Path, root: Path) -> str:
        return path.name if root.is_file() else path.relative_to(root).as_posix()

    def _outline(self, files: list[Path], root: Path, context: ToolContext) -> ToolResult:
        out: list[str] = []
        for path in files[:MAX_FILES]:
            text = path.read_text(encoding="utf-8", errors="replace")
            entries = outline_of(path, text)
            out.append(f"{self._label(path, root)} ({len(text.splitlines())} lines)")
            out += [f"  {entry}" for entry in entries] or ["  (no top-level definitions found)"]
            if len(out) > MAX_LINES:
                out.append(f"... stopped at {MAX_LINES} lines; outline a narrower folder or a single file.")
                return ToolResult(ok=True, content="\n".join(out))
        if len(files) > MAX_FILES:
            out.append(f"... {len(files) - MAX_FILES} more files; outline a narrower folder.")
        return ToolResult(ok=True, content="\n".join(out))

    def _callers(self, files: list[Path], root: Path, name: str, context: ToolContext) -> ToolResult:
        out: list[str] = []
        for path in files:
            text = path.read_text(encoding="utf-8", errors="replace")
            hits = python_callers(text, name) if path.suffix == ".py" else generic_callers(text, name)
            out += [
                f"{self._label(path, root)}:{line}" + (f"  in {scope}" if scope else "")
                for line, scope in hits
            ]
            if len(out) >= MAX_LINES:
                out.append(f"... stopped at {MAX_LINES} hits.")
                break
        if not out:
            return ToolResult(
                ok=True,
                content=f"No calls of `{name}` found under {root}. It may be called dynamically; try grep.",
            )
        return ToolResult(ok=True, content=f"Calls of `{name}`:\n" + "\n".join(out))


def code_outline_tools() -> list[Tool]:
    return [CodeOutline()]

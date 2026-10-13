"""Tests that prove something (TODO C10, D-309): static warnings for tests that cannot fail, and a light mutation check.

- `weak_test_findings` reads test files and flags a test with no assertion, a tautology (`assert True`, `assert x == x`), an assertion
  that compares a call with the same call, and a test that mocks more than it asserts.
- `mutation_check` makes a few small deliberate mistakes in a source file (a flipped comparison, `+` for `-`, `True` for `False`, a
  dropped `return` value) one at a time, runs the tests after each, and reports the mistakes the tests did NOT notice: those are the
  places no test checks. The file is always restored. It runs the project's own tests, so it costs a few test runs; the model asks
  for it (the `mutation_check` tool), nothing runs it automatically."""

from __future__ import annotations

import ast
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import Field

from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult

MAX_MUTANTS = 8
TEST_TIMEOUT_S = 90
ASSERT_NAMES = {
    "fail",
    "raises",
    "warns",
    "approx",
    "assert_called",
    "assert_called_once",
    "assert_called_with",
}


def _is_test_file(path: Path) -> bool:
    return path.suffix == ".py" and (path.name.startswith("test_") or path.name.endswith("_test.py"))


def _asserts(node: ast.AST) -> int:
    count = 0
    for child in ast.walk(node):
        if isinstance(child, ast.Assert):
            count += 1
        elif isinstance(child, ast.Call):
            name = child.func.attr if isinstance(child.func, ast.Attribute) else getattr(child.func, "id", "")
            if name.startswith("assert") or name in ASSERT_NAMES:
                count += 1
        elif isinstance(child, ast.With):  # `with pytest.raises(...)` counts as a check
            for item in child.items:
                ctx = item.context_expr
                if isinstance(ctx, ast.Call) and getattr(ctx.func, "attr", "") in ASSERT_NAMES:
                    count += 1
    return count


def _tautology(node: ast.Assert) -> str | None:
    test = node.test
    if isinstance(test, ast.Constant) and test.value is True:
        return "assert True"
    if isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq):
        left, right = ast.dump(test.left), ast.dump(test.comparators[0])
        if left == right:
            return "compares an expression with itself"
    return None


def weak_test_findings(files: list[Path], root: Path) -> list[str]:
    found: list[str] = []
    for path in files:
        if not _is_test_file(path):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            continue
        shown = (
            path.resolve().relative_to(root.resolve()).as_posix()
            if path.resolve().is_relative_to(root.resolve())
            else path.name
        )
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) or not node.name.startswith(
                "test"
            ):
                continue
            checks = _asserts(node)
            mocks = sum(
                1
                for n in ast.walk(node)
                if isinstance(n, ast.Name) and n.id in ("patch", "MagicMock", "Mock")
            )
            if checks == 0 and not any(
                isinstance(d, ast.Attribute) and d.attr == "skip" for d in node.decorator_list
            ):
                found.append(f"tests: {shown}:{node.lineno}: {node.name} has no assertion, so it cannot fail")
            for child in ast.walk(node):
                if isinstance(child, ast.Assert):
                    why = _tautology(child)
                    if why:
                        found.append(
                            f"tests: {shown}:{child.lineno}: {why}: this passes whatever the code does"
                        )
            if mocks >= 3 and checks <= 1:
                found.append(
                    f"tests: {shown}:{node.lineno}: {node.name} mocks {mocks} things and checks little: it may only test the mocks"
                )
    return found


# --- mutation check ---

SWAPS: dict[type, type] = {
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.GtE, ast.LtE: ast.Gt, ast.Gt: ast.LtE, ast.GtE: ast.Lt,
    ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.FloorDiv, ast.And: ast.Or, ast.Or: ast.And, ast.In: ast.NotIn, ast.NotIn: ast.In,
}  # fmt: skip


@dataclass
class Mutant:
    line: int
    description: str
    source: str


def make_mutants(source: str, limit: int = MAX_MUTANTS) -> list[Mutant]:
    """Small deliberate mistakes, one per mutant, spread over the file (the first of each kind per function first)."""
    tree = ast.parse(source)
    sites: list[tuple[int, str, Any, str]] = []  # line, description, node, kind
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in SWAPS:
            sites.append(
                (
                    node.lineno,
                    f"flipped `{type(node.ops[0]).__name__}` to `{SWAPS[type(node.ops[0])].__name__}`",
                    node,
                    "cmp",
                )
            )
        elif isinstance(node, ast.BinOp) and type(node.op) in SWAPS:
            sites.append(
                (
                    node.lineno,
                    f"changed `{type(node.op).__name__}` to `{SWAPS[type(node.op)].__name__}`",
                    node,
                    "bin",
                )
            )
        elif isinstance(node, ast.BoolOp) and type(node.op) in SWAPS:
            sites.append(
                (
                    node.lineno,
                    f"changed `{type(node.op).__name__}` to `{SWAPS[type(node.op)].__name__}`",
                    node,
                    "bool",
                )
            )
        elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
            sites.append((node.lineno, f"changed `{node.value}` to `{not node.value}`", node, "const"))
        elif (
            isinstance(node, ast.Return)
            and node.value is not None
            and not (isinstance(node.value, ast.Constant) and node.value.value is None)
        ):
            sites.append((node.lineno, "made the function return None", node, "ret"))
    step = max(1, len(sites) // limit)
    chosen = sites[::step][:limit]
    mutants: list[Mutant] = []
    for line, description, site, kind in chosen:
        fresh = ast.parse(source)
        target: Any = next(
            (
                n
                for n in ast.walk(fresh)
                if type(n) is type(site)
                and getattr(n, "lineno", -1) == line
                and getattr(n, "col_offset", -1) == getattr(site, "col_offset", -2)
            ),
            None,
        )
        if target is None:
            continue
        if kind == "cmp":
            target.ops = [SWAPS[type(target.ops[0])]()]
        elif kind in ("bin", "bool"):
            target.op = SWAPS[type(target.op)]()
        elif kind == "const":
            target.value = not target.value
        else:
            target.value = ast.Constant(value=None)
        mutants.append(Mutant(line, description, ast.unparse(ast.fix_missing_locations(fresh))))
    return mutants


def run_mutation_check(
    path: Path, root: Path, python: str, test_args: list[str], env: dict[str, str] | None = None
) -> tuple[int, list[Mutant]]:
    """(mutants tried, the ones the tests did not catch). The file is restored whatever happens."""
    original = path.read_text(encoding="utf-8")
    mutants = make_mutants(original)
    survivors: list[Mutant] = []
    try:
        for mutant in mutants:
            path.write_text(mutant.source, encoding="utf-8")
            try:
                done = subprocess.run(
                    [python, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *test_args],
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=TEST_TIMEOUT_S,
                )
            except subprocess.TimeoutExpired:
                continue  # a mutant that hangs the tests was noticed (the tests did not pass)
            if done.returncode == 0:
                survivors.append(mutant)
    finally:
        path.write_text(original, encoding="utf-8")
    return len(mutants), survivors


class MutationCheck(Tool):
    name = "mutation_check"
    read_only = False  # it briefly edits the file and always restores it
    description = (
        "Check that your tests really test a source file: it makes a few small deliberate mistakes in the file one at a time (a flipped "
        "comparison, + for -, True for False, a function returning None), runs the tests after each, and reports the mistakes the tests "
        "did NOT notice: those are places no test checks. Add a test for each surviving mistake that matters. The file is restored. Run "
        "it on a module you wrote when its logic has edges (limits, comparisons, calculations); it costs a few test runs."
    )

    class Args(ToolArgs):
        path: str = Field(
            description="The source file to mutate, relative to the repository root (not a test file)"
        )
        tests: str = Field(
            default="",
            description="Which tests to run, as pytest arguments (a file, a folder, -k expr); default all tests",
        )

    def summary(self, args: MutationCheck.Args) -> str:
        return f"mutation check {args.path}"

    async def run(self, args: MutationCheck.Args, context: ToolContext) -> ToolResult:
        import asyncio
        import shlex

        file = context.workspace.path_of(args.path)
        if not file.is_file() or file.suffix != ".py" or _is_test_file(file):
            return ToolResult(ok=False, content="Give a Python source file (not a test file).")
        env = context.workspace.info.python_env
        python = env.python if env is not None and env.python else None
        if not python:
            return ToolResult(ok=False, content="No Python environment is set up for this workspace yet.")
        root = Path(env.app_dir) if env is not None and env.app_dir else context.workspace.root
        tried, survivors = await asyncio.to_thread(
            run_mutation_check, file, root, python, shlex.split(args.tests)
        )
        if tried == 0:
            return ToolResult(
                ok=True,
                content="Nothing to mutate in that file (no comparisons, arithmetic, booleans or returns).",
            )
        if not survivors:
            return ToolResult(ok=True, content=f"All {tried} deliberate mistakes were caught by the tests.")
        lines = [
            f"- line {m.line}: {m.description}, and the tests still passed: nothing checks this"
            for m in survivors
        ]
        return ToolResult(
            ok=True,
            content=f"{len(survivors)} of {tried} deliberate mistakes went unnoticed by the tests:\n"
            + "\n".join(lines)
            + "\nAdd tests that fail for these, then run the check again.",
        )

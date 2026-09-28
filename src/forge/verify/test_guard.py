"""Deterministic check that the agent didn't make tests pass by weakening them (spec §13.2): compares every
changed test file with its baseline. Existing tests may gain assertions, never lose them; they may not be
deleted, skipped or marked xfail; and trivially-true assertions don't count as tests."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from forge.workspace.output import compute_changes, file_texts
from forge.workspace.workspace import Workspace

SKIP_MARKERS = ("skip", "skipif", "xfail")


@dataclass
class GuardFinding:
    path: str
    test: str
    problem: str
    blocking: bool = True

    def render(self) -> str:
        level = "blocking" if self.blocking else "minor"
        return f"[{level}] {self.path}::{self.test}: {self.problem}"


@dataclass
class _TestInfo:
    assertions: int
    skipped: bool
    trivial: int


def check_tests(workspace: Workspace) -> list[GuardFinding]:
    findings: list[GuardFinding] = []
    for change in compute_changes(workspace):
        if not _is_test_path(change.path) or change.secret:
            continue
        before_text, after_text = file_texts(workspace, change)
        before, after = _tests_in(before_text), _tests_in(after_text)
        if change.status == "deleted" and before:
            findings.append(GuardFinding(change.path, "*", "an existing test file was deleted"))
            continue
        for name, old in before.items():
            new = after.get(name)
            if new is None:
                findings.append(GuardFinding(change.path, name, "an existing test was removed or renamed"))
                continue
            if new.skipped and not old.skipped:
                findings.append(GuardFinding(change.path, name, "an existing test is now skipped or xfail"))
            if new.assertions < old.assertions:
                findings.append(
                    GuardFinding(
                        change.path, name, f"assertions went from {old.assertions} to {new.assertions}"
                    )
                )
            if new.trivial > old.trivial:
                findings.append(GuardFinding(change.path, name, "a trivially-true assertion was added"))
        for name, new in after.items():
            if name in before:
                continue
            if new.assertions == 0:
                findings.append(GuardFinding(change.path, name, "new test asserts nothing", blocking=False))
            elif new.trivial >= new.assertions:
                findings.append(GuardFinding(change.path, name, "new test only asserts constants"))
    return findings


def _is_test_path(path: str) -> bool:
    name = PurePosixPath(path).name
    return name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py"))


def _tests_in(source: str) -> dict[str, _TestInfo]:
    if not source.strip():
        return {}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    tests: dict[str, _TestInfo] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            class_skipped = _decorated_skip(node)
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef) and item.name.startswith("test"):
                    info = _info(item)
                    info.skipped = info.skipped or class_skipped
                    tests[f"{node.name}.{item.name}"] = info
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith("test"):
            tests[node.name] = _info(node)
    return tests


def _info(function: ast.FunctionDef | ast.AsyncFunctionDef) -> _TestInfo:
    assertions = trivial = 0
    skipped = _decorated_skip(function)
    for node in ast.walk(function):
        if isinstance(node, ast.Assert):
            assertions += 1
            if isinstance(node.test, ast.Constant) and node.test.value:
                trivial += 1
        elif isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name.endswith(("raises", "warns")) or name.split(".")[-1].startswith("assert"):
                assertions += 1
            if name in ("pytest.skip", "pytest.xfail", "self.skipTest"):
                skipped = True
    return _TestInfo(assertions, skipped, trivial)


def _decorated_skip(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> bool:
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        name = _call_name(target)
        if name.split(".")[-1] in SKIP_MARKERS or name.endswith("unittest.skip"):
            return True
    return False


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_call_name(node.value)}.{node.attr}"
    return ""


# Seen live: the CLI's "real" clients were fakes ("not intended for production", a "stub invocation" used by
# the CLI); every test passed against fakes and the reviewer missed it. Tests may fake integrations; delivered
# code may not. ("Tests can monkeypatch this" is NOT a marker: it describes testable real code.)
_STUB_MARKERS = re.compile(
    r"not (?:intended|meant|suitable) for production|stub (?:implementation|invocation|client)"
    r"|placeholder implementation|without contacting any (?:external|real)"
    r"|replace (?:this|with) (?:a |the )?real (?:implementation|client|call)|todo:? implement",
    re.IGNORECASE,
)


def check_stubs(workspace: Workspace) -> list[GuardFinding]:
    """Stub/placeholder markers in added or changed non-test Python files: the requirement's integration was
    faked in the code that ships."""
    findings: list[GuardFinding] = []
    for change in compute_changes(workspace):
        path = PurePosixPath(change.path)
        if change.status == "deleted" or change.secret or path.suffix != ".py" or _is_test_path(change.path):
            continue
        if "tests" in path.parts or path.name == "conftest.py":
            continue
        _, after_text = file_texts(workspace, change)
        for number, line in enumerate(after_text.splitlines(), start=1):
            match = _STUB_MARKERS.search(line)
            if match:
                findings.append(
                    GuardFinding(
                        f"{change.path}:{number}",
                        "production code",
                        f"looks like a stub or placeholder ('{match.group(0)}'): implement the real "
                        "behaviour the requirement asks for; only tests may use fakes",
                    )
                )
                break
    return findings

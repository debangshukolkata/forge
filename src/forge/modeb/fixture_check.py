"""Mode B review check: delivered tests that use the host's database/app setup without the host's fixtures.

Seen in every live Mode B run: contract tests called `session_scope()` (directly, or through the new service
that uses it) with no fixture. The harness stub worked on import; in the real host the engine is only set up
by the app fixture, so the tests failed there ("engine is not initialised") and cost a revision round.

Rule: a test in project/ that uses a host infrastructure symbol (from a host `db`/`database`/`session`/
`extensions` module, or named like `session_scope`/`get_db`), or a symbol from a new module that imports one,
must request at least one fixture the harness recreates from the host (harness_conftest.py), unless the
harness has an autouse fixture.
"""

from __future__ import annotations

import ast
from pathlib import Path

from forge.verify.test_guard import GuardFinding
from forge.workspace.workspace import Workspace

INFRA_MODULES = {"db", "database", "session", "sessions", "extensions"}
INFRA_NAMES = {
    "session_scope",
    "get_session",
    "get_db",
    "get_engine",
    "init_engine",
    "engine",
    "SessionLocal",
}


def check_fixture_use(workspace: Workspace) -> list[GuardFinding]:
    if not workspace.mode_b:
        return []
    fixtures, autouse = _harness_fixtures(workspace.harness_dir / "harness_conftest.py")
    if not fixtures or autouse:
        return []
    project = workspace.repo_dir
    infra_symbols = _infra_using_modules(project)
    findings = []
    for test_file in sorted(project.rglob("test_*.py")):
        tree = _parse(test_file)
        if tree is None:
            continue
        risky = _risky_names(tree, infra_symbols)
        for function in tree.body:
            if not isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if not function.name.startswith("test"):
                continue
            parameters = {a.arg for a in function.args.args}
            used = sorted({n.id for n in ast.walk(function) if isinstance(n, ast.Name)} & risky)
            if used and not parameters & fixtures:
                findings.append(
                    GuardFinding(
                        test_file.relative_to(project).as_posix(),
                        function.name,
                        f"uses {', '.join(used)} (the host's database/app setup) without any host fixture "
                        f"({', '.join(sorted(fixtures))}); in the host that setup only exists inside those "
                        "fixtures, even if the stub works without them — request the fixture that sets it up",
                    )
                )
    return findings


def _harness_fixtures(conftest: Path) -> tuple[set[str], bool]:
    tree = _parse(conftest)
    names, autouse = set(), False
    for node in tree.body if tree else []:
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            text = ast.unparse(decorator)
            if "fixture" in text:
                names.add(node.name)
                autouse = autouse or "autouse=True" in text
    return names, autouse


def _infra_using_modules(project: Path) -> set[str]:
    """`module.function` for each top-level function/class of the new (non-test) modules that uses host
    infrastructure (a pure helper next to it doesn't count)."""
    symbols = set()
    for path in project.rglob("*.py"):
        if path.name.startswith("test_") or "tests" in path.relative_to(project).parts:
            continue
        tree = _parse(path)
        if tree is None:
            continue
        infra = _infra_imports(tree)
        if not infra:
            continue
        module = ".".join(path.relative_to(project).with_suffix("").parts)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                used = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
                if used & infra:
                    symbols.add(f"{module}.{node.name}")
    return symbols


def _infra_imports(tree: ast.Module) -> set[str]:
    """Local names bound to host infrastructure by `from … import …`."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            module_is_infra = node.module.split(".")[-1] in INFRA_MODULES
            for alias in node.names:
                if module_is_infra or alias.name in INFRA_NAMES:
                    names.add(alias.asname or alias.name)
    return names


def _risky_names(tree: ast.Module, infra_symbols: set[str]) -> set[str]:
    names = _infra_imports(tree)
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if f"{node.module}.{alias.name}" in infra_symbols:
                    names.add(alias.asname or alias.name)
    return names


def _parse(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None

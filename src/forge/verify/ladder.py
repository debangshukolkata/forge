"""The verify ladder (spec §13.1) after edits: compile the changed files, lint and type-check them with the
repo's own tools (only when the repo uses them), run the tests for the touched modules, and — at phase end —
the full suite. Each rung reports a compact, parsed summary; the first failing rung stops the climb, since
later rungs would only repeat the same problem."""

from __future__ import annotations

import asyncio
import configparser
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from forge.db.table_check import TableCheck, check_tables
from forge.tools.base import ToolContext
from forge.tools.powershell import ps_quote
from forge.tools.shell import execute
from forge.verify.parsers import (
    TestReport,
    error_signature,
    parse_compile,
    parse_lint,
    parse_mypy,
    parse_pytest,
    render_diagnostics,
)
from forge.workspace.output import compute_changes

# No -q: repos often set it in addopts, and -qq hides the summary line the parser reads.
PYTEST_ARGS = "-rfE --tb=short --no-header -p no:cacheprovider"
STEP_TIMEOUT_S = 300
FULL_SUITE_TIMEOUT_S = 900


@dataclass
class StepResult:
    name: str
    ok: bool
    summary: str
    skipped: bool = False


@dataclass
class LadderReport:
    steps: list[StepResult] = field(default_factory=list)
    tests: TestReport | None = None
    signature: str | None = None

    @property
    def ok(self) -> bool:
        return all(step.ok for step in self.steps)

    def render(self) -> str:
        lines = []
        for step in self.steps:
            mark = "skipped" if step.skipped else ("ok" if step.ok else "FAILED")
            lines.append(f"[{mark}] {step.name}: {step.summary}")
        verdict = "All checks passed." if self.ok else "Fix the first failing check and run verify again."
        return "\n".join([*lines, verdict])


def changed_python_files(context: ToolContext) -> list[str]:
    """App-relative paths of added/modified .py files (baseline diff, so shell edits count too)."""
    app = context.workspace.info.app_subfolder.strip("/")
    prefix = f"{app}/" if app else ""
    return sorted(
        change.path[len(prefix) :]
        for change in compute_changes(context.workspace)
        if change.status != "deleted" and change.path.endswith(".py") and change.path.startswith(prefix)
    )


class VerifyLadder:
    def __init__(self, context: ToolContext) -> None:
        assert context.shell is not None
        self.context = context
        self.app_dir = context.workspace.app_dir
        self.app_subfolder = context.workspace.info.app_subfolder or None
        self.python = context.shell.python or "python"

    async def run(self, full: bool = False, paths: list[str] | None = None) -> LadderReport:
        report = LadderReport()
        files = paths if paths is not None else changed_python_files(self.context)
        code = [f for f in files if not _is_test_file(f)]
        for rung in (self._compile, self._lint, self._typecheck):
            step = await rung(files)
            report.steps.append(step)
            if not step.ok:
                report.signature = step.summary
                return report
        selector = self.targeted_tests(files, code)
        if full:
            step, report.tests = await self._pytest("full test suite", "", FULL_SUITE_TIMEOUT_S)
        elif selector:
            step, report.tests = await self._pytest("tests for touched modules", selector, STEP_TIMEOUT_S)
        elif code:  # nothing points at the change: the whole suite rather than no evidence
            step, report.tests = await self._pytest(
                "full test suite (no targeted tests found)", "", FULL_SUITE_TIMEOUT_S
            )
        else:
            step = StepResult("tests", True, "no tests found for the touched modules; add some", skipped=True)
        report.steps.append(step)
        if not step.ok:
            report.signature = error_signature(step.summary)
        return report

    async def run_tests(self, selector: str) -> tuple[StepResult, TestReport]:
        return await self._pytest("tests", selector, FULL_SUITE_TIMEOUT_S if not selector else STEP_TIMEOUT_S)

    # --- rungs ---

    async def _compile(self, files: list[str]) -> StepResult:
        if not files:
            return StepResult("compile", True, "no changed Python files", skipped=True)
        output, ok = await self._run(f"-m py_compile {_quoted(files)}", STEP_TIMEOUT_S)
        if ok:
            return StepResult("compile", True, f"{len(files)} file(s) compile")
        return StepResult(
            "compile", False, render_diagnostics("compile", parse_compile(output)) or output[-800:]
        )

    async def _lint(self, files: list[str]) -> StepResult:
        tool = self._configured("ruff") or self._configured("flake8")
        if tool is None or not files:
            return StepResult("lint", True, "the repo has no ruff/flake8 setup in this venv", skipped=True)
        command = f"-m ruff check {_quoted(files)}" if tool == "ruff" else f"-m flake8 {_quoted(files)}"
        output, ok = await self._run(command, STEP_TIMEOUT_S)
        return StepResult(f"lint ({tool})", ok, render_diagnostics(tool, parse_lint(output)))

    async def _typecheck(self, files: list[str]) -> StepResult:
        code = [f for f in files if not _is_test_file(f)]
        if self._configured("mypy") is None or not code:
            return StepResult("mypy", True, "the repo doesn't use mypy", skipped=True)
        output, ok = await self._run(f"-m mypy {_quoted(code)}", STEP_TIMEOUT_S)
        return StepResult("mypy", ok, render_diagnostics("mypy", parse_mypy(output)))

    async def _pytest(self, name: str, selector: str, timeout_s: int) -> tuple[StepResult, TestReport]:
        harness = " -p harness_conftest" if self.context.workspace.mode_b else ""  # Mode B stand-ins
        if self.context.workspace.mode_b:
            from forge.modeb.workspace import ensure_shared_stub_packages

            ensure_shared_stub_packages(self.context.workspace)
        table_note = ""
        tables = await self._table_check()
        if tables is not None and tables.refusal:
            return StepResult(name, False, tables.refusal), TestReport()
        if tables is not None and tables.missing:
            table_note = tables.note(self.context.db.scratch.schema) + "\n"
        output, exited_ok = await self._run(
            f"-m pytest {PYTEST_ARGS}{harness} {selector}".rstrip(), timeout_s
        )
        tests = parse_pytest(output)
        if tests.ran:
            ok, summary = tests.passed, tests.summary()
        else:  # no summary line (e.g. -qq in the repo's addopts): the exit code decides
            ok, summary = exited_ok, ("pytest passed" if exited_ok else output[-1200:])
        nothing_ran = "no tests ran" in output or "collected 0 items" in output
        collection_errors = "ERROR collecting" in output or re.search(r"\b\d+ errors?\b", output)
        if not ok and nothing_ran and collection_errors:
            # Seen live: "no tests ran, 1 error" read as "write tests" sent the agent round in circles.
            summary = (
                "pytest could not COLLECT the tests (import or setup errors below): fix those first; "
                "don't write more tests.\n" + _collection_errors(output) + summary[-400:]
            )
        elif not ok and nothing_ran:
            app = self.context.workspace.info.app_subfolder
            where = f"pytest runs in {app}/, so tests must live under {app}/tests/. " if app else ""
            summary = (
                f"pytest found NO tests to run. {where}Write tests for the code you changed (in the "
                "project's test style), then run verify again: the change isn't verified without them.\n"
                + summary[-400:]
            )
        return StepResult(name, ok, table_note + summary), tests

    async def _table_check(self) -> TableCheck | None:
        """Spec §9.5: tables the code uses must exist in the scratch schema before DB-backed runs."""
        try:
            return await asyncio.to_thread(check_tables, self.context.workspace, self.context.db)
        except Exception:  # an unreachable DB mustn't stop the tests; they report it themselves
            return None

    async def _run(self, arguments: str, timeout_s: int) -> tuple[str, bool]:
        result = await execute(
            self.context, f"& {ps_quote(self.python)} {arguments}", timeout_s, self.app_subfolder
        )
        return result.content, result.ok

    # --- discovery ---

    def targeted_tests(self, files: list[str], code: list[str]) -> str:
        """Changed test files; tests importing a touched module or anything that (transitively) imports it;
        and tests whose file name shares a word with those modules (API tests reach services through the
        client, not by import: claims_service -> claims/routes -> test_claims_api)."""
        tests = {f for f in files if _is_test_file(f) and Path(f).name != "conftest.py"}
        # A changed conftest affects every test beside and below it.
        tests |= {Path(f).parent.as_posix() for f in files if Path(f).name == "conftest.py"}
        affected = self._affected_modules([_dotted(f) for f in code if Path(f).stem != "__init__"])
        if not affected:
            return _quoted(sorted(tests))
        words = {w for module in affected for w in _name_words(module)}
        for test_file in self._test_files():
            relative = test_file.relative_to(self.app_dir).as_posix()
            imports = _imports(test_file.read_text(encoding="utf-8", errors="replace"))
            by_import = any(module in imports for module in affected)
            by_name = bool(
                words & set(_name_words(test_file.stem.removeprefix("test_").removesuffix("_test")))
            )
            if by_import or by_name:
                tests.add(relative)
        return _quoted(sorted(tests))

    def _affected_modules(self, changed: list[str]) -> set[str]:
        """The changed modules plus app modules importing them, up to three levels (the app factory and
        package __init__ files import everything, so they don't propagate)."""
        importers: dict[str, set[str]] = {}
        for path in self.app_dir.rglob("*.py"):
            parts = path.relative_to(self.app_dir).parts
            if (
                "venv" in parts
                or parts[0].startswith(".")
                or _is_test_file(path.name)
                or path.stem == "__init__"
            ):
                continue
            module = _dotted(path.relative_to(self.app_dir).as_posix())
            for imported in _imported_modules(path.read_text(encoding="utf-8", errors="replace")):
                importers.setdefault(imported, set()).add(module)
        affected, frontier = set(changed), set(changed)
        for _ in range(3):
            frontier = {
                importer
                for module in frontier
                for name, users in importers.items()
                if name == module or name.startswith(module + ".") or module.startswith(name + ".")
                for importer in users
            } - affected
            affected |= frontier
        return affected

    def _test_files(self) -> list[Path]:
        return [
            path
            for path in self.app_dir.rglob("*.py")
            if _is_test_file(path.name) and path.name != "conftest.py" and "venv" not in path.parts
        ]

    def _configured(self, tool: str) -> str | None:
        """The tool when the repo configures it AND it is installed in the app's venv."""
        if not _installed(self.context, tool):
            return None
        roots = {self.app_dir, self.context.workspace.repo_dir}
        for root in roots:
            pyproject = root / "pyproject.toml"
            if pyproject.exists():
                try:
                    if tool in tomllib.loads(pyproject.read_text(encoding="utf-8")).get("tool", {}):
                        return tool
                except tomllib.TOMLDecodeError:
                    pass
            dedicated = {
                "ruff": ["ruff.toml", ".ruff.toml"],
                "flake8": [".flake8"],
                "mypy": ["mypy.ini", ".mypy.ini"],
            }
            if any((root / name).exists() for name in dedicated[tool]):
                return tool
            for name in ("setup.cfg", "tox.ini"):
                parser = configparser.ConfigParser()
                if (root / name).exists():
                    try:
                        parser.read(root / name, encoding="utf-8")
                    except configparser.Error:
                        continue
                    if parser.has_section(tool):
                        return tool
        return None


def _installed(context: ToolContext, module: str) -> bool:
    env = context.workspace.info.python_env
    if env is None:
        return False
    venv = Path(env.venv)
    candidates = [venv / "Lib" / "site-packages" / module, *venv.glob(f"lib/python*/site-packages/{module}")]
    return any(path.exists() for path in candidates)


def _is_test_file(path: str) -> bool:
    name = Path(path).name
    return name.endswith(".py") and (
        name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"
    )


GENERIC_WORDS = {
    "api",
    "app",
    "routes",
    "route",
    "views",
    "view",
    "service",
    "services",
    "repository",
    "repositories",
    "repo",
    "schemas",
    "schema",
    "models",
    "model",
    "utils",
    "helpers",
    "core",
    "common",
    "base",
    "db",
    "init",
}


def _name_words(module: str) -> list[str]:
    """Meaningful words of a module path: claims_app.services.claims_service -> ['claims']."""
    parts = module.lower().split(".")
    below_top = parts[1:] if len(parts) > 1 else parts  # the package name itself says nothing
    words = [w for part in below_top for w in part.split("_")]
    return [w for w in words if w and w not in GENERIC_WORDS]


def _imports(source: str) -> str:
    return "\n".join(line for line in source.splitlines() if re.match(r"\s*(from|import)\s", line))


def _imported_modules(source: str) -> set[str]:
    modules = set()
    for line in source.splitlines():
        match = re.match(r"\s*from\s+([\w.]+)\s+import\s+(.+)", line)
        if match:
            base = match.group(1)
            modules.add(base)
            for name in re.findall(r"\w+", match.group(2).split("#")[0]):
                modules.add(f"{base}.{name}")
            continue
        match = re.match(r"\s*import\s+([\w.]+)", line)
        if match:
            modules.add(match.group(1))
    return modules


def _dotted(path: str) -> str:
    return path.removesuffix(".py").replace("/", ".")


def _quoted(paths: list[str]) -> str:
    return " ".join(ps_quote(p) for p in paths)


def _collection_errors(output: str) -> str:
    """The 'E ...' lines of each collection error: the summary line alone ('1 error') says nothing."""
    lines = [line for line in output.splitlines() if line.startswith(("ERROR collecting", "E   "))]
    return "\n".join(lines[:20]) + ("\n" if lines else "")

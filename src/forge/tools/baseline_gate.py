"""Run the existing tests once before the first change to existing code (D-408).

The approach challenges of 2026-10-15 (docs/CODE_BENCHMARK.md, "Approach challenges") showed a pricing function rewritten in one step with no test run before it: nobody knew
whether the starting point was green, and a refactor had nothing to compare against. The first edit of an existing source file in a project that has tests is refused once, with the
reason; it is allowed after any test run (pass or fail), after a test file was written, or after this one refusal, so it never traps the model."""

from __future__ import annotations

from pathlib import Path

from forge.toolkit.base import ToolContext

SOURCE_SUFFIXES = (".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".cs", ".rb", ".php")
TEST_NAME_PARTS = ("test_", "_test.", ".test.", ".spec.", "conftest")

MESSAGE = (
    "Not saved yet: this project has tests and you have not run them. Run the existing tests once (python -m pytest, or the project's own command) so you know the starting point is "
    "green, and for a refactor write tests that pin the current behaviour first (or keep the old function beside the new one as an oracle and compare them on many inputs). "
    "Then repeat this edit; it will be accepted."
)


def is_test_file(relative: str) -> bool:
    normalised = relative.replace("\\", "/").lower()
    name = Path(normalised).name
    return (
        any(part in name for part in TEST_NAME_PARTS)
        or "/tests/" in f"/{normalised}"
        or "/__tests__/" in f"/{normalised}"
    )


def project_has_tests(context: ToolContext) -> bool:
    root = context.workspace.repo_dir
    for pattern in (
        "test_*.py",
        "*_test.py",
        "*.test.ts",
        "*.test.tsx",
        "*.test.js",
        "*.spec.ts",
        "*.spec.js",
    ):
        if next(
            (p for p in root.rglob(pattern) if "node_modules" not in p.parts and ".venv" not in p.parts), None
        ):
            return True
    return False


def baseline_gate(context: ToolContext, relative: str, existing: bool) -> str:
    """The refusal text for the first edit of an existing source file before any test run, else an empty string. Also notes a test file being written."""
    if is_test_file(relative):
        context.baseline_checked = True
        context.tests_pinned = True
        return ""
    if (
        not context.require_baseline
        or context.baseline_checked
        or context.write_only_under is not None
        or not existing
    ):
        return ""
    if not relative.lower().endswith(SOURCE_SUFFIXES):
        return ""
    context.baseline_checked = True  # one refusal at most
    return MESSAGE if project_has_tests(context) else ""


REWRITE_MESSAGE = (
    "Not saved yet: this replaces most of an existing file in one step and no test has been written in this session. When behaviour must not change, pin it first: write tests with one case "
    "per branch (expected values from running the current code, odd corners included) or keep the old function under another name beside the new one and compare them on many inputs; then change the "
    "code in steps with multi_edit and run the tests after each. Then repeat this write; it will be accepted."
)
REWRITE_SHARE = 0.5  # lines kept below this share count as a rewrite


def rewrite_gate(context: ToolContext, relative: str, before: str, after: str) -> str:
    """The refusal text, once per session, for a write_file that replaces most of an existing source file before any test was written; else an empty string (D-410)."""
    import difflib

    if (
        not context.require_baseline
        or context.tests_pinned
        or context.rewrite_asked
        or context.write_only_under is not None
    ):
        return ""
    if not before.strip() or is_test_file(relative) or not relative.lower().endswith(SOURCE_SUFFIXES):
        return ""
    if (
        len(before.splitlines()) < 30
    ):  # a short file is cheap to redo; the reminder is for logic that has grown
        return ""
    kept = difflib.SequenceMatcher(None, before.splitlines(), after.splitlines(), autojunk=False).ratio()
    if kept >= REWRITE_SHARE:
        return ""
    context.rewrite_asked = True
    return REWRITE_MESSAGE

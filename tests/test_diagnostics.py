"""HW4: the syntax check after an edit covers JSON, JavaScript and TypeScript (no model involved).

The Node checks run through the sandboxed command path; they are tested only where `node` exists."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from forge.toolkit.base import ToolContext
from forge.toolkit.shell import ShellSession
from forge.tools.diagnostics import diagnose_file
from forge.workspace.create import create_workspace

HAS_NODE = shutil.which("node") is not None
needs_node = pytest.mark.skipif(not HAS_NODE, reason="node is not on the PATH")
REAL_TYPESCRIPT = next(
    (
        path
        for path in Path(__file__).resolve().parents[1].glob("ui-react/node_modules/typescript/bin/tsc")
        if path.is_file()
    ),
    None,
)


@pytest.fixture
def context(original_repo: Path, tmp_path: Path) -> ToolContext:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend", max_file_mb=1)
    return ToolContext(workspace=workspace, shell=ShellSession(workspace))


def _write(context: ToolContext, relative: str, text: str) -> None:
    path = context.workspace.path_of(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


async def test_valid_json_passes_and_broken_json_reports_line_and_column(context: ToolContext) -> None:
    _write(context, "backend/data.json", '{"a": 1}\n')
    _write(context, "backend/broken.json", '{\n  "a": 1,\n  "b": \n}\n')

    assert await diagnose_file(context, "backend/data.json") is None
    report = await diagnose_file(context, "backend/broken.json")
    assert report is not None and report.startswith("Syntax check FAILED:") and "line 4, column 1" in report


async def test_json_that_may_have_comments_is_not_checked(context: ToolContext) -> None:
    broken_with_comment = '{\n  // the compiler options\n  "a": 1,\n}\n'
    for name in ("backend/tsconfig.json", "backend/tsconfig.app.json", "backend/.eslintrc.json"):
        _write(context, name, broken_with_comment)
        assert await diagnose_file(context, name) is None
    _write(context, ".vscode/settings.json", broken_with_comment)
    assert await diagnose_file(context, ".vscode/settings.json") is None
    _write(context, "backend/other.json", broken_with_comment)  # any file with // or /* is left alone
    assert await diagnose_file(context, "backend/other.json") is None


@needs_node
async def test_a_javascript_file_with_a_broken_bracket_is_reported(context: ToolContext) -> None:
    _write(context, "backend/bad.js", "function f() {\n  return [1, 2;\n}\n")
    _write(context, "backend/good.js", "function f() {\n  return [1, 2];\n}\nmodule.exports = f;\n")

    report = await diagnose_file(context, "backend/bad.js")
    assert report is not None and report.startswith("Syntax check FAILED:") and "SyntaxError" in report
    assert await diagnose_file(context, "backend/good.js") is None


async def test_javascript_is_skipped_when_there_is_no_shell(context: ToolContext) -> None:
    _write(context, "backend/bad.js", "function f() {\n  return [1, 2;\n}\n")
    context.shell = None

    assert await diagnose_file(context, "backend/bad.js") is None


async def test_typescript_without_a_project_compiler_is_skipped_silently(context: ToolContext) -> None:
    _write(context, "backend/a.ts", "const x: number = ;\n")

    assert await diagnose_file(context, "backend/a.ts") is None


STUB_TSC = """
const file = process.argv[process.argv.length - 1];
console.log(`${file}(3,5): error TS1005: ';' expected.`);
console.log(`${file}(1,8): error TS2307: Cannot find module 'react'.`);
process.exit(2);
"""


@needs_node
async def test_only_syntax_errors_of_tsc_are_reported_through_the_sandboxed_shell(
    context: ToolContext,
) -> None:
    """Plumbing and the filter: a stand-in launcher prints a syntax error and a missing-module error."""
    _write(context, "backend/node_modules/typescript/bin/tsc", STUB_TSC)
    _write(context, "backend/src/bad.ts", "const BROKEN = ;\n")

    report = await diagnose_file(context, "backend/src/bad.ts")
    assert report == "Syntax check FAILED:\n3:5 ';' expected."


@needs_node
async def test_a_type_error_alone_is_not_reported(context: ToolContext) -> None:
    _write(
        context,
        "backend/node_modules/typescript/bin/tsc",
        "console.log(process.argv.at(-1) + \"(1,8): error TS2307: Cannot find module 'x'.\");process.exit(2);",
    )
    _write(context, "backend/src/a.ts", "import x from 'x';\n")

    assert await diagnose_file(context, "backend/src/a.ts") is None


@needs_node
@pytest.mark.skipif(REAL_TYPESCRIPT is None, reason="no ui-react/node_modules/typescript/bin/tsc")
async def test_the_real_tsc_finds_a_syntax_error_and_passes_a_good_file(context: ToolContext) -> None:
    assert REAL_TYPESCRIPT is not None
    # the workspace gets a launcher that runs the real compiler of the repository's own front end
    _write(
        context,
        "backend/node_modules/typescript/bin/tsc",
        f"require({REAL_TYPESCRIPT.as_posix()!r});",
    )
    _write(context, "backend/src/bad.ts", "const x: number = ;\n")
    _write(context, "backend/src/good.ts", "export const x: number = 1;\n")

    report = await diagnose_file(context, "backend/src/bad.ts")
    assert report is not None and report.startswith("Syntax check FAILED:\n1:")
    assert await diagnose_file(context, "backend/src/good.ts") is None

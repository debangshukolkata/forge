"""M3: file, search, shell and background tools (no LLM involved)."""

from __future__ import annotations

import json
from pathlib import Path

import psutil
import pytest

from forge.toolkit.background import (
    BackgroundManager,
    ReadBackground,
    StartBackground,
    StopBackground,
    port_open,
)
from forge.toolkit.base import ToolContext, ToolResult
from forge.toolkit.shell import PythonRun, RunCommand, ShellSession
from forge.tools.files import DeleteFile, EditFile, MoveFile, MultiEdit, ReadFile, WriteFile
from forge.tools.registry import ToolRegistry
from forge.tools.search import Glob, Grep, ListDir
from forge.workspace.create import create_workspace
from forge.workspace.workspace import Workspace
from tests.conftest import FIXTURE_BACKEND, FIXTURE_REPO
from tests.workspace_helpers import CRLF_FILE

ERRORS = "backend/claims_app/errors.py"


@pytest.fixture
def context(original_repo: Path, tmp_path: Path) -> ToolContext:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend", max_file_mb=1)
    return ToolContext(workspace=workspace, shell=ShellSession(workspace), background=BackgroundManager())


async def call(tool: object, context: ToolContext, **arguments: object) -> ToolResult:
    args = tool.Args.model_validate(arguments)  # type: ignore[attr-defined]
    result: ToolResult = await tool.run(args, context)  # type: ignore[attr-defined]
    return result


# --- files ---


async def test_read_file_numbers_lines_and_pages(context: ToolContext) -> None:
    result = await call(ReadFile(), context, path=ERRORS, offset=2, limit=3)

    assert result.content.splitlines()[0].startswith("     2\t")
    assert "more lines; read again with offset=5" in result.content


async def test_secret_file_shows_key_names_only(context: ToolContext) -> None:
    result = await call(ReadFile(), context, path="backend/.env")

    assert "JWT_SECRET" in result.content and "BOOTSTRAP_DB_URL" in result.content
    assert "fixture-not-a-real" not in result.content


async def test_edit_requires_a_prior_read_and_detects_changes_on_disk(context: ToolContext) -> None:
    denied = await call(EditFile(), context, path=ERRORS, old_string="Bad Request", new_string="Bad input")
    assert not denied.ok and "have not read" in denied.content

    await call(ReadFile(), context, path=ERRORS)
    path = context.workspace.path_of(ERRORS)
    path.write_text(path.read_text(encoding="utf-8") + "# changed elsewhere\n", encoding="utf-8")
    stale = await call(EditFile(), context, path=ERRORS, old_string="Bad Request", new_string="Bad input")
    assert not stale.ok and "changed on disk" in stale.content

    await call(ReadFile(), context, path=ERRORS)
    ok = await call(EditFile(), context, path=ERRORS, old_string='"Bad Request"', new_string='"Bad input"')
    assert ok.ok and '"Bad input"' in path.read_text(encoding="utf-8")
    again = await call(EditFile(), context, path=ERRORS, old_string='"Bad input"', new_string='"Bad Request"')
    assert again.ok  # its own write counts as seen


async def test_edit_uniqueness_errors_help_the_model(context: ToolContext) -> None:
    await call(ReadFile(), context, path=ERRORS)

    ambiguous = await call(
        EditFile(), context, path=ERRORS, old_string="status_code = ", new_string="code = "
    )
    missing = await call(
        EditFile(), context, path=ERRORS, old_string="class NotFoundErr(ClaimsError):", new_string="x"
    )

    assert "matches 3 places (lines" in ambiguous.content
    assert "Closest lines" in missing.content and "class NotFoundError(ClaimsAppError):" in missing.content
    everywhere = await call(
        EditFile(), context, path=ERRORS, old_string="status_code = ", new_string="code = ", replace_all=True
    )
    assert everywhere.ok


async def test_crlf_file_edit_with_lf_strings(context: ToolContext) -> None:
    await call(ReadFile(), context, path=CRLF_FILE)

    result = await call(
        EditFile(), context, path=CRLF_FILE, old_string="\nVALUE = 1\n", new_string="\nVALUE = 2\n"
    )

    assert result.ok
    assert context.workspace.path_of(CRLF_FILE).read_bytes().endswith(b"\r\nVALUE = 2\r\n")


async def test_multi_edit_is_all_or_nothing(context: ToolContext) -> None:
    await call(ReadFile(), context, path=ERRORS)
    before = context.workspace.path_of(ERRORS).read_bytes()

    failed = await call(
        MultiEdit(),
        context,
        path=ERRORS,
        edits=[
            {"old_string": '"Not Found"', "new_string": '"Missing"'},
            {"old_string": "no such text", "new_string": "x"},
        ],
    )

    assert not failed.ok and failed.content.startswith("Edit 2 failed, nothing was changed")
    assert context.workspace.path_of(ERRORS).read_bytes() == before


async def test_write_file_reports_syntax_errors(context: ToolContext) -> None:
    result = await call(WriteFile(), context, path="backend/claims_app/broken.py", content="def oops(:\n")

    assert result.ok and "Syntax check FAILED" in result.content


async def test_write_file_refuses_to_overwrite_unread_file(context: ToolContext) -> None:
    result = await call(WriteFile(), context, path=ERRORS, content="x = 1\n")

    assert not result.ok and "have not read" in result.content


async def test_delete_and_move(context: ToolContext) -> None:
    await call(
        MoveFile(), context, source="backend/claims_app/llm.py", destination="backend/claims_app/ai/llm.py"
    )
    await call(DeleteFile(), context, path="backend/claims_app/prompts/triage.py")

    assert context.workspace.path_of("backend/claims_app/ai/llm.py").is_file()
    assert not context.workspace.path_of("backend/claims_app/prompts/triage.py").exists()


def test_tool_schemas_are_flat() -> None:
    for spec in ToolRegistry().specs():
        text = json.dumps(spec.parameters)
        assert "$ref" not in text and "$defs" not in text, spec.name
    multi = next(s for s in ToolRegistry().specs() if s.name == "multi_edit")
    assert multi.parameters["properties"]["edits"]["items"]["properties"]["old_string"]["type"] == "string"


# --- search ---


async def test_glob_list_and_grep(context: ToolContext) -> None:
    globbed = await call(Glob(), context, pattern="**/routes.py")
    listed = await call(ListDir(), context, path="backend")
    files = await call(Grep(), context, pattern=r"class \w+Error", glob="*.py")
    lines = await call(
        Grep(), context, pattern="NotFoundError", output_mode="content", path="backend/claims_app"
    )
    counted = await call(Grep(), context, pattern="status_code", output_mode="count")

    assert "backend/claims_app/api/claims/routes.py" in globbed.content.splitlines()
    assert "claims_app/" in listed.content and "venv/" not in listed.content and "logs/" not in listed.content
    assert "backend/claims_app/errors.py" in files.content.splitlines()
    assert any(
        line.startswith("backend/claims_app/errors.py:14:class NotFoundError")
        for line in lines.content.splitlines()
    )
    assert "backend/claims_app/errors.py:5" in counted.content  # 3 class attributes + 2 uses


async def test_grep_hides_secret_contents(context: ToolContext) -> None:
    result = await call(Grep(), context, pattern="JWT_SECRET", output_mode="content", path="backend")

    assert "backend/.env: [secret file: content hidden]" in result.content
    assert "fixture-jwt-secret" not in result.content


# --- shell ---


async def test_run_command_exit_codes_and_persistent_cwd(context: ToolContext) -> None:
    moved = await call(RunCommand(), context, command="cd claims_app; Get-Location")
    listed = await call(RunCommand(), context, command="Get-ChildItem -Name errors.py")
    failed = await call(RunCommand(), context, command='python -c "import sys; sys.exit(3)"')

    assert moved.ok and "[cwd: repo/backend/claims_app]" in moved.content
    assert "errors.py" in listed.content
    assert not failed.ok and "[exit code 3]" in failed.content


async def test_python_run_imports_the_workspace_copy(context: ToolContext) -> None:
    result = await call(
        PythonRun(),
        context,
        args="-c \"import importlib.util as u; print(u.find_spec('claims_app').origin)\"",
    )

    assert result.ok
    assert str(context.workspace.app_dir) in result.content.replace("/", "\\")


async def test_timeout_kills_the_whole_process_tree(context: ToolContext) -> None:
    child = "[sys.executable, '-c', 'import time; time.sleep(120)']"
    script = f"import subprocess, sys, time; subprocess.Popen({child}); time.sleep(120)"
    before = {p.pid for p in psutil.process_iter()}

    result = await call(RunCommand(), context, command=f'python -c "{script}"', timeout_s=3)

    assert not result.ok and "timed out after 3s" in result.content
    leftovers = [
        p
        for p in psutil.process_iter(["pid", "cmdline"])
        if p.pid not in before and "time.sleep(120)" in " ".join(p.info["cmdline"] or [])
    ]
    assert leftovers == []


async def test_long_output_is_capped_and_saved(context: ToolContext) -> None:
    context.shell_cap_tokens = 500

    result = await call(RunCommand(), context, command='1..3000 | ForEach-Object { "line $_" }')

    assert "tokens omitted. Full output: .forge/tool_outputs/" in result.content
    assert result.full_output_path and "line 3000" in Path(result.full_output_path).read_text(
        encoding="utf-8"
    )


# --- background (the real fixture app, with its real venv) ---


@pytest.fixture
def fixture_app_context(tmp_path: Path) -> ToolContext:
    if not (FIXTURE_BACKEND / "venv" / "Scripts" / "python.exe").exists():
        pytest.skip("run scripts/dev/setup_fixture_venv.ps1 first")
    workspace = create_workspace(FIXTURE_REPO, tmp_path / "ws", "backend")
    return ToolContext(workspace=workspace, shell=ShellSession(workspace), background=BackgroundManager())


async def test_flask_app_runs_in_the_background_and_answers(fixture_app_context: ToolContext) -> None:
    context = fixture_app_context
    command = (
        "$env:DATABASE_URL = 'sqlite:///claims.db'; "
        "python -m flask --app claims_app:create_app run --port {port}"
    )
    started = await call(StartBackground(), context, name="api", command=command, timeout_s=60)
    try:
        assert started.ok, started.content
        port = started.meta["port"]
        response = await call(
            RunCommand(),
            context,
            command=f"(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:{port}/openapi.json).StatusCode",
        )
        log = await call(ReadBackground(), context, name="api")
        assert "200" in response.content
        assert "[running]" in log.content
    finally:
        stopped = await call(StopBackground(), context, name="api")
    assert stopped.ok and not port_open(port)


def test_workspace_for_fixture_never_touches_it(fixture_app_context: ToolContext) -> None:
    workspace: Workspace = fixture_app_context.workspace
    assert Path(workspace.info.repo_path) == FIXTURE_REPO.resolve()

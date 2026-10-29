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


async def test_write_file_reports_an_svg_that_will_not_show_as_an_image(context: ToolContext) -> None:
    """D-540: without the SVG namespace the file loads but draws nothing in <img>; the audit only said "broken image"."""
    bare = await call(
        WriteFile(),
        context,
        path="web/hero.svg",
        content='<svg viewBox="0 0 10 10"><rect width="10" height="10"/></svg>',
    )
    good = await call(
        WriteFile(),
        context,
        path="web/ok.svg",
        content='<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"/>',
    )

    assert bare.ok and 'no xmlns="http://www.w3.org/2000/svg"' in bare.content
    assert good.ok and "SVG check" not in good.content


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
    command = "$env:DATABASE_URL = 'sqlite:///claims.db'; python -m flask --app claims_app:create_app run --port {port}"
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


async def test_start_background_starts_in_the_folder_it_is_given(tmp_path: Path, original_repo: Path) -> None:
    """D-248: it used to start wherever an earlier `cd` left the shell, so three dev servers all served one app."""
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace, shell=ShellSession(workspace), background=BackgroundManager())
    for folder in ("design-a", "design-b"):
        workspace.path_of(f"designs/{folder}").mkdir(parents=True)
    await call(RunCommand(), context, command="cd designs/design-b")  # the shell now sits in design-b
    command = 'Write-Output "in $((Get-Location).Path | Split-Path -Leaf)"; Start-Sleep -Seconds 20'
    try:
        started = await call(
            StartBackground(),
            context,
            name="a",
            command=command,
            cwd="designs/design-a",
            ready_pattern="in design-",
            timeout_s=30,
        )
        assert (
            started.ok and "in design-a" in started.content and "design-a" in started.content.split("\n")[0]
        )
        missing = await call(StartBackground(), context, name="x", command="echo hi", cwd="designs/nope")
        assert not missing.ok and "No such folder" in missing.content
    finally:
        await call(StopBackground(), context, name="a")


@pytest.mark.parametrize(
    "command,port",
    [
        ("python -m http.server 8000", 8000),
        ("python -m http.server --bind 127.0.0.1 8123", None),
        ("npm run dev -- --port 5174", 5174),
        ("flask run -p 5001", 5001),
        ("uvicorn app:app --host 0.0.0.0 --port=8001", 8001),
        ("node server.js 0.0.0.0:3000", 3000),
        ("python -m pytest -p no:cacheprovider", None),
        ("python build.py", None),
        ("serve --port 80", None),  # privileged ports are not guessed
    ],
)
def test_the_port_a_command_serves_on_is_detected(command: str, port: int | None) -> None:
    from forge.toolkit.background import detect_port

    assert detect_port(command) == port


async def test_a_server_whose_expected_line_never_appears_is_still_ready_when_its_port_answers(
    tmp_path: Path, original_repo: Path
) -> None:
    """The page-redesign speed run lost 245 s: Python buffers a server's output when piped, so the 'Serving HTTP' line the model waited
    for arrived late or never, and every start took the whole 60 s timeout."""
    import time

    from forge.toolkit.background import free_port

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace, shell=ShellSession(workspace), background=BackgroundManager())
    port = free_port(5400)
    started_at = time.perf_counter()
    started = await call(
        StartBackground(),
        context,
        name="static",
        command=f"python -m http.server {port}",
        ready_pattern="a line this server never prints",
        timeout_s=60,
    )
    elapsed = time.perf_counter() - started_at
    try:
        assert started.ok and "not confirmed ready" not in started.content, started.content
        assert elapsed < 20 and port_open(port)
    finally:
        await call(StopBackground(), context, name="static")


def test_a_session_with_too_many_tools_is_cut_to_the_provider_limit() -> None:
    """D-462: Azure refuses more than 128 tools in one request; the rarely needed ones go first, the core ones stay."""
    from forge.tools.registry import MAX_TOOLS_PER_REQUEST, ToolRegistry, default_tools

    class Extra(default_tools()[0].__class__):  # type: ignore[misc]
        pass

    extras = []
    for number in range(30):
        extra = Extra()
        extra.name = f"extra_{number}"
        extras.append(extra)
    registry = ToolRegistry([*default_tools(), *extras])
    names = [spec.name for spec in registry.specs()]
    assert len(names) == MAX_TOOLS_PER_REQUEST
    assert {"read_file", "write_file", "run_command", "archive"} <= set(names)
    assert "synth_samples" not in names  # first on the leave-out list


async def test_read_file_opens_what_the_user_attached_and_the_cut_text_says_how_to_get_the_rest(
    original_repo: Path, tmp_path: Path
) -> None:
    """D-469: an attached file over the inline limit was cut silently and read_file said it does not exist."""
    from forge.parity.mentions import MAX_FILE_CHARS, expand, store_input
    from forge.tools.files import ReadFile
    from forge.tools.search import ListDir
    from forge.workspace.create import create_workspace

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    lines = [f"line {number} " + "x" * 60 for number in range(1, 1001)]
    stored = store_input(workspace, "react_handler.py", "\n".join(lines).encode())
    expanded = expand(f"look at @{stored['path']}", workspace)
    assert "CUT HERE" in expanded.text and f"read_file path={stored['path']}" in expanded.text
    assert len(expanded.text) < MAX_FILE_CHARS + 1500

    context = ToolContext(workspace=workspace)
    first = await ReadFile().run(ReadFile.Args(path=stored["path"], offset=1, limit=3), context)
    assert first.ok and "line 1 " in first.content and "[997 more lines" in first.content
    last = await ReadFile().run(ReadFile.Args(path=stored["path"], offset=1000, limit=5), context)
    assert last.ok and "line 1000 " in last.content  # the end of the file, which the message never showed
    listed = await ListDir().run(ListDir.Args(path=".forge/inputs"), context)
    assert listed.ok and "react_handler.py" in listed.content


async def test_the_attachment_folder_cannot_be_used_to_reach_other_files(
    original_repo: Path, tmp_path: Path
) -> None:
    import pytest

    from forge.errors import ForgeError
    from forge.tools.files import ReadFile
    from forge.workspace.create import create_workspace

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    (workspace.forge_dir / "secret.txt").write_text("not an attachment", encoding="utf-8")
    context = ToolContext(workspace=workspace)
    with pytest.raises(ForgeError):
        await ReadFile().run(ReadFile.Args(path=".forge/inputs/../secret.txt"), context)
    assert workspace.input_path("src/app.py") is None
    assert workspace.input_path("./.forge/inputs/a.txt") is not None
    write_target = workspace.input_path(".forge/inputs/x.txt")
    assert write_target is not None and write_target.parent == (workspace.forge_dir / "inputs").resolve()


async def test_the_saved_full_text_of_a_long_tool_result_can_be_read_in_ranges(
    original_repo: Path, tmp_path: Path
) -> None:
    """The omitted-tokens marker names .forge/tool_outputs/...; read_file could not open it (D-469)."""
    from forge.tools.files import ReadFile
    from forge.workspace.create import create_workspace

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace)
    text = "\n".join(f"row {n} " + "y" * 80 for n in range(1, 3001))
    capped, saved = context.cap_output(text)
    assert saved is not None and ".forge/tool_outputs/" in capped
    relative = Path(saved).relative_to(workspace.root).as_posix()
    part = await ReadFile().run(ReadFile.Args(path=relative, offset=1500, limit=3), context)
    assert part.ok and "row 1500 " in part.content

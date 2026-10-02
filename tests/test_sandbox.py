"""D-050: the low-integrity sandbox. These tests call the shell tool directly, bypassing the
classifier on purpose, to prove that Windows itself refuses writes outside the workspace."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from forge.safety.sandbox import SandboxUnavailableError
from forge.toolkit.background import BackgroundManager
from forge.toolkit.base import ToolContext, ToolResult
from forge.toolkit.shell import PythonRun, RunCommand, ShellSession
from forge.workspace.create import create_workspace
from tests.conftest import FIXTURE_BACKEND, FIXTURE_REPO

# Git Bash puts a Unix whoami on PATH; always use the Windows one.
WHOAMI_GROUPS = r'& "$env:SystemRoot\System32\whoami.exe" /groups | Select-String Mandatory'

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="the sandbox is Windows-only")


@pytest.fixture
def context(original_repo: Path, tmp_path: Path) -> ToolContext:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend", max_file_mb=1)
    return ToolContext(workspace=workspace, shell=ShellSession(workspace), background=BackgroundManager())


async def run(context: ToolContext, command: str) -> ToolResult:
    return await RunCommand().run(RunCommand.Args(command=command), context)


async def test_commands_run_at_low_integrity(context: ToolContext) -> None:
    result = await run(context, WHOAMI_GROUPS)

    assert context.shell is not None and context.shell.sandbox_active
    assert "Low Mandatory Level" in result.content


async def test_windows_refuses_writes_outside_the_workspace(
    context: ToolContext, original_repo: Path
) -> None:
    target = original_repo / "backend" / "sandbox_probe.txt"
    profile_target = Path.home() / "forge_sandbox_probe.txt"
    original_config = (original_repo / "backend" / "claims_app" / "config.py").read_bytes()

    via_powershell = await run(context, f"Set-Content -LiteralPath '{target}' 'escaped'")
    via_python = await run(context, f"python -c \"open(r'{target}', 'w').write('escaped')\"")
    overwrite = await run(
        context, f"Set-Content -LiteralPath '{original_repo / 'backend/claims_app/config.py'}' x"
    )
    profile = await run(context, f"Set-Content -LiteralPath '{profile_target}' 'escaped'")

    assert not via_powershell.ok and not via_python.ok and not overwrite.ok and not profile.ok
    assert not target.exists() and not profile_target.exists()
    assert (original_repo / "backend" / "claims_app" / "config.py").read_bytes() == original_config


async def test_forge_state_is_out_of_reach(context: ToolContext) -> None:
    rules = context.workspace.forge_dir / "permissions.json"
    rules.write_text('{"allowed_prefixes": []}', encoding="utf-8")

    tamper = await run(context, f"Set-Content -LiteralPath '{rules}' '{{\"allowed_prefixes\": [\"rm\"]}}'")
    output = await run(context, f"Set-Content -LiteralPath '{context.workspace.output_dir / 'x.txt'}' 'x'")

    assert not tamper.ok and not output.ok
    assert rules.read_text(encoding="utf-8") == '{"allowed_prefixes": []}'


async def test_normal_work_inside_the_workspace_still_works(context: ToolContext) -> None:
    write = await run(context, "Set-Content -LiteralPath claims_app\\sandbox_ok.txt 'fine'")
    temp = await PythonRun().run(
        PythonRun.Args(
            args="-c \"import tempfile; f = tempfile.NamedTemporaryFile(delete=True); print('temp ok')\""
        ),
        context,
    )

    assert write.ok and (context.workspace.app_dir / "claims_app" / "sandbox_ok.txt").exists()
    assert temp.ok and "temp ok" in temp.content


async def test_fixture_test_suite_passes_inside_the_sandbox(tmp_path: Path) -> None:
    if not (FIXTURE_BACKEND / "venv" / "Scripts" / "python.exe").exists():
        pytest.skip("run scripts/dev/setup_fixture_venv.ps1 first")
    workspace = create_workspace(FIXTURE_REPO, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace, shell=ShellSession(workspace))

    result = await PythonRun().run(
        PythonRun.Args(args="-m pytest -p no:cacheprovider", timeout_s=300), context
    )

    assert context.shell is not None and context.shell.sandbox_active
    assert result.ok, result.content
    assert result.content.count(".") >= 15 and "[100%]" in result.content  # pytest.ini adds -q


async def test_falls_back_with_a_notice_when_the_sandbox_fails(
    context: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken(*args: object, **kwargs: object) -> object:
        raise SandboxUnavailableError("blocked by policy (simulated)")

    monkeypatch.setattr("forge.toolkit.powershell.spawn_low_integrity", broken)
    notices: list[dict[str, object]] = []

    async def publish(kind: str, payload: dict[str, object]) -> None:
        notices.append(payload)

    context.publish = publish
    first = await run(context, "Write-Output ok")
    second = await run(context, "Write-Output again")

    assert first.ok and "Sandbox unavailable, commands now run without it: blocked by policy" in first.content
    assert second.ok and "Sandbox unavailable" not in second.content  # told once
    assert context.shell is not None and context.shell.sandbox_active is False
    assert [n["kind"] for n in notices] == ["sandbox"]


async def test_sandbox_can_be_switched_off(original_repo: Path, tmp_path: Path) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace, shell=ShellSession(workspace, sandbox="off"))

    result = await run(context, WHOAMI_GROUPS)

    assert "Medium Mandatory Level" in result.content
    assert not (workspace.forge_dir / "sandbox" / "labelled").exists()


def test_labelling_works_where_the_user_only_has_modify_rights(tmp_path: Path) -> None:
    # Seen live under C:\Work: inherited Modify rights can't change the label, and icacls /C still exited 0.
    import subprocess

    from forge.safety.sandbox import _current_user_sid, label_low

    folder = tmp_path / "modify_only"
    (folder / "sub").mkdir(parents=True)
    sid = _current_user_sid()
    subprocess.run(
        ["icacls", str(folder), "/inheritance:r", "/grant:r", f"*{sid}:(OI)(CI)M"],
        check=True,
        capture_output=True,
    )
    label_low(folder)
    shown = subprocess.run(["icacls", str(folder / "sub")], capture_output=True, text=True).stdout
    assert "Low Mandatory Level" in shown

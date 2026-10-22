"""Safety invariant 5 (CLAUDE.md): DebCraft cannot modify its own install folder or its config.yaml (D-470)."""

from __future__ import annotations

from pathlib import Path

import pytest

import forge
from forge.config import forge_home
from forge.errors import ForgeError
from forge.safety.shell_classifier import classify
from forge.toolkit.base import ToolContext
from forge.toolkit.shell import ShellSession
from forge.tools.files import WriteFile
from forge.workspace.create import create_workspace
from forge.workspace.read_grants import ReadGrants

INSTALL_FOLDER = Path(forge.__file__).resolve().parent


@pytest.fixture
def workspace(original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FORGE_HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    (tmp_path / "home" / "config.yaml").write_text("llm: {}\n", encoding="utf-8")
    return create_workspace(original_repo, tmp_path / "ws", "backend")


def test_the_write_jail_refuses_the_install_folder_and_config_yaml(workspace) -> None:  # type: ignore[no-untyped-def]
    from forge.safety.paths import JailViolationError

    for target in (
        INSTALL_FOLDER / "config.py",
        INSTALL_FOLDER / "defaults" / "config.yaml",
        forge_home() / "config.yaml",
    ):
        with pytest.raises(JailViolationError):
            workspace.jail.check(target)


async def test_the_file_tools_refuse_to_write_there_by_absolute_path(workspace) -> None:  # type: ignore[no-untyped-def]
    context = ToolContext(workspace=workspace)
    for target in (INSTALL_FOLDER / "session.py", forge_home() / "config.yaml"):
        with pytest.raises(ForgeError):
            await WriteFile().run(WriteFile.Args(path=str(target), content="x = 1\n"), context)
    assert "x = 1" not in (forge_home() / "config.yaml").read_text(encoding="utf-8")


def test_a_read_permission_never_becomes_a_write_permission(workspace) -> None:  # type: ignore[no-untyped-def]
    """The user may open DebCraft's own folder for reading (/allow-read); writing there must still be refused."""
    from forge.safety.paths import JailViolationError

    workspace.read_grants = ReadGrants.for_workspace(workspace.root, forge_home())
    workspace.read_grants.grant(str(INSTALL_FOLDER))
    target = INSTALL_FOLDER / "config.py"
    assert workspace.path_of(str(target)) == target  # readable
    with pytest.raises(JailViolationError):
        workspace.write_text(str(target), "boom\n", "test")


def test_a_shell_command_that_writes_there_is_never_run_unasked(workspace) -> None:  # type: ignore[no-untyped-def]
    scope = ShellSession(workspace, sandbox="off").scope()
    for command in (
        f'Set-Content -Path "{INSTALL_FOLDER / "config.py"}" -Value "x"',
        f'Add-Content "{forge_home() / "config.yaml"}" "x: 1"',
        f"python -c \"open(r'{INSTALL_FOLDER / 'config.py'}', 'w').write('x')\"",
    ):
        assert classify(command, scope).level != "safe", command

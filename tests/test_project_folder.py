"""A Mode B project folder may already hold other files (D-211): they stay untouched and out of reach."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from forge.modeb.profile import ProfileStore
from forge.modeb.workspace import RESERVED_NAMES, check_project_folder, create_standalone_workspace
from forge.parity.mentions import expand
from forge.safety.paths import JailViolationError
from forge.safety.shell_classifier import classify
from forge.toolkit.base import ToolContext
from forge.toolkit.shell import ShellSession
from forge.tools.files import ReadFile
from forge.workspace.read_grants import ReadGrants
from forge.workspace.workspace import WorkspaceError


@pytest.fixture(autouse=True)
def quick(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORGE_SKIP_TEST_RUNNER_INSTALL", "1")  # no pip run: not what is tested here


def make(tmp_path: Path, isolated_forge_home: Path, folder: Path) -> object:
    profile = ProfileStore(isolated_forge_home).create("host")
    return create_standalone_workspace(folder, profile)


def test_a_folder_with_other_files_is_accepted_and_those_files_are_left_alone(
    tmp_path: Path, isolated_forge_home: Path
) -> None:
    folder = tmp_path / "inputs"
    folder.mkdir()
    (folder / "brief.md").write_text("my notes", encoding="utf-8")
    (folder / "sub").mkdir()
    (folder / "sub" / "data.csv").write_text("a,b\n", encoding="utf-8")

    workspace = make(tmp_path, isolated_forge_home, folder)

    assert (folder / "brief.md").read_text(encoding="utf-8") == "my notes"
    assert (folder / "sub" / "data.csv").read_text(encoding="utf-8") == "a,b\n"
    for name in ("project", "_harness", "output", ".forge"):
        assert (folder / name).is_dir()
    assert workspace.mode_b  # type: ignore[attr-defined]


def test_the_shell_cannot_read_the_users_other_files_but_can_use_forges_own_folders(
    tmp_path: Path, isolated_forge_home: Path
) -> None:
    folder = tmp_path / "inputs"
    folder.mkdir()
    (folder / "notes.txt").write_text("private", encoding="utf-8")
    workspace = make(tmp_path, isolated_forge_home, folder)
    scope = ShellSession(workspace, sandbox="off").scope()  # type: ignore[arg-type]

    assert classify(f'type "{folder / "notes.txt"}"', scope).level == "blocked"
    assert classify("type ..\\notes.txt", scope).level == "blocked"
    assert classify(f'type "{folder / "project" / "app.py"}"', scope).level == "safe"
    assert classify(f'type "{folder / "output" / "COPY_INSTRUCTIONS.md"}"', scope).level == "safe"
    assert classify("type app.py", scope).level == "safe"


def test_forges_own_names_must_be_free(tmp_path: Path) -> None:
    for name in RESERVED_NAMES:
        folder = tmp_path / f"has-{name.strip('._')}"
        folder.mkdir()
        (folder / name).mkdir()
        with pytest.raises(WorkspaceError) as raised:
            check_project_folder(folder)
        assert name in str(raised.value) and "Choose another folder" in str(raised.value)


def test_an_existing_project_is_not_created_over_and_a_file_is_not_a_folder(
    tmp_path: Path, isolated_forge_home: Path
) -> None:
    folder = tmp_path / "again"
    make(tmp_path, isolated_forge_home, folder)
    with pytest.raises(WorkspaceError, match="already a Forge project"):
        check_project_folder(folder)
    afile = tmp_path / "a.txt"
    afile.write_text("x", encoding="utf-8")
    with pytest.raises(WorkspaceError, match="is a file"):
        check_project_folder(afile)


def test_a_missing_or_empty_folder_is_fine(tmp_path: Path) -> None:
    check_project_folder(tmp_path / "new")
    empty = tmp_path / "empty"
    empty.mkdir()
    check_project_folder(empty)
    assert os.listdir(empty) == []


async def test_files_beside_project_can_be_opened_by_typing_their_path(
    tmp_path: Path, isolated_forge_home: Path
) -> None:
    """The case from a live run: the project folder held brief.md and .env next to project/. They are not
    part of the workspace, so reading them needs the user's own words, like any file elsewhere."""
    folder = tmp_path / "inputs"
    folder.mkdir()
    (folder / "brief.md").write_text("Reading Radar brief", encoding="utf-8")
    (folder / ".env").write_text("API_TOKEN=do-not-show-me-123\n", encoding="utf-8")  # check_secrets: fake
    (folder / "other.txt").write_text("not mentioned", encoding="utf-8")
    workspace = make(tmp_path, isolated_forge_home, folder)
    workspace.read_grants = ReadGrants.for_workspace(workspace.root, isolated_forge_home)  # type: ignore[attr-defined]
    context = ToolContext(workspace=workspace)  # type: ignore[arg-type]

    with pytest.raises(JailViolationError):  # nothing is open until the user says so
        await ReadFile().run(ReadFile.Args(path=str(folder / "brief.md")), context)

    typed = f"Please read {folder / 'brief.md'} and also look at {folder / '.env'}"
    opened = expand(typed, workspace)  # type: ignore[arg-type]
    assert len(opened.grants) == 2 and all("may now read" in line for line in opened.grants)

    brief = await ReadFile().run(ReadFile.Args(path=str(folder / "brief.md")), context)
    assert brief.ok and "Reading Radar brief" in brief.content
    secret = await ReadFile().run(ReadFile.Args(path=str(folder / ".env")), context)
    assert "do-not-show-me-123" not in secret.content and "API_TOKEN" in secret.content  # names only
    with pytest.raises(JailViolationError):  # the file that was not mentioned stays closed
        await ReadFile().run(ReadFile.Args(path=str(folder / "other.txt")), context)

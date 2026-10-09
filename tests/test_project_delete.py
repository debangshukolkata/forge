from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from forge.web.manager import WebSessionManager
from forge.web.project_delete import ProjectDeleteError


def _project(home: Path, root: Path, repo: str = "standalone (Mode B)") -> dict[str, str]:
    (root / ".forge").mkdir(parents=True)
    (root / ".forge" / "workspace.json").write_text("{}", encoding="utf-8")
    (root / "output").mkdir()
    readonly = root / "output" / "locked.txt"
    readonly.write_text("x", encoding="utf-8")
    readonly.chmod(0o444)  # copied repo files are often read-only on Windows
    entry = {"path": str(root), "name": root.name, "repo": repo, "app_folder": None}
    recent = home / "recent_workspaces.json"
    known = json.loads(recent.read_text(encoding="utf-8")) if recent.exists() else []
    recent.write_text(json.dumps([*known, entry]), encoding="utf-8")
    return entry


def _manager(home: Path) -> WebSessionManager:
    return WebSessionManager(home, session_factory=lambda workspace: None)  # type: ignore[arg-type,return-value]


def test_delete_removes_the_folder_and_the_list_entry(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    keep, doomed = tmp_path / "keep", tmp_path / "doomed"
    _project(home, keep)
    _project(home, doomed)
    manager = _manager(home)
    asyncio.run(manager.delete_project(doomed))
    assert not doomed.exists()
    assert keep.exists()
    assert [Path(e["path"]) for e in manager.recent()] == [keep]


def test_delete_refuses_a_folder_forge_does_not_know(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    stranger = tmp_path / "documents"
    stranger.mkdir()
    with pytest.raises(ProjectDeleteError):
        asyncio.run(_manager(home).delete_project(stranger))
    assert stranger.exists()


def test_delete_refuses_when_the_original_repo_is_inside(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    root = tmp_path / "parent"
    repo = root / "my-repo"
    repo.mkdir(parents=True)
    _project(home, root, repo=str(repo))
    with pytest.raises(ProjectDeleteError):
        asyncio.run(_manager(home).delete_project(root))
    assert repo.exists()


def test_delete_refuses_a_folder_holding_the_forge_home(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    home = root / "inner-home"
    home.mkdir(parents=True)
    _project(home, root)
    with pytest.raises(ProjectDeleteError):
        asyncio.run(_manager(home).delete_project(root))
    assert home.exists()

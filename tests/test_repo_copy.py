"""D-674: Copy to source replaces one file in the user's repository, on the user's click in a red card only."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from forge.safety.server_security import ServerSecurity
from forge.web.manager import WebSessionManager
from forge.web.server import create_app
from forge.workspace.create import create_workspace
from forge.workspace.to_repository import RepoCopyError, copy_to_repository, plan_copy, undo_copy
from forge.workspace.workspace import Workspace
from tests.test_web import BASE, direct_session, login
from tests.workspace_helpers import copy_fixture

ERRORS = "backend/claims_app/errors.py"


def _project(tmp_path: Path) -> tuple[Path, Workspace]:
    repo = copy_fixture(tmp_path / "repo")
    workspace = create_workspace(repo, tmp_path / "ws", "backend")
    text = (workspace.repo_dir / ERRORS).read_text(encoding="utf-8")
    workspace.write_text(ERRORS, text + "\nDELIVERED_BY_DEBCRAFT = True\n", reason="test")
    return repo, workspace


def test_a_copy_replaces_the_file_keeps_the_old_one_and_undoes(tmp_path: Path) -> None:
    repo, workspace = _project(tmp_path)
    before = (repo / ERRORS).read_bytes()
    plan = plan_copy(workspace, ERRORS)
    assert plan.status == "modified" and plan.state == "differs" and plan.edited_lines == 0
    assert plan.command == f'Copy-Item -LiteralPath "{plan.source}" -Destination "{plan.target}" -Force'
    copy_id = copy_to_repository(workspace, plan)
    assert (repo / ERRORS).read_bytes() == (workspace.repo_dir / ERRORS).read_bytes()
    assert plan_copy(workspace, ERRORS).state == "same"
    assert undo_copy(workspace, copy_id) == ERRORS
    assert (repo / ERRORS).read_bytes() == before
    with pytest.raises(RepoCopyError):
        undo_copy(workspace, copy_id)  # undone once


def test_the_users_own_edits_are_counted_and_undo_leaves_a_later_change_alone(tmp_path: Path) -> None:
    repo, workspace = _project(tmp_path)
    target = repo / ERRORS
    target.write_text(target.read_text(encoding="utf-8") + "LOCAL = 1\nOTHER = 2\n", encoding="utf-8")
    assert plan_copy(workspace, ERRORS).edited_lines == 2
    copy_id = copy_to_repository(workspace, plan_copy(workspace, ERRORS))
    target.write_text("changed after the copy\n", encoding="utf-8")
    with pytest.raises(RepoCopyError, match="changed after the copy"):
        undo_copy(workspace, copy_id)
    assert target.read_text(encoding="utf-8") == "changed after the copy\n"


def test_a_new_file_is_added_and_its_undo_removes_it(tmp_path: Path) -> None:
    repo, workspace = _project(tmp_path)
    workspace.write_text("backend/claims_app/new_agent.py", "AGENT = 1\n", reason="test")
    plan = plan_copy(workspace, "backend/claims_app/new_agent.py")
    assert plan.status == "added" and not plan.target_exists
    copy_id = copy_to_repository(workspace, plan)
    assert (repo / "backend/claims_app/new_agent.py").read_text(encoding="utf-8") == "AGENT = 1\n"
    undo_copy(workspace, copy_id)
    assert not (repo / "backend/claims_app/new_agent.py").exists()


def test_what_is_never_copied(tmp_path: Path) -> None:
    _, workspace = _project(tmp_path)
    for path, why in (
        ("backend/claims_app/__init__.py", "nothing to copy"),  # unchanged
        ("backend/.env", "not copied"),  # a secret file
        ("../outside.py", "not copied|nothing to copy|escapes"),
    ):
        with pytest.raises((RepoCopyError, Exception), match=why):
            plan_copy(workspace, path)
    with pytest.raises(RepoCopyError, match=r"undo|Unknown"):
        undo_copy(workspace, "../../x")


def test_the_route_copies_only_with_the_cards_one_time_code(
    tmp_path: Path, isolated_forge_home: Path
) -> None:
    repo, workspace = _project(tmp_path)
    security = ServerSecurity(port=8799, token="test-token-0123456789")  # check_secrets: fake
    manager = WebSessionManager(isolated_forge_home, direct_session)
    with TestClient(create_app(manager, security), base_url=BASE) as client:
        login(client, security)
        assert client.post("/api/open", json={"workspace": str(workspace.root)}).status_code == 200
        assert client.post("/api/repo-copy", json={"code": "made-up"}).status_code == 403
        card = client.get("/api/repo-copy", params={"path": ERRORS}).json()
        assert card["command"].startswith("Copy-Item") and card["target"] == str(repo / ERRORS)
        done = client.post("/api/repo-copy", json={"code": card["code"]})
        assert done.status_code == 200, done.text
        assert (repo / ERRORS).read_bytes() == (workspace.repo_dir / ERRORS).read_bytes()
        assert client.post("/api/repo-copy", json={"code": card["code"]}).status_code == 403  # used once
        undone = client.post("/api/repo-copy/undo", json={"copy_id": done.json()["copy_id"]})
        assert undone.status_code == 200 and "DELIVERED_BY_DEBCRAFT" not in (repo / ERRORS).read_text(
            encoding="utf-8"
        )
        assert client.get("/api/repo-copy", params={"path": "backend/.env"}).status_code == 400

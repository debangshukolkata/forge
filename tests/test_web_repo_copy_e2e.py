"""D-674 in headless Edge: the file card's Copy to source opens a red card with the command; Replace copies, Undo puts
the user's file back. Screenshots go to test-artifacts/react-ui/."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.protocol.events import EventType
from forge.workspace.create import create_workspace
from forge.workspace.workspace import Workspace
from tests.conftest import REPO_ROOT
from tests.test_web_e2e import (  # noqa: F401  (the fixtures are used by name)
    LiveServer,
    configured_secrets,
    live_server,
    open_in_edge,
    playwright_api,
)
from tests.workspace_helpers import copy_fixture

pytestmark = pytest.mark.e2e

ERRORS = "backend/claims_app/errors.py"


@pytest.fixture
def own_project(tmp_path: Path) -> tuple[Path, Workspace]:
    repo = copy_fixture(tmp_path / "repo")  # its own repository: this test writes into it
    workspace = create_workspace(repo, tmp_path / "ws", "backend")
    text = (workspace.repo_dir / ERRORS).read_text(encoding="utf-8")
    workspace.write_text(ERRORS, text + "\nDELIVERED_BY_DEBCRAFT = True\n", reason="test")
    (repo / ERRORS).write_text(text + "LOCAL_EDIT = 1\n", encoding="utf-8")  # the user changed it meanwhile
    return repo, workspace


def test_copy_to_source_shows_the_command_copies_and_undoes(
    live_server: LiveServer,  # noqa: F811
    own_project: tuple[Path, Workspace],
) -> None:
    repo, workspace = own_project
    users_file = (repo / ERRORS).read_bytes()
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    shots.mkdir(parents=True, exist_ok=True)
    with playwright_api.sync_playwright() as p:
        browser, page = open_in_edge(p, live_server, workspace)
        live_server.publish(EventType.USER_MESSAGE, {"text": "Which file did you change?"})
        live_server.publish(EventType.MESSAGE_DONE, {"text": f"I changed `{ERRORS}`."})
        page.click(f"code.md-file:has-text('{ERRORS}')")
        page.wait_for_selector(".file-location")
        page.click(".file-location button:has-text('Copy to source')")
        page.wait_for_selector(".repo-copy .repo-copy-command")
        command = page.inner_text(".repo-copy-command")
        assert command.startswith("Copy-Item") and str(repo / ERRORS).replace("/", "\\") in command.replace(
            "/", "\\"
        )
        warnings = page.inner_text(".repo-copy-body")
        assert "Those edits will be lost" in warnings, warnings
        assert (repo / ERRORS).read_bytes() == users_file  # nothing happens before the click
        page.screenshot(path=str(shots / "repo-copy-card.png"))
        page.click(".repo-copy-confirm")
        page.wait_for_selector(".repo-copy-done")
        assert (repo / ERRORS).read_bytes() == (workspace.repo_dir / ERRORS).read_bytes()
        page.screenshot(path=str(shots / "repo-copy-done.png"))
        page.click(".repo-copy-actions button:has-text('Undo')")
        page.wait_for_selector("text=Undone: your repository has its own file again.")
        assert (repo / ERRORS).read_bytes() == users_file
        assert page.problems == [], page.problems  # type: ignore[attr-defined]
        browser.close()

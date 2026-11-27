"""D-672: a change the user already put into the repository is not asked for again (office 2026-11-27)."""

from __future__ import annotations

from pathlib import Path

from forge.agent.handover_check import already_there_note
from forge.toolkit.base import ToolContext
from forge.workspace.create import create_workspace
from forge.workspace.output import build_copy_instructions, changes_of, compute_changes, repository_state
from tests.workspace_helpers import copy_fixture

INIT = "backend/claims_app/__init__.py"


def _project(tmp_path: Path):  # type: ignore[no-untyped-def]
    repo = copy_fixture(tmp_path / "repo")
    workspace = create_workspace(repo, tmp_path / "ws", "backend")
    text = (workspace.repo_dir / INIT).read_text(encoding="utf-8")
    # like the dashboard agent: a comment and an import added in the middle of the file
    lines = text.splitlines()
    lines[1:1] = ["# ruff: noqa: F401", "from .db import get_connection as _registered"]
    workspace.write_text(INIT, "\n".join(lines) + "\n", reason="register the agent")
    return repo, workspace, text


def test_the_state_follows_what_the_user_did_in_the_repository(tmp_path: Path) -> None:
    repo, workspace, original = _project(tmp_path)
    [change] = [c for c in compute_changes(workspace) if c.path == INIT]
    assert repository_state(workspace, change) == "differs"  # not copied yet
    # the user pasted only the import, at the end, without the comment
    (repo / INIT).write_text(original + "from .db import get_connection as _registered\n", encoding="utf-8")
    assert repository_state(workspace, change) == "applied"
    instructions = build_copy_instructions(workspace, compute_changes(workspace))
    assert (
        "Already in your repository (1)" in instructions and f"`{INIT}` (every changed line" in instructions
    )
    assert "## 2. Replace modified files (0)" in instructions
    (repo / INIT).write_bytes((workspace.repo_dir / INIT).read_bytes())
    assert repository_state(workspace, change) == "same"


def test_a_reply_that_asks_to_copy_it_again_gets_a_note_once(tmp_path: Path) -> None:
    repo, workspace, original = _project(tmp_path)
    context = ToolContext(workspace=workspace)
    reply = f"Copy these updated files into your repository:\n- `{INIT}`"
    assert already_there_note(context, reply) == ""  # still to copy: nothing to correct
    (repo / INIT).write_text(original + "from .db import get_connection as _registered\n", encoding="utf-8")
    note = already_there_note(context, reply)
    assert INIT in note and "already have these changes" in note and "do not ask the user to copy" in note
    assert already_there_note(context, reply) == ""  # told once
    assert already_there_note(ToolContext(workspace=workspace), "The tests pass.") == ""  # no copying asked
    assert [c.path for c in changes_of(workspace, {"claims_app/__init__.py"})] == [
        INIT
    ]  # the end of a path is enough

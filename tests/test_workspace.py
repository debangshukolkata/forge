"""M2 acceptance: workspace copy, write jail, format preservation, checkpoints, output/ generator."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from forge.safety.paths import JailViolationError, os_path
from forge.workspace.create import create_workspace
from forge.workspace.output import build_output
from forge.workspace.pyenv import find_app_folder_candidates, find_venvs, origins_outside_copy
from forge.workspace.workspace import Workspace, WorkspaceError
from tests.workspace_helpers import (
    BIG_FILE,
    BOM_FILE,
    CP1252_FILE,
    CRLF_FILE,
    long_file_relative,
    make_junction,
    site_packages,
    tree_bytes,
)

SKIP_DIRS = {"venv", "__pycache__", ".pytest_cache", "logs", "linked_outside"}


@pytest.fixture
def workspace(original_repo: Path, tmp_path: Path) -> Workspace:
    return create_workspace(original_repo, tmp_path / "ws", "backend", max_file_mb=1)


def snapshot(repo: Path) -> dict[str, bytes]:
    return tree_bytes(repo, skip={"venv"})


# --- creation ---


def test_copy_respects_excludes_gitignores_and_limits(workspace: Workspace, original_repo: Path) -> None:
    copied = set(workspace.manifest.files)
    report = workspace.info.copy_report

    assert "backend/claims_app/__init__.py" in copied
    assert long_file_relative() in copied  # > 260-character path
    assert not any(path.startswith("backend/venv/") for path in copied)  # venv reused, never copied
    assert "backend/logs/app.log" not in copied  # default exclude
    assert "backend/claims.db" not in copied  # backend/.gitignore
    assert "backend/notes.tmp" not in copied  # .gitignore above the app folder
    assert ".gitignore" in copied  # ...which is copied so the rules still apply
    assert not any(path.startswith("frontend/") for path in copied)  # only the app folder
    assert BIG_FILE in report.skipped_large
    assert "backend/linked_outside" in report.skipped_links
    assert workspace.manifest.files["backend/.env"].secret


def test_app_venv_interpreter_is_reused(workspace: Workspace, original_repo: Path) -> None:
    env = workspace.info.python_env

    assert env is not None
    assert Path(env.python).is_relative_to(original_repo / "backend" / "venv")
    assert env.top_packages == ["claims_app"]
    assert env.shim_dir is None
    assert origins_outside_copy(env) == {}  # imports resolve to the workspace copy


def test_workspace_location_is_validated(original_repo: Path, tmp_path: Path) -> None:
    with pytest.raises(WorkspaceError, match="inside the repository"):
        create_workspace(original_repo, original_repo / "ws", "backend")
    busy = tmp_path / "busy"
    busy.mkdir()
    (busy / "x.txt").write_text("x", encoding="utf-8")
    with pytest.raises(WorkspaceError, match="new or empty"):
        create_workspace(original_repo, busy, "backend")


def test_app_folder_candidates(original_repo: Path) -> None:
    assert find_app_folder_candidates(original_repo) == ["backend"]


# --- write jail ---


def test_writes_can_never_reach_the_original_repo(workspace: Workspace, original_repo: Path) -> None:
    before = snapshot(original_repo)
    target = original_repo / "backend" / "claims_app" / "config.py"

    with pytest.raises(JailViolationError):
        workspace.jail.check(target)
    with pytest.raises(JailViolationError):
        workspace.write_text("../../../orig/claims-repo/backend/x.py", "x = 1\n")
    with pytest.raises(JailViolationError):
        workspace.write_text(str(target), "x = 1\n")
    with pytest.raises(JailViolationError):
        workspace.jail.check(Path.home() / "forge-escape.txt")

    assert snapshot(original_repo) == before


def test_junction_into_the_original_repo_is_rejected(workspace: Workspace, original_repo: Path) -> None:
    link = workspace.repo_dir / "backend" / "sneaky"
    if not make_junction(link, original_repo / "backend"):
        pytest.skip("cannot create a junction here")
    before = snapshot(original_repo)

    with pytest.raises(JailViolationError):
        workspace.write_text("backend/sneaky/claims_app/config.py", "hacked = True\n")

    assert snapshot(original_repo) == before


# --- editing, formats, baseline ---


def test_edits_preserve_crlf_bom_and_encoding(workspace: Workspace) -> None:
    for relative in (CRLF_FILE, BOM_FILE, CP1252_FILE):
        text, _ = workspace.read_text(relative)
        workspace.write_text(relative, text + "ADDED = 1\n")

    assert workspace.path_of(CRLF_FILE).read_bytes().endswith(b"VALUE = 1\r\nADDED = 1\r\n")
    assert workspace.path_of(BOM_FILE).read_bytes().startswith(b"\xef\xbb\xbf")
    assert b"\r" not in workspace.path_of(BOM_FILE).read_bytes()
    assert workspace.path_of(CP1252_FILE).read_bytes().startswith(b"Caf\xe9 claims guide\n")


def test_baseline_saved_on_first_write_only(workspace: Workspace) -> None:
    relative = "backend/claims_app/errors.py"
    original = workspace.path_of(relative).read_bytes()

    workspace.write_text(relative, "first = 1\n")
    workspace.write_text(relative, "second = 2\n")

    assert (workspace.forge_dir / "baseline" / relative).read_bytes() == original


def test_new_file_uses_the_repo_dominant_line_ending(workspace: Workspace) -> None:
    workspace.write_text("backend/claims_app/new_module.py", "a = 1\nb = 2\n")
    expected = b"\r\n" if workspace.info.default_newline == "crlf" else b"\n"

    assert (
        workspace.path_of("backend/claims_app/new_module.py").read_bytes()
        == b"a = 1" + expected + b"b = 2" + expected
    )


# --- checkpoints ---


def test_undo_and_rewind_restore_files(workspace: Workspace) -> None:
    config = "backend/claims_app/config.py"
    original = workspace.path_of(config).read_bytes()

    first = workspace.write_text(config, "changed = 1\n")
    workspace.write_text("backend/claims_app/brand_new.py", "x = 1\n")
    workspace.delete("backend/claims_app/llm.py")

    assert workspace.undo() is not None  # restores llm.py
    assert workspace.path_of("backend/claims_app/llm.py").exists()
    workspace.rewind(first.id)  # removes brand_new.py and restores config.py

    assert not workspace.path_of("backend/claims_app/brand_new.py").exists()
    assert workspace.path_of(config).read_bytes() == original
    assert workspace.checkpoints.all() == []
    assert workspace.changes() == []
    assert workspace.undo() is None


# --- output ---


def make_typical_changes(workspace: Workspace) -> None:
    routes = "backend/claims_app/api/claims/routes.py"
    text, _ = workspace.read_text(routes)
    workspace.write_text(routes, text + "\n# exported claims\n", reason="Add export endpoint")
    workspace.write_text(CRLF_FILE, workspace.read_text(CRLF_FILE)[0] + "MORE = 2\n")
    workspace.write_text(
        "backend/claims_app/services/export_service.py",
        "def export():\n    return []\n",
        reason="New export service",
    )
    workspace.delete("backend/claims_app/prompts/triage.py", reason="Prompts moved")
    workspace.move("backend/docs_cp1252.txt", "backend/docs/guide_cp1252.txt", reason="Docs folder")


def test_output_contains_only_changes_at_repo_relative_paths(workspace: Workspace) -> None:
    make_typical_changes(workspace)

    report = build_output(workspace)

    statuses = {change.path: change.status for change in report.files}
    assert statuses == {
        "backend/claims_app/api/claims/routes.py": "modified",
        CRLF_FILE: "modified",
        "backend/claims_app/services/export_service.py": "added",
        "backend/claims_app/prompts/triage.py": "deleted",
        "backend/docs_cp1252.txt": "deleted",
        "backend/docs/guide_cp1252.txt": "added",
    }
    exported = {
        p.relative_to(workspace.output_dir).as_posix() for p in workspace.output_dir.rglob("*") if p.is_file()
    }
    assert exported == {
        "backend/claims_app/api/claims/routes.py",
        CRLF_FILE,
        "backend/claims_app/services/export_service.py",
        "backend/docs/guide_cp1252.txt",
        "MANIFEST.json",
        "CHANGES.md",
        "changes.patch",
        "COPY_INSTRUCTIONS.md",
    }
    instructions = (workspace.output_dir / "COPY_INSTRUCTIONS.md").read_text(encoding="utf-8")
    assert (
        "## 1. Add new files (2)" in instructions and "moved from `backend/docs_cp1252.txt`" in instructions
    )
    assert "Delete `backend/claims_app/prompts/triage.py`" in instructions
    changes_md = (workspace.output_dir / "CHANGES.md").read_text(encoding="utf-8")
    assert "- Add export endpoint" in changes_md and "+# exported claims" in changes_md
    assert "+++ b/backend/claims_app/services/export_service.py" in (
        workspace.output_dir / "changes.patch"
    ).read_text(encoding="utf-8")


def test_applying_output_to_a_fresh_copy_reproduces_the_workspace(
    workspace: Workspace, original_repo: Path, tmp_path: Path
) -> None:
    make_typical_changes(workspace)
    report = build_output(workspace)
    fresh = tmp_path / "fresh"
    shutil.copytree(
        os_path(original_repo, force=True),
        os_path(fresh, force=True),
        ignore=shutil.ignore_patterns("venv", "linked_outside"),
    )

    for change in report.files:  # exactly what COPY_INSTRUCTIONS tells the user to do
        target = fresh / change.path
        if change.status == "deleted":
            target.unlink()
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(workspace.output_dir / change.path, target)

    copied_paths = set(workspace.manifest.files) | {c.path for c in report.files if c.status == "added"}
    copied_paths -= {c.path for c in report.files if c.status == "deleted"}
    fresh_files = tree_bytes(fresh, SKIP_DIRS)
    workspace_files = tree_bytes(workspace.repo_dir, SKIP_DIRS)
    for relative in copied_paths:
        assert fresh_files[relative] == workspace_files[relative], relative
    assert fresh_files[CRLF_FILE].endswith(b"\r\nMORE = 2\r\n")


def test_secret_files_are_never_exported(workspace: Workspace) -> None:
    text, _ = workspace.read_text("backend/.env")
    workspace.write_text("backend/.env", text + "NEW_FLAG=1\n")

    report = build_output(workspace)

    assert [c.path for c in report.files if c.secret] == ["backend/.env"]
    assert not (workspace.output_dir / "backend" / ".env").exists()
    assert "fixture-not-a-real" not in (workspace.output_dir / "CHANGES.md").read_text(encoding="utf-8")
    assert "fixture-not-a-real" not in (workspace.output_dir / "changes.patch").read_text(encoding="utf-8")
    assert "`backend/.env` (modified)" in (workspace.output_dir / "COPY_INSTRUCTIONS.md").read_text(
        encoding="utf-8"
    )


def test_workspace_reopens_from_disk(workspace: Workspace) -> None:
    workspace.write_text("backend/claims_app/x.py", "x = 1\n")

    reopened = Workspace.open(workspace.root)

    assert reopened.info == workspace.info
    assert [cp.label for cp in reopened.checkpoints.all()] == ["write backend/claims_app/x.py"]


# --- editable installs and broken venvs ---


def test_editable_install_of_the_original_is_detected_and_corrected(
    original_repo: Path, tmp_path: Path
) -> None:
    repo = tmp_path / "editable-repo"
    shutil.copytree(
        os_path(original_repo, force=True),
        os_path(repo, force=True),
        symlinks=True,
        ignore=shutil.ignore_patterns("linked_outside"),
    )
    venv = repo / "backend" / "venv"
    for cfg_line in (venv / "pyvenv.cfg").read_text(encoding="utf-8").splitlines():
        assert "home" not in cfg_line or Path(cfg_line.split("=", 1)[1].strip()).exists()
    # Legacy easy-install style .pth: puts the ORIGINAL app first on sys.path, ahead of PYTHONPATH.
    original_app = repo / "backend"
    (site_packages(venv) / "zz_editable_claims.pth").write_text(
        f"import sys; sys.path.insert(0, {str(original_app)!r})\n", encoding="utf-8"
    )

    workspace = create_workspace(repo, tmp_path / "ws", "backend")
    env = workspace.info.python_env

    assert env is not None and env.shim_dir is not None
    assert origins_outside_copy(env) == {}
    without_shim = env.model_copy(update={"shim_dir": None})
    assert "editable-repo" in origins_outside_copy(without_shim)["claims_app"]


def test_broken_venv_is_not_used(tmp_path: Path) -> None:
    app = tmp_path / "app"
    (app / "venv").mkdir(parents=True)
    (app / "venv" / "pyvenv.cfg").write_text(
        "home = C:\\missing\\python\nversion = 3.13.0\n", encoding="utf-8"
    )

    venvs = find_venvs(app)

    assert len(venvs) == 1 and not venvs[0].base_interpreter_ok


def test_output_manifest_is_machine_readable(workspace: Workspace) -> None:
    workspace.write_text("backend/claims_app/y.py", "y = 2\n")
    build_output(workspace)

    data = json.loads((workspace.output_dir / "MANIFEST.json").read_text(encoding="utf-8"))

    assert data["files"][0]["path"] == "backend/claims_app/y.py"
    assert data["repository"] == workspace.info.repo_path
    assert os.path.isabs(data["repository"])


def test_runtime_data_files_are_not_delivered(workspace: Workspace) -> None:
    """D-222: a SQLite file the app wrote while Forge ran it is data, not code."""
    workspace.write_text("backend/claims_app/services/export_service.py", "x = 1\n", reason="New service")
    (workspace.repo_dir / "backend" / "claims_app" / "app.sqlite").write_bytes(b"SQLite format 3\x00")
    (workspace.repo_dir / "backend" / "claims_app" / "app.db-journal").write_bytes(b"journal")

    report = build_output(workspace)

    paths = {change.path for change in report.files}
    assert "backend/claims_app/services/export_service.py" in paths
    assert not any(path.endswith((".sqlite", ".db-journal")) for path in paths)
    assert not (workspace.output_dir / "backend" / "claims_app" / "app.sqlite").exists()

"""Creates a Mode A workspace from the user's repository (spec §6.1)."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from forge.safety.paths import is_within, real_path
from forge.workspace.copy_repo import ProgressCallback, copy_app_folder
from forge.workspace.ignore import IgnoreRules
from forge.workspace.manifest import BaselineManifest, ManifestEntry, sha256_of
from forge.workspace.pyenv import (
    PythonEnvironment,
    find_top_packages,
    find_venvs,
    origins_outside_copy,
    write_import_shim,
)
from forge.workspace.text_format import Newline, detect_format
from forge.workspace.workspace import Workspace, WorkspaceError, WorkspaceInfo

DEFAULT_MAX_FILE_MB = 20


def validate_locations(repo: Path, workspace: Path) -> None:
    if not repo.is_dir():
        raise WorkspaceError(f"Repository folder not found: {repo}")
    if is_within(workspace, repo):
        raise WorkspaceError("The workspace must not be inside the repository (Forge never writes there).")
    if is_within(repo, workspace):
        raise WorkspaceError("The repository must not be inside the workspace folder.")
    if workspace.exists() and any(workspace.iterdir()):
        raise WorkspaceError(f"The workspace folder must be new or empty: {workspace}")


def create_workspace(
    repo_path: Path,
    workspace_path: Path,
    app_subfolder: str,
    *,
    extra_excludes: list[str] | None = None,
    max_file_mb: int = DEFAULT_MAX_FILE_MB,
    on_progress: ProgressCallback | None = None,
) -> Workspace:
    repo = real_path(repo_path)
    root = real_path(workspace_path)
    validate_locations(repo, root)
    app_subfolder = Path(app_subfolder).as_posix().strip("/")
    if not (repo / app_subfolder).is_dir():
        raise WorkspaceError(f"App folder not found in the repository: {app_subfolder}")

    info = WorkspaceInfo(name=root.name, repo_path=str(repo), app_subfolder=app_subfolder, created=_now())
    workspace = Workspace(root, info)
    for directory in (workspace.repo_dir, workspace.output_dir, workspace.forge_dir):
        directory.mkdir(parents=True, exist_ok=True)

    rules = IgnoreRules(repo, extra_excludes=extra_excludes)
    report, manifest = copy_app_folder(
        repo, app_subfolder, workspace.repo_dir, rules, workspace.jail, max_file_mb * 1024 * 1024, on_progress
    )
    _copy_ancestor_gitignores(repo, app_subfolder, workspace, manifest)
    manifest.save(workspace.jail.check(workspace.forge_dir / "baseline_manifest.json"))
    workspace._manifest = manifest

    info.copy_report = report
    info.default_newline = dominant_newline(manifest)
    info.python_env = setup_python_environment(workspace, repo / app_subfolder)
    info.status = "ready"
    workspace.save_info()
    return workspace


def setup_python_environment(workspace: Workspace, original_app_dir: Path) -> PythonEnvironment | None:
    """Reuses the app's own venv (never copied) and makes sure imports resolve to the workspace copy."""
    venvs = [venv for venv in find_venvs(original_app_dir) if venv.base_interpreter_ok]
    if not venvs:
        return None  # the orchestrator asks the user (M6); nothing can run until then
    env = PythonEnvironment(
        python=venvs[0].python,
        venv=venvs[0].path,
        app_dir=str(workspace.app_dir),
        top_packages=find_top_packages(workspace.app_dir),
    )
    if env.top_packages and origins_outside_copy(env):
        shim_dir = workspace.jail.check(workspace.forge_dir / "pyshim")
        write_import_shim(shim_dir, workspace.app_dir, original_app_dir, env.top_packages)
        env = env.model_copy(update={"shim_dir": str(shim_dir)})
        still_wrong = origins_outside_copy(env)
        if still_wrong:
            raise WorkspaceError(
                "The app's venv imports these packages from outside the workspace even after correction: "
                + json.dumps(still_wrong)
                + ". Uninstall the editable install (pip uninstall <package>) "
                "or tell Forge which venv to use."
            )
    return env


def dominant_newline(manifest: BaselineManifest) -> Newline:
    counts = Counter(entry.format.newline for entry in manifest.files.values() if not entry.format.binary)
    return "crlf" if counts["crlf"] > counts["lf"] else "lf"


def _copy_ancestor_gitignores(
    repo: Path, app_subfolder: str, workspace: Workspace, manifest: BaselineManifest
) -> None:
    """.gitignore files above the app folder still apply to it, so they are copied too."""
    parts = Path(app_subfolder).parts
    for depth in range(len(parts)):
        relative = "/".join([*parts[:depth], ".gitignore"])
        source = repo / relative
        if source.is_file():
            data = source.read_bytes()
            target = workspace.jail.check(workspace.repo_dir / relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            manifest.files[relative] = ManifestEntry(
                sha256=sha256_of(data),
                size=len(data),
                mtime=source.stat().st_mtime,
                format=detect_format(data),
            )


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")

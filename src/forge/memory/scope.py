"""Memory scopes (spec §12.2 "scope isolation", kept by D-156): what Forge remembers about a Mode A repository
belongs to that repository, what it remembers about a Mode B host belongs to that host profile, and the user's
own preferences are global. Nothing crosses between repositories or profiles."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from forge.safety.paths import real_path
from forge.workspace.workspace import Workspace


def repo_key(repo_path: Path | str, app_subfolder: str) -> str:
    """<repo-slug>-<hash>: one key per repository app folder, shared by all workspaces of it. The format is
    unchanged from the former knowledge-base folder name, so existing scope keys stay valid."""
    resolved = str(real_path(repo_path)).lower()
    digest = hashlib.sha256(f"{resolved}|{app_subfolder}".encode()).hexdigest()[:10]
    slug = "".join(c if c.isalnum() else "-" for c in Path(resolved).name)[:40].strip("-") or "repo"
    return f"{slug}-{digest}"


def scope_of(workspace: Workspace) -> str:
    if workspace.mode_b:
        ref_path = workspace.forge_dir / "host_profile_ref.json"
        ref = json.loads(ref_path.read_text(encoding="utf-8")) if ref_path.exists() else {}
        return f"profile:{ref.get('profile', 'unknown')}"
    return f"repo:{repo_key(workspace.info.repo_path, workspace.info.app_subfolder)}"


def project_dir(home: Path, scope: str) -> Path:
    """<forge_home>/memory/scopes/<scope>/: this project's memories, FORGE.md and skills (D-160)."""
    return home / "memory" / "scopes" / re.sub(r"[^A-Za-z0-9._-]", "-", scope)


def repo_level_dir(home: Path, workspace: Workspace, profile_root: Path | None) -> Path:
    """Where the repository-level FORGE.md and skills live: the host profile folder in Mode B, otherwise the
    project folder. A FORGE.md written into the old knowledge-base folder is copied over once."""
    if profile_root is not None:
        return profile_root
    folder = project_dir(home, scope_of(workspace))
    target = folder / "FORGE.md"
    legacy = home / "kb" / repo_key(workspace.info.repo_path, workspace.info.app_subfolder) / "FORGE.md"
    if not target.exists() and legacy.exists():
        folder.mkdir(parents=True, exist_ok=True)
        target.write_text(legacy.read_text(encoding="utf-8"), encoding="utf-8")
    return folder

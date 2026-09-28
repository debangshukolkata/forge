"""Scope keys (spec §12.2 "scope isolation"): Mode A knowledge belongs to one repository (its KB), Mode B
knowledge to one host profile; nothing crosses unless promoted to "global"."""

from __future__ import annotations

import json
from pathlib import Path

from forge.kb.store import kb_dir_for
from forge.workspace.workspace import Workspace


def scope_of(workspace: Workspace, home: Path) -> str:
    if workspace.mode_b:
        ref_path = workspace.forge_dir / "host_profile_ref.json"
        ref = json.loads(ref_path.read_text(encoding="utf-8")) if ref_path.exists() else {}
        return f"profile:{ref.get('profile', 'unknown')}"
    return f"repo:{kb_dir_for(home, workspace.info.repo_path, workspace.info.app_subfolder).name}"


def visible_scopes(scope: str) -> tuple[str, ...]:
    """What a workspace may see: its own repo/profile, global lessons, and the user's preferences."""
    return (scope, "global", "user")

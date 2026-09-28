"""Remembers per-repository answers (e.g. which sub-folder is the Python app) in Forge home (spec §6.1)."""

from __future__ import annotations

import json
from pathlib import Path

from forge.safety.paths import real_path


def _store(home: Path) -> Path:
    return home / "repos.json"


def remembered_app_folder(home: Path, repo: Path) -> str | None:
    path = _store(home)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    value = data.get(str(real_path(repo)), {}).get("app_subfolder")
    return str(value) if value else None


def remember_app_folder(home: Path, repo: Path, app_subfolder: str) -> None:
    path = _store(home)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    data.setdefault(str(real_path(repo)), {})["app_subfolder"] = app_subfolder
    home.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")

"""Deleting a project (D-226): removes the project's workspace folder (repo copy, output, transcripts) and
its entry in the recent list. What Forge learned about the repository or host (memories, FORGE.md, the
Mode B host profile) is shared by every project of that repository or host, so it is kept."""

from __future__ import annotations

import contextlib
import os
import shutil
import stat
from pathlib import Path
from typing import Any

from forge.errors import ForgeError


class ProjectDeleteError(ForgeError):
    pass


def _is_inside(inner: Path, outer: Path) -> bool:
    return inner == outer or outer in inner.parents


def check_deletable(root: Path, home: Path, known: list[dict[str, Any]]) -> None:
    """Refuses anything Forge did not make, or whose folder holds something that must survive."""
    resolved = root.resolve()
    entry = next((e for e in known if Path(e["path"]).resolve() == resolved), None)
    if entry is None or not (resolved / ".forge" / "workspace.json").is_file():
        raise ProjectDeleteError("That is not a project Forge knows about.")
    if resolved.parent == resolved or _is_inside(home.resolve(), resolved):
        raise ProjectDeleteError("That folder contains Forge's own data folder, so it is not deleted.")
    repo = str(entry.get("repo", ""))
    if not repo.startswith("standalone") and _is_inside(Path(repo).resolve(), resolved):
        raise ProjectDeleteError(
            "Your original repository is inside this project folder, so it is not deleted."
        )


def _clear_read_only(root: Path) -> None:
    """Windows refuses to delete read-only files (git objects, repo copies); clear the flag first."""
    for folder, _dirs, files in os.walk(root):
        for name in files:
            with contextlib.suppress(OSError):
                os.chmod(Path(folder) / name, stat.S_IWRITE)


def remove_project_folder(root: Path) -> None:
    _clear_read_only(root)
    try:
        shutil.rmtree(root)
    except OSError as error:
        raise ProjectDeleteError(
            f"Could not delete everything in {root} ({error}). Close programs using it and try again."
        ) from error

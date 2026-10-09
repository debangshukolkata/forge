"""What Forge has learned, grouped by project, so the user can pick what to forget (D-227).

A group is one memory scope: the notes (and FORGE.md) shared by every project of a repository or host, or
the user's own preferences. Groups come from the project list plus the folders on disk, so notes left behind
by a deleted project still show up under "no project"."""

from __future__ import annotations

import contextlib
import shutil
from pathlib import Path
from typing import Any

from forge.errors import ForgeError
from forge.memory.scope import project_dir
from forge.memory.store import INSTRUCTIONS_FILE, MemoryStore
from forge.modeb.profile import HostProfile, ProfileError, ProfileStore
from forge.web.project_memory import _scope

MAX_TEXT_CHARS = 4000
USER_GROUP = "user"
INSTRUCTIONS_ITEM = "instructions"
PROFILE_ITEM = "profile"


class LearningsError(ForgeError):
    pass


class _Group:
    def __init__(self, group_id: str, notes_folder: Path, instructions_folder: Path | None) -> None:
        self.id = group_id
        self.title = ""
        self.projects: list[str] = []
        self.notes_folder, self.instructions_folder = notes_folder, instructions_folder
        self.profile_root: Path | None = None  # Mode B: the host profile folder

    def store(self, home: Path) -> MemoryStore:
        store = MemoryStore(home, "folder")  # only the folder matters here
        store.folder = self.notes_folder
        return store

    def instructions_file(self) -> Path | None:
        if self.id == USER_GROUP:
            return None
        return (self.instructions_folder or self.notes_folder) / INSTRUCTIONS_FILE


def _groups(home: Path, recent: list[dict[str, Any]]) -> list[_Group]:
    groups: dict[str, _Group] = {USER_GROUP: _Group(USER_GROUP, home / "memory", None)}
    groups[USER_GROUP].title = "Your preferences"
    for entry in recent:
        mode = "B" if str(entry.get("repo", "")).startswith("standalone") else "A"
        scope = _scope(Path(entry["path"]), entry, mode)
        if scope is None:
            continue
        key, profile_name = scope
        folder = project_dir(home, key)
        group = groups.setdefault(folder.name, _Group(folder.name, folder, folder))
        if profile_name is not None:  # Mode B keeps FORGE.md in the host profile folder
            with contextlib.suppress(ProfileError):
                group.profile_root = group.instructions_folder = ProfileStore(home).open(profile_name).root
        group.projects.append(str(entry.get("name", "")))
    scopes = home / "memory" / "scopes"
    for folder in sorted(scopes.iterdir()) if scopes.is_dir() else []:
        if folder.is_dir():
            groups.setdefault(folder.name, _Group(folder.name, folder, folder))
    for group in groups.values():
        if group.id != USER_GROUP:
            group.title = " · ".join(sorted(set(group.projects))) or "No project (left behind)"
    return list(groups.values())


def list_learnings(home: Path, recent: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for group in _groups(home, recent):
        items = [
            {
                "id": f"note:{m.name}",
                "title": m.name,
                "kind": m.kind,
                "description": m.description,
                "text": m.text,
            }
            for m in group.store(home).all()
        ]
        if group.profile_root is not None:
            document = group.profile_root / "PROFILE.md"
            examples = len(HostProfile(group.profile_root).exemplars())
            items.insert(
                0,
                {
                    "id": PROFILE_ITEM,
                    "title": "Host profile",
                    "kind": "profile",
                    "description": (
                        f"What Forge was told about your code ({examples} example(s)). "
                        "Forgetting it also removes this project's FORGE.md; the project starts from scratch."
                    ),
                    "text": document.read_text(encoding="utf-8", errors="replace")[:MAX_TEXT_CHARS]
                    if document.is_file()
                    else "",
                },
            )
        instructions = group.instructions_file()
        if instructions is not None and instructions.is_file():
            text = instructions.read_text(encoding="utf-8", errors="replace")[:MAX_TEXT_CHARS]
            items.insert(
                0,
                {
                    "id": INSTRUCTIONS_ITEM,
                    "title": "FORGE.md",
                    "kind": "instructions",
                    "description": "Instructions for this project",
                    "text": text,
                },
            )
        if items:
            result.append(
                {
                    "id": group.id,
                    "title": group.title,
                    "projects": sorted(set(group.projects)),
                    "items": items,
                }
            )
    return result


def delete_learnings(home: Path, recent: list[dict[str, Any]], selections: dict[str, list[str]]) -> int:
    """`selections` maps a group id to the item ids to forget. Only known groups are honoured."""
    known = {group.id: group for group in _groups(home, recent)}
    if any(group_id not in known for group_id in selections):
        raise LearningsError("Unknown group; reload the list and try again.")
    removed = 0
    for group_id, item_ids in selections.items():
        group = known[group_id]
        store = group.store(home)
        for item_id in item_ids:
            instructions = group.instructions_file()
            if item_id == PROFILE_ITEM and group.profile_root is not None:
                if group.profile_root.is_dir():
                    shutil.rmtree(group.profile_root)
                    removed += 1
            elif item_id == INSTRUCTIONS_ITEM and instructions is not None:
                if instructions.is_file():
                    instructions.unlink()
                    removed += 1
            elif item_id.startswith("note:") and store.delete(item_id[5:]):
                removed += 1
    return removed

"""What Forge remembers about a project, for the "open an existing project" list (D-196): how many notes it
holds, whether a FORGE.md exists, and where the work stands (the `project-state` memory a handoff leaves).
Read from the Forge folder without opening the project, so a long list stays quick."""

from __future__ import annotations

import contextlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from forge.memory.scope import project_dir, repo_key
from forge.memory.store import STATE_MEMORY, MemoryStore
from forge.modeb.profile import ProfileError, ProfileStore

LINE_CHARS = 140
_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


def _scope(root: Path, entry: dict[str, Any], mode: str) -> tuple[str, str | None] | None:
    """The memory scope key and, in Mode B, the host profile name."""
    try:
        if mode == "B":
            ref = json.loads((root / ".forge" / "host_profile_ref.json").read_text(encoding="utf-8"))
            name = str(ref["profile"])
            return f"profile:{name}", name
        return f"repo:{repo_key(entry['repo'], entry.get('app_folder') or '')}", None
    except (OSError, ValueError, KeyError):
        return None


def _section_line(text: str, heading: str) -> str:
    """The first real line under `## <heading>` in a handoff, without its bullet, shortened."""
    found = False
    for line in text.splitlines():
        if line.startswith("#"):
            found = line.lstrip("# ").strip().lower().startswith(heading)
            continue
        if found and line.strip():
            clean = _BULLET.sub("", line).strip()
            return clean if len(clean) <= LINE_CHARS else clean[: LINE_CHARS - 1] + "…"
    return ""


def project_memory(home: Path, root: Path, entry: dict[str, Any], mode: str) -> dict[str, Any]:
    scope = _scope(root, entry, mode)
    empty: dict[str, Any] = {"memories": 0, "instructions": False, "state": None}
    if scope is None:
        return empty
    key, profile_name = scope
    store = MemoryStore(home, key)
    memories = [m for m in store.all() if m.name != STATE_MEMORY]
    folder = project_dir(home, key)
    if profile_name is not None:  # Mode B keeps FORGE.md in the host profile folder
        with contextlib.suppress(ProfileError):
            folder = ProfileStore(home).open(profile_name).root
    state = store.get(STATE_MEMORY)
    summary = None
    if state is not None:
        saved = store.folder / f"{STATE_MEMORY}.md"
        goal = _section_line(state.text, "goal")
        nxt = _section_line(state.text, "next")
        first = next(
            (ln.strip() for ln in state.text.splitlines() if ln.strip() and not ln.startswith("#")), ""
        )
        summary = {
            "goal": goal or first[:LINE_CHARS],
            "next": nxt,
            "saved": datetime.fromtimestamp(saved.stat().st_mtime, UTC).isoformat() if saved.exists() else "",
        }
    return {"memories": len(memories), "instructions": (folder / "FORGE.md").exists(), "state": summary}

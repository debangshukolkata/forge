"""Where things are in DebCraft Home (D-646): what the user edits is at the top, DebCraft's own state is in `data`.

`data_path` finds an entry in the new or the old place, so nothing depends on the move having happened: an entry that
could not be moved (a file in use) is used where it is and moved at a later start. Nothing is overwritten or deleted."""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path

DATA = "data"
MARKER = "layout.json"
README = "README.txt"
README_HEAD = "DebCraft: what is in this folder"
# DebCraft's own files and folders; everything else at the top is the user's or is meant to be looked at.
OWN = (
    "account.json",
    "environment.json",
    "recent_workspaces.json",
    "scratch_registry.json",
    "tokens.json",
    "repos.json",
    "cache",
    "library",
    "profiles",
    "read_grants",
    "browser_profile",
    "certs",
    "sessions",
)
LEFT_OVER = ("learning",)  # folders of features that are gone; kept, out of the way

README_TEXT = f"""{README_HEAD}

Yours to edit
  .env              keys of DebCraft itself (models, databases, search). Never share this file.
  app.env           values for the application you are testing
  app_logins.yaml   how DebCraft signs in to your dev and SIT environments
  tunnels.yaml      how the database tunnel is opened
  config.yaml       models and settings that differ from the defaults
  settings.json     what DebCraft may do without asking (if present)
  FORGE.md, rules, commands, agents, plugins   your own instructions and extensions (if present)

To look at
  reports           what /report and the doctor wrote: the files to send
  logs              log files, also of the tunnel
  skills            installed skills
  memory            what DebCraft learned about you and your repositories

DebCraft's own: leave alone
  data              your local account, sign-in tokens, the list of projects, caches, host profiles.
                    tokens.json and browser_profile are as secret as a password.
                    Forgot the DebCraft password? Delete data\\account.json and start DebCraft again.
"""

_moved_cache: dict[Path, tuple[int, frozenset[str]]] = {}


def _moved(home: Path) -> frozenset[str]:
    marker = home / DATA / MARKER
    try:
        stamp = marker.stat().st_mtime_ns
        cached = _moved_cache.get(marker)
        if cached is not None and cached[0] == stamp:
            return cached[1]
        names = frozenset(str(name) for name in json.loads(marker.read_text(encoding="utf-8"))["moved"])
    except (OSError, ValueError, KeyError, TypeError):
        return frozenset()
    _moved_cache[marker] = (stamp, names)
    return names


def data_path(home: Path, name: str) -> Path:
    """The place of one of DebCraft's own entries: `data/<name>`, or the old place while it is still there."""
    new, old = home / DATA / name, home / name
    if new.exists() or name in _moved(home) or not old.exists():
        return new
    return old


def _move(old: Path, new: Path) -> bool:
    """A rename inside one folder tree: complete or not at all. Never onto something that is there."""
    if not old.exists() or new.exists():
        return False
    try:
        new.parent.mkdir(parents=True, exist_ok=True)
        os.rename(old, new)
    except OSError:
        return False  # in use: it stays where it is and is found there
    return True


def tidy(home: Path) -> list[str]:
    """Moves what is still in the old place; called when the app starts. Returns what it moved."""
    if not home.is_dir():
        return []
    moved = [name for name in OWN if _move(home / name, home / DATA / name)]
    others = [name for name in LEFT_OVER if _move(home / name, home / DATA / "old" / name)]
    others += [log.name for log in sorted(home.glob("tunnel_*.log")) if _move(log, home / "logs" / log.name)]
    with contextlib.suppress(OSError):
        _remember(home, moved)
        _write_readme(home)
    return moved + others


def _remember(home: Path, moved: list[str]) -> None:
    present = {name for name in OWN if (home / DATA / name).exists()}
    names = sorted({*_moved(home), *moved, *present})
    if not names or set(names) == _moved(home):
        return
    marker = home / DATA / MARKER
    scratch = marker.with_suffix(".tmp")
    scratch.write_text(json.dumps({"version": 1, "moved": names}), encoding="utf-8")
    scratch.replace(marker)


def _write_readme(home: Path) -> None:
    target = home / README
    if target.exists():
        text = target.read_text(encoding="utf-8", errors="replace")
        if text == README_TEXT or not text.startswith(README_HEAD):  # a README of the user's own stays
            return
    target.write_text(README_TEXT, encoding="utf-8")

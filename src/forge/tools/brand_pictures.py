"""The user's own pictures, offered first by find_image (TODO DIE6).

A project folder named `brand-assets`, `assets/brand` or `brand` holds what the user supplied: their photographs, their logo, illustrations they
downloaded by hand (for example from unDraw, whose terms do not allow Forge to fetch it). These are listed before any picture from the network,
as `project:<path>` candidates. Nothing leaves the project; the files are read only."""

from __future__ import annotations

import re
from pathlib import Path

from forge.tools.image_sources import Candidate

BRAND_FOLDERS = ("brand-assets", "assets/brand", "brand")
PICTURE_SUFFIXES = {".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif"}
MAX_FILES = 200
MAX_FILE_BYTES = 25 * 1024 * 1024
LICENCE = "supplied by the user"


def _words(text: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", text.lower()) if len(w) > 2}


def _kind(path: Path) -> str:
    name = path.stem.lower()
    if path.suffix == ".svg" and ("undraw" in name or "illustration" in name):
        return "illustration"
    return "icon" if path.suffix == ".svg" and "logo" not in name else "photo"


def project_candidates(root: Path, query: str, limit: int) -> list[Candidate]:
    """Pictures in the project's brand folders, those whose file or folder name matches the query first, then the rest (the user put them there to be used)."""
    wanted = _words(query)
    scored: list[tuple[int, str, Path]] = []
    for folder in BRAND_FOLDERS:
        base = root / folder
        if not base.is_dir():
            continue
        for number, path in enumerate(sorted(base.rglob("*"))):
            if number >= MAX_FILES:
                break
            if (
                path.suffix.lower() not in PICTURE_SUFFIXES
                or not path.is_file()
                or path.stat().st_size > MAX_FILE_BYTES
            ):
                continue
            relative = path.relative_to(root).as_posix()
            scored.append((-len(wanted & _words(relative)), relative, path))
    scored.sort(key=lambda item: (item[0], item[1]))
    found: list[Candidate] = []
    for _, relative, path in scored[:limit]:
        found.append(
            Candidate(
                id=f"project:{relative}",
                source="project",
                kind=_kind(path),
                title=f"{path.stem.replace('-', ' ').replace('_', ' ')} (your own file)",
                licence=LICENCE,
                extra={"file": relative},
            )
        )
    return found

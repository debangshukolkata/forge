"""Slides of a .pptx for the web UI (TODO P1.2): the pictures PowerPoint made of each slide, and the speaker notes.

`preview_presentation` leaves the pictures in `.forge/reports/slides/<deck name>/`; the Files tab asks for them here, and can ask
for them to be made (only where PowerPoint is available). Read-only apart from writing those pictures; the deck path goes through
the same jail and secret check as the file viewer."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException

from forge.errors import ForgeError
from forge.slides import preview
from forge.slides.read import slide_notes
from forge.web.manager import WebSessionManager
from forge.workspace.workspace import Workspace

PREVIEW_FOLDER = ".forge/reports/slides"
MAX_SLIDES = 200


def _number(path: Path) -> int:
    tail = path.stem.rsplit("-", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def describe(workspace: Workspace, deck: Path) -> dict[str, Any]:
    folder = workspace.root / PREVIEW_FOLDER / deck.stem
    pictures = sorted(folder.glob("slide-*.png"), key=_number)[:MAX_SLIDES] if folder.is_dir() else []
    stale = bool(pictures) and deck.stat().st_mtime > min(p.stat().st_mtime for p in pictures) + 1
    try:
        notes = slide_notes(deck)
    except (ForgeError, OSError, ValueError, KeyError):
        notes = []
    root = workspace.root.resolve()
    return {
        "deck": deck.name,
        "pictures": [p.resolve().relative_to(root).as_posix() for p in pictures],
        "notes": notes,
        "stale": stale,
        "can_render": preview.available(),
    }


def add_slide_routes(app: FastAPI, manager: WebSessionManager) -> None:
    def resolve(root: str, path: str) -> tuple[Workspace, Path]:
        workspace = manager.workspace
        if workspace is None:
            raise HTTPException(409, "No workspace is open.")
        base = {"repo": workspace.repo_dir, "output": workspace.output_dir}.get(root)
        if base is None:
            raise HTTPException(400, "root must be repo or output")
        try:
            deck = workspace.jail.check(base / path)
            deck.resolve().relative_to(base.resolve())
        except (ForgeError, ValueError) as error:
            raise HTTPException(403, "Path outside the workspace") from error
        if workspace.is_secret(path.replace("\\", "/")):
            raise HTTPException(403, "Secret files are never shown")
        if deck.suffix.lower() != ".pptx" or not deck.is_file():
            raise HTTPException(404, "No such presentation")
        return workspace, deck

    @app.get("/api/slides")
    async def slides(root: str, path: str) -> dict[str, Any]:
        workspace, deck = resolve(root, path)
        return await asyncio.to_thread(describe, workspace, deck)

    @app.post("/api/slides/render")
    async def render(root: str, path: str) -> dict[str, Any]:
        workspace, deck = resolve(root, path)
        folder = workspace.jail.check(workspace.root / PREVIEW_FOLDER / deck.stem)
        try:
            await asyncio.to_thread(preview.export_slides, deck, folder)
        except preview.PreviewUnavailable as error:
            raise HTTPException(409, str(error)) from error
        return await asyncio.to_thread(describe, workspace, deck)

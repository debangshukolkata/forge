"""Serves an image the agent is looking at, so the chat can show it (D-253).

The event carries only a workspace-relative path; this route turns it into bytes for the signed-in user's browser.
It is deliberately narrow: images only, inside the open workspace, never a secret file, never a symlink out."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from forge.web.manager import WebSessionManager

IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
MAX_IMAGE_BYTES = 12 * 1024 * 1024


def add_image_routes(app: FastAPI, manager: WebSessionManager) -> None:
    @app.get("/api/image")
    async def image(path: str) -> FileResponse:
        workspace = manager.workspace
        if workspace is None:
            raise HTTPException(409, "No workspace is open.")
        relative = path.replace("\\", "/").lstrip("/")
        media_type = IMAGE_TYPES.get("." + relative.rsplit(".", 1)[-1].lower()) if "." in relative else None
        if media_type is None:
            raise HTTPException(403, "Only images can be shown here")
        root = workspace.root.resolve()
        target = (root / relative).resolve()
        try:
            inside = target.relative_to(root).as_posix()
        except ValueError as error:
            raise HTTPException(403, "Path outside the workspace") from error
        if workspace.is_secret(inside):
            raise HTTPException(403, "Secret files are never shown")
        if not target.is_file():
            raise HTTPException(404, "No such image")
        if target.stat().st_size > MAX_IMAGE_BYTES:
            raise HTTPException(413, "That image is too large to show")
        return FileResponse(target, media_type=media_type)

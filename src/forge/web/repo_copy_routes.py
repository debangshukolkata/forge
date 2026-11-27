"""Copy to source (D-674): the red card that replaces one file in the user's repository with the delivered one.

GET shows what would happen and hands out a one-time code; only a POST with that code copies. The code lives in
memory for a few minutes, so a request that did not come from the card the user saw (the model calling this server
with http_request has neither the server token nor the sign-in anyway) cannot copy."""

from __future__ import annotations

import asyncio
import secrets
import time
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from forge.config import forge_home
from forge.errors import ForgeError
from forge.toolkit import field_log
from forge.web.manager import WebSessionManager
from forge.workspace.to_repository import CopyPlan, RepoCopyError, copy_to_repository, plan_copy, undo_copy
from forge.workspace.workspace import Workspace

CODE_LIFETIME_S = 300


class CopyRequest(BaseModel):
    code: str


class UndoRequest(BaseModel):
    copy_id: str


def add_repo_copy_routes(app: FastAPI, manager: WebSessionManager) -> None:
    pending: dict[str, tuple[float, str, str]] = {}  # code -> (expires, workspace root, relative path)

    def current() -> Workspace:
        if manager.workspace is None:
            raise HTTPException(409, "No workspace is open.")
        return manager.workspace

    def describe(plan: CopyPlan) -> dict[str, Any]:
        return {
            "relative": plan.relative,
            "source": str(plan.source),
            "target": str(plan.target),
            "status": plan.status,
            "target_exists": plan.target_exists,
            "state": plan.state,
            "edited_lines": plan.edited_lines,
            "temporary": plan.temporary,
            "command": plan.command,
        }

    @app.get("/api/repo-copy")
    async def preview(path: str) -> dict[str, Any]:
        workspace = current()
        try:
            plan = await asyncio.to_thread(plan_copy, workspace, path)
        except (RepoCopyError, ForgeError, OSError) as error:
            raise HTTPException(400, str(error)) from error
        now = time.time()
        for code in [code for code, (expires, _, _) in pending.items() if expires < now]:
            del pending[code]
        code = secrets.token_urlsafe(24)
        pending[code] = (now + CODE_LIFETIME_S, str(workspace.root), plan.relative)
        return {**describe(plan), "code": code}

    @app.post("/api/repo-copy")
    async def copy(body: CopyRequest) -> dict[str, Any]:
        workspace = current()
        expires, root, relative = pending.pop(body.code, (0.0, "", ""))
        if expires < time.time() or root != str(workspace.root):
            raise HTTPException(403, "This card has expired; open it again.")
        try:
            plan = await asyncio.to_thread(plan_copy, workspace, relative)  # again: the file may have changed
            copy_id = await asyncio.to_thread(copy_to_repository, workspace, plan)
        except (RepoCopyError, ForgeError, OSError) as error:
            raise HTTPException(400, str(error)) from error
        field_log.write(
            "repo_copy",
            forge_home(),
            file=plan.relative,
            replaced=plan.target_exists,
            edited_lines=plan.edited_lines,
        )
        return {"copy_id": copy_id, "target": str(plan.target)}

    @app.post("/api/repo-copy/undo")
    async def undo(body: UndoRequest) -> dict[str, Any]:
        workspace = current()
        try:
            relative = await asyncio.to_thread(undo_copy, workspace, body.copy_id)
        except (RepoCopyError, ForgeError, OSError) as error:
            raise HTTPException(400, str(error)) from error
        field_log.write("repo_copy_undone", forge_home(), file=relative)
        return {"relative": relative}

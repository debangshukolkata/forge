"""Serves the full result of a tool call on request (D-195): the event only carries a preview."""

from __future__ import annotations

import re
from typing import Any

from fastapi import FastAPI, HTTPException

from forge.agent.tool_output import FOLDER
from forge.web.manager import WebSessionManager

OUTPUT_ID = re.compile(r"[0-9a-f]{32}")  # only what `save_full_output` makes, so no path can be smuggled in


def add_tool_output_routes(app: FastAPI, manager: WebSessionManager) -> None:
    @app.get("/api/tool-output/{output_id}")
    async def tool_output(output_id: str) -> dict[str, Any]:
        workspace = manager.workspace
        if workspace is None:
            raise HTTPException(400, "No project is open")
        if not OUTPUT_ID.fullmatch(output_id):
            raise HTTPException(404, "No such output")
        path = workspace.forge_dir / FOLDER / f"{output_id}.txt"
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            raise HTTPException(404, "That output is no longer available") from error
        return {"text": text, "chars": len(text)}

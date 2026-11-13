"""The conversations of the open project (D-582): list, start, open and rename. A switch while the agent works
answers 409 `busy` unless the caller says `stop_running` (the chat asks the user first)."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from forge.errors import ConversationBusyError, ConversationError
from forge.web.manager import WebSessionManager


class NewConversation(BaseModel):
    title: str = Field(default="", max_length=200)
    stop_running: bool = False


class OpenConversation(BaseModel):
    id: str = Field(max_length=16)
    stop_running: bool = False


class RenameConversation(BaseModel):
    id: str = Field(max_length=16)
    title: str = Field(max_length=200)


def add_conversation_routes(app: FastAPI, manager: WebSessionManager) -> None:
    async def switch(conversation_id: str | None, title: str, stop_running: bool) -> Any:
        try:
            chosen = await manager.switch_conversation(conversation_id, title, stop_running)
        except ConversationBusyError as error:
            return JSONResponse({"detail": str(error), "busy": True}, status_code=409)
        except ConversationError as error:
            raise HTTPException(404, str(error)) from error
        return {"id": chosen}

    @app.get("/api/conversations")
    async def conversations() -> dict[str, Any]:
        return manager.conversations()

    @app.post("/api/conversations")
    async def new_conversation(body: NewConversation) -> Any:
        return await switch(None, body.title, body.stop_running)

    @app.post("/api/conversations/open")
    async def open_conversation(body: OpenConversation) -> Any:
        return await switch(body.id, "", body.stop_running)

    @app.post("/api/conversations/rename")
    async def rename_conversation(body: RenameConversation) -> dict[str, Any]:
        try:
            manager.rename_conversation(body.id, body.title)
        except ConversationError as error:
            raise HTTPException(404, str(error)) from error
        return manager.conversations()

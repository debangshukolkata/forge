"""The Contracts panel's endpoints (D-129, Mode B): list, pin or revise, and forget the interface contracts
the user pinned for this project's host profile. Pinning goes through the same `contract_pin` tool the chat
uses, so a contract entered here is also remembered as project memory, and the pinned context is refreshed
at once."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from forge.modeb.contracts import ContractRegister
from forge.tools.modeb import ContractPin
from forge.web.manager import WebSessionManager


class PinContract(BaseModel):
    seam: str = Field(max_length=64)
    signature: str = Field(min_length=1, max_length=4000)
    note: str = Field(default="", max_length=1000)


def add_contracts_routes(app: FastAPI, manager: WebSessionManager) -> None:
    def register() -> ContractRegister | None:
        host = manager.host
        profile = host.host_profile() if host is not None else None
        return ContractRegister(profile) if profile is not None else None

    def listing(items: ContractRegister | None) -> dict[str, Any]:
        # `available` is False outside Mode B: Mode A reads the repository itself, there are no seams to pin.
        if items is None:
            return {"available": False, "contracts": []}
        return {"available": True, "contracts": [c.model_dump() for c in items.all()]}

    @app.get("/api/contracts")
    async def contracts() -> dict[str, Any]:
        return listing(register())

    @app.post("/api/contracts")
    async def pin(body: PinContract) -> dict[str, Any]:
        host = manager.host
        items = register()
        if host is None or host.agent is None or items is None:
            raise HTTPException(400, "Contracts belong to a Standalone (Mode B) project.")
        result = await ContractPin().run(
            ContractPin.Args(seam=body.seam, signature=body.signature, note=body.note), host.agent.context
        )
        if not result.ok:
            raise HTTPException(400, result.content)
        host.refresh_profile_pin()  # the next model call sees the new contract
        return listing(items)

    @app.delete("/api/contracts/{seam_or_id}")
    async def forget(seam_or_id: str) -> dict[str, Any]:
        host = manager.host
        items = register()
        if host is None or items is None:
            raise HTTPException(400, "Contracts belong to a Standalone (Mode B) project.")
        if not items.forget(seam_or_id):
            raise HTTPException(404, "No such contract")
        host.refresh_profile_pin()
        return listing(items)

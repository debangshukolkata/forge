"""The setup screen's endpoints (D-186): live checks one at a time, the model plan and its confirmation.
Nothing here returns or stores a secret value; check details are redacted in `environment.checks`."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from forge.config import ForgeConfig, load_config
from forge.environment import store
from forge.environment.checks import CHECKS, KNOWN_IDS, run_check
from forge.environment.plan import propose_plan, validate_plan
from forge.errors import ForgeError
from forge.web.manager import WebSessionManager


class ConfirmedPlan(BaseModel):
    roles: dict[str, str]


def add_environment_routes(app: FastAPI, manager: WebSessionManager) -> None:
    def config() -> ForgeConfig:
        try:
            return load_config(manager.home)
        except ForgeError as error:
            raise HTTPException(400, str(error)) from error

    def overview() -> dict[str, Any]:
        saved = store.load(manager.home)
        return {
            "checks": [asdict(check) for check in CHECKS],
            "saved": saved,
            "plan": propose_plan(config(), saved["results"], saved["plan"]),
        }

    @app.get("/api/environment")
    async def environment() -> dict[str, Any]:
        return overview()

    @app.post("/api/environment/check/{check_id}")
    async def check(check_id: str) -> dict[str, Any]:
        if check_id not in KNOWN_IDS:
            raise HTTPException(404, "No such check")
        result = (await run_check(check_id)).to_dict()
        store.save_result(manager.home, check_id, result)
        return {"result": result, "plan": overview()["plan"]}

    @app.post("/api/environment/confirm")
    async def confirm(body: ConfirmedPlan) -> dict[str, Any]:
        try:
            roles = validate_plan(config(), body.roles)
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        store.save_plan(manager.home, roles)
        host = manager.host  # a session is already open for the new project: switch its roles now
        if host is not None:
            for role, key in roles.items():
                host.router.set_role_model(role, key)
        return overview()

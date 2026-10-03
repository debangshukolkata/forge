"""The setup screen's endpoints (D-186): live checks one at a time, the model plan and its confirmation.
Nothing here returns or stores a secret value; check details are redacted in `environment.checks`."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from forge.config import ForgeConfig, load_config
from forge.environment import store
from forge.environment.checks import ASKED_IDS, CHECKS, KNOWN_IDS, not_in_use, run_check
from forge.environment.plan import propose_plan, validate_plan
from forge.errors import ForgeError
from forge.tools.vision import ocr_tools
from forge.web.manager import WebSessionManager


class ConfirmedPlan(BaseModel):
    roles: dict[str, str]


class Answer(BaseModel):
    check: str
    enabled: bool


def add_environment_routes(app: FastAPI, manager: WebSessionManager) -> None:
    def sync_ocr_tool() -> None:
        """A yes (and a passing test) on the drawer gives the open session the `ocr_image` tool now; a no
        takes it away. A session started later gets it from the saved answer (D-203)."""
        host = manager.host
        if host is None or host.agent is None:
            return
        tools = host.agent.tools
        if store.tesseract_ready(manager.home):
            if tools.get("ocr_image") is None:
                for tool in ocr_tools():
                    tools.add(tool)
        else:
            tools.remove("ocr_image")

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
        # Tools the user may not have (Tesseract, Gemini) are only tested after a "yes" (D-201): the server
        # holds to that too, whatever the page asks for.
        answer = store.load(manager.home)["answers"].get(check_id)
        if check_id in ASKED_IDS and answer is not True:
            result = not_in_use(check_id, said_no=answer is False).to_dict()
        else:
            result = (await run_check(check_id)).to_dict()
        store.save_result(manager.home, check_id, result)
        if check_id == "tesseract":
            sync_ocr_tool()
        return {"result": result, "plan": overview()["plan"]}

    @app.post("/api/environment/answer")
    async def answer(body: Answer) -> dict[str, Any]:
        if body.check not in ASKED_IDS:
            raise HTTPException(400, "That check is not optional")
        store.save_answer(manager.home, body.check, body.enabled)
        if not body.enabled:  # nothing to test: show it as not in use right away
            store.save_result(manager.home, body.check, not_in_use(body.check, said_no=True).to_dict())
        if body.check == "tesseract":
            sync_ocr_tool()
        return overview()

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

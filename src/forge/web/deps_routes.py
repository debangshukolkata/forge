"""The Dependencies section (D-238): what the open project uses, and, only when the user asks, which
libraries have known vulnerabilities."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException

from forge.config import forge_home
from forge.deps import audit
from forge.deps.check import run_check
from forge.deps.model import CheckResult, Dependency
from forge.deps.scan import scan_project
from forge.modeb.profile import ProfileError, ProfileStore
from forge.modeb.workspace import profile_ref
from forge.web.manager import WebSessionManager
from forge.workspace.workspace import Workspace

SAVED = "dependency_check.json"


def _scan(workspace: Workspace) -> list[Dependency]:
    env = workspace.info.python_env
    venv = Path(env.venv) if env is not None else None
    host_packages: dict[str, str] = {}
    if (
        workspace.mode_b
    ):  # a standalone project has no manifests of the host: its profile lists the host's libraries
        try:
            host_packages = (
                ProfileStore(forge_home()).open(str(profile_ref(workspace).get("profile"))).packages()
            )
        except (ProfileError, OSError, ValueError):
            host_packages = {}
    return scan_project(workspace.repo_dir, venv, host_packages)


def _saved(workspace: Workspace) -> CheckResult | None:
    try:
        return CheckResult.model_validate_json((workspace.forge_dir / SAVED).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def add_deps_routes(app: FastAPI, manager: WebSessionManager) -> None:
    def current() -> Workspace:
        if manager.workspace is None:
            raise HTTPException(400, "No project is open")
        return manager.workspace

    @app.get("/api/dependencies")
    async def dependencies() -> dict[str, Any]:
        workspace = current()
        found = await asyncio.to_thread(_scan, workspace)
        saved = _saved(workspace)
        return {
            "dependencies": [d.model_dump() for d in found],
            "last_check": saved.model_dump() if saved else None,
            "pip_audit_installed": audit.available(),
            "standalone": workspace.mode_b,
        }

    @app.post("/api/dependencies/check")
    async def check() -> dict[str, Any]:
        """Sends library names and versions to osv.dev and PyPI: the page asks the user first."""
        workspace = current()
        found = await asyncio.to_thread(_scan, workspace)
        result = await asyncio.to_thread(run_check, found)
        path = workspace.jail.check(workspace.forge_dir / SAVED)
        path.write_text(result.model_dump_json(indent=1), encoding="utf-8")
        return result.model_dump()

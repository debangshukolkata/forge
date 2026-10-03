"""The web UI server (spec §15A.3): FastAPI with one WebSocket for events + inputs and a small REST API for
workspaces, files, diffs, output.zip, config and doctor. Every request passes ServerSecurity; file access is
confined to the workspace (repo/ and output/), and secret files are never served."""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import secrets
import zipfile
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from importlib import resources
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, ValidationError
from starlette.staticfiles import StaticFiles

from forge.config import ROLES
from forge.errors import ForgeError
from forge.protocol.inputs import parse_user_input
from forge.safety.server_security import ServerSecurity
from forge.web.accounts import AccountStore
from forge.web.auth_routes import add_auth_routes, add_no_login_route, needs_login, session_cookie_name
from forge.web.contracts_routes import add_contracts_routes
from forge.web.environment_routes import add_environment_routes
from forge.web.manager import WebSessionManager
from forge.web.project_list import describe_projects
from forge.web.tool_output_routes import add_tool_output_routes
from forge.workspace.output import build_output, build_patch, compute_changes
from forge.workspace.text_format import decode_text, detect_format
from forge.workspace.workspace import Workspace

UI = Path(str(resources.files("forge.web") / "react"))  # the React UI, built by ui-react (npm run build)
MAX_FILE_BYTES = 1_000_000
MAX_UPLOAD_BYTES = 25 * 1_048_576  # attachments (images, PDFs, documents)
MAX_FILE_MATCHES = 20  # @-mention suggestions
Stopper = Callable[[], Awaitable[None]]


class NewWorkspace(BaseModel):
    repo: str
    workspace: str
    app_folder: str | None = None


class NewProject(BaseModel):
    mode: Literal["A", "B"] = "B"
    project: str
    folder: str
    repo: str = ""  # Mode A: the existing project / repository (read only)
    app_folder: str = ""  # Mode A: only when Forge can't tell which sub-folder holds the Python app
    sensitive_terms: str = ""  # Mode B, new project: names that must never reach a web search


class NewStandalone(BaseModel):
    workspace: str
    profile: str


class OpenWorkspace(BaseModel):
    workspace: str


class SetupSecrets(BaseModel):
    """Body for POST /api/setup/secrets: name -> value, restricted to doctor's own required-names list
    (never an arbitrary-file-write primitive — see the handler)."""

    values: dict[str, str]


def create_app(
    manager: WebSessionManager,
    security: ServerSecurity,
    on_quit: Stopper | None = None,
    accounts: AccountStore | None = None,
) -> FastAPI:
    # accounts=None: no login. Only tests build the app that way; `forge ui` always passes one.
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    session_cookie = session_cookie_name(security)
    add_environment_routes(app, manager)
    add_contracts_routes(app, manager)
    add_tool_output_routes(app, manager)
    if accounts:
        add_auth_routes(app, accounts, security)
    else:
        add_no_login_route(app)

    @app.middleware("http")
    async def guard(request: Request, call_next: Any) -> Response:
        problem = security.check(request.headers, request.cookies, request.query_params.get("t"))
        if problem is not None:
            return JSONResponse({"error": f"Forbidden: {problem}"}, status_code=403)
        if (
            accounts
            and needs_login(request.url.path)
            and not accounts.signed_in(request.cookies.get(session_cookie))
        ):
            return JSONResponse({"error": "Sign in first"}, status_code=401)
        response: Response = await call_next(request)
        response.headers["Content-Security-Policy"] = security.content_security_policy()
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    async def index(request: Request) -> Response:
        if request.query_params.get("t"):  # first load: move the token into the cookie, off the URL
            # React dev mode: the page itself comes from the Vite dev server (same host: it gets the cookie).
            redirect = RedirectResponse(
                f"{security.dev_origin}/" if security.dev_origin else "/", status_code=303
            )
            redirect.set_cookie(
                security.cookie_name, security.token, httponly=True, samesite="strict", path="/"
            )
            return redirect
        if not (UI / "index.html").exists():
            missing = {"error": "The web UI isn't built: cd ui-react; npm run build"}
            return JSONResponse(missing, status_code=503)
        return FileResponse(UI / "index.html", media_type="text/html")

    if (UI / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=UI / "assets"), name="assets")

    @app.get("/favicon.svg")
    async def favicon() -> Response:
        return FileResponse(UI / "favicon.svg", media_type="image/svg+xml")

    # --- state and workspaces ---

    @app.get("/api/state")
    async def state() -> dict[str, Any]:
        host, workspace = manager.host, manager.workspace
        if host is None or workspace is None:
            return {"workspace": None, "recent": manager.recent()}
        orchestrator = host.orchestrator
        return {
            "workspace": {
                "path": str(workspace.root),
                "name": workspace.info.project or workspace.info.name,
                "repo": workspace.info.repo_path or "standalone (Mode B)",
                "mode": workspace.info.mode,
                "app_folder": workspace.info.app_subfolder,
            },
            "busy": host.busy,
            "pending": [*host.approvals.pending_ids, *host.questions.pending_ids],
            "last_seq": host.bus.last_seq,
            # No fixed phase any more (D-128/D-131): "phase" is kept as a coarse status string so the
            # (not-yet-redesigned, D-131) React UI degrades instead of breaking; prefer "cadence"/"tasks".
            "phase": orchestrator.state.resume_summary() if orchestrator else "direct",
            "cadence": orchestrator.state.cadence if orchestrator else "default",
            "tasks": [t.model_dump() for t in orchestrator.state.tasks] if orchestrator else [],
            "current_task": orchestrator.state.current_task if orchestrator else None,
            "mode": host.agent.gate.mode if host.agent else None,
            "database": host.db.status_line() if host.db else None,
            "db_requests": [r.model_dump() for r in host.db.requests.all()] if host.db else [],
            "recent": manager.recent(),
        }

    @app.post("/api/workspaces")
    async def new_workspace(body: NewWorkspace) -> dict[str, str]:
        try:
            workspace = await manager.new_workspace(Path(body.repo), Path(body.workspace), body.app_folder)
        except (ForgeError, OSError, ValueError) as error:
            raise HTTPException(400, str(error)) from error
        return {"path": str(workspace.root)}

    @app.post("/api/projects")
    async def new_project(body: NewProject) -> dict[str, str]:
        """The start form: project name + project folder in both modes, plus the existing repo in Mode A."""
        from forge.modeb.profile import ProfileStore, project_slug

        try:
            name = body.project.strip()
            if not name:
                raise ValueError("Enter a project name.")
            if not body.folder.strip():
                raise ValueError("Enter the project folder (a new, empty folder).")
            if body.mode == "A":
                if not body.repo.strip():
                    raise ValueError("Enter the path of the existing project / repository.")
                workspace = await manager.new_workspace(
                    Path(body.repo.strip()), Path(body.folder.strip()), body.app_folder.strip() or None, name
                )
                return {"path": str(workspace.root)}
            # Mode B: the project's knowledge (its profile) is reused when the same name comes back.
            store, slug = ProfileStore(manager.home), project_slug(name)
            if slug not in store.names():
                terms = [t.strip() for t in body.sensitive_terms.split(",") if t.strip()]
                store.create(slug, terms)
            workspace = await manager.new_standalone(Path(body.folder.strip()), slug, name)
        except (ForgeError, OSError, ValueError) as error:
            raise HTTPException(400, str(error)) from error
        from forge.modeb.workspace import test_runner_note

        return {"path": str(workspace.root), "test_runner": test_runner_note(workspace)}

    @app.get("/api/setup-progress")
    async def setup_progress() -> dict[str, str | None]:
        """Polled by the start form while creating a project (spec: Home.tsx), since setup runs as one
        blocking call before the session's WebSocket exists — there's nowhere else to publish progress."""
        return {"phase": manager.setup_progress}

    @app.post("/api/standalone")
    async def new_standalone(body: NewStandalone) -> dict[str, str]:
        try:
            workspace = await manager.new_standalone(Path(body.workspace), body.profile)
        except (ForgeError, OSError, ValueError) as error:
            raise HTTPException(400, str(error)) from error
        from forge.modeb.workspace import test_runner_note

        return {"path": str(workspace.root), "test_runner": test_runner_note(workspace)}

    @app.get("/api/learning")
    async def learning() -> dict[str, Any]:
        """The lessons/library/improvements panel was retired with the learning module (D-156); the endpoint
        stays, empty, until the timeline UI replaces that panel, so the current UI keeps rendering."""
        return {"lessons": [], "cards": [], "improvements": []}

    @app.get("/api/evals")
    async def evals() -> list[dict[str, Any]]:
        history = current().forge_dir / "reports" / "eval-history.jsonl"
        if not history.exists():
            return []
        return [json.loads(line) for line in history.read_text(encoding="utf-8").splitlines() if line.strip()]

    @app.get("/api/evals/{number}")
    async def eval_report(number: int) -> dict[str, Any]:
        reports = current().forge_dir / "reports"
        report = reports / f"eval-{number}.md"
        if not report.exists():
            raise HTTPException(404, "No such eval run")
        overlays = sorted(p.name for p in (reports / f"eval-{number}").glob("*.png"))
        return {"markdown": report.read_text(encoding="utf-8"), "overlays": overlays}

    @app.get("/api/evals/{number}/overlay/{name}")
    async def eval_overlay(number: int, name: str) -> Response:
        folder = (current().forge_dir / "reports" / f"eval-{number}").resolve()
        path = (folder / name).resolve()
        if path.parent != folder or path.suffix != ".png" or not path.is_file():
            raise HTTPException(404, "No such overlay")
        return FileResponse(path, media_type="image/png")

    @app.get("/api/projects")
    async def project_list() -> list[dict[str, Any]]:
        return describe_projects(manager.recent(), manager.home)

    @app.get("/api/profiles")
    async def profiles() -> list[str]:
        from forge.modeb.profile import ProfileStore

        return ProfileStore(manager.home).names()

    @app.post("/api/open")
    async def open_workspace(body: OpenWorkspace) -> dict[str, str]:
        try:
            workspace = await manager.open_workspace(Path(body.workspace))
        except (ForgeError, OSError, ValueError) as error:
            raise HTTPException(400, str(error)) from error
        return {"path": str(workspace.root)}

    # --- files, diffs, output ---

    def current() -> Workspace:
        if manager.workspace is None:
            raise HTTPException(409, "No workspace is open.")
        return manager.workspace

    def locate(workspace: Workspace, root: str, relative: str) -> Path:
        base = {"repo": workspace.repo_dir, "output": workspace.output_dir}.get(root)
        if base is None:
            raise HTTPException(400, "root must be repo or output")
        try:
            path = workspace.jail.check(base / relative) if relative else base
            path.resolve().relative_to(base.resolve())
        except (ForgeError, ValueError) as error:
            raise HTTPException(403, "Path outside the workspace") from error
        if relative and workspace.is_secret(relative.replace("\\", "/")):
            raise HTTPException(403, "Secret files are never shown")
        return path

    @app.get("/api/tree")
    async def tree(root: str = "repo", dir: str = "") -> dict[str, Any]:
        workspace = current()
        folder = locate(workspace, root, dir)
        if not folder.is_dir():
            raise HTTPException(404, "No such folder")
        statuses = {c.path: c.status for c in compute_changes(workspace)} if root == "repo" else {}
        entries = []
        for child in sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            relative = child.relative_to(
                workspace.repo_dir if root == "repo" else workspace.output_dir
            ).as_posix()
            if child.name in ("venv", ".venv", "__pycache__", "node_modules", ".git"):
                continue
            changed = [s for p, s in statuses.items() if p == relative or p.startswith(relative + "/")]
            entries.append(
                {
                    "name": child.name,
                    "path": relative,
                    "dir": child.is_dir(),
                    "status": statuses.get(relative) or ("changed" if changed else None),
                }
            )
        return {"root": root, "dir": dir, "entries": entries}

    @app.get("/api/file")
    async def read_file(root: str, path: str) -> dict[str, Any]:
        file = locate(current(), root, path)
        if not file.is_file():
            raise HTTPException(404, "No such file")
        data = file.read_bytes()[: MAX_FILE_BYTES + 1]
        file_format = detect_format(data)
        if file_format.binary:
            return {"path": path, "binary": True, "text": ""}
        return {
            "path": path,
            "binary": False,
            "truncated": len(data) > MAX_FILE_BYTES,
            "text": decode_text(data[:MAX_FILE_BYTES], file_format),
        }

    @app.post("/api/upload")
    async def upload(request: Request, name: str) -> dict[str, str]:
        """An attachment (file picker, paste or drag-and-drop): stored in .forge/inputs/ and referenced in the
        message as @.forge/inputs/<file>. Raw body (no multipart dependency); size-capped; never executed."""
        from forge.parity.mentions import store_input

        data = await request.body()
        if not data:
            raise HTTPException(400, "Empty file.")
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"Files up to {MAX_UPLOAD_BYTES // 1_048_576} MB can be attached.")
        try:
            stored = store_input(current(), name, data)
        except (ForgeError, OSError, ValueError) as error:
            raise HTTPException(400, str(error)) from error
        return stored

    @app.get("/api/files")
    async def find_files(q: str = "") -> list[str]:
        """@-mention autocomplete: project files whose path contains the query (never ignored/secret ones)."""
        from forge.tools.search import workspace_files

        workspace = current()
        needle = q.lower().replace("\\", "/")
        found = []
        for path in workspace_files(workspace):
            if needle in path.lower() and not workspace.is_secret(path):
                found.append(path)
                if len(found) >= MAX_FILE_MATCHES:
                    break
        return sorted(found, key=lambda p: (not p.lower().endswith(needle), len(p)))

    @app.get("/api/changes")
    async def changes() -> list[dict[str, Any]]:
        return [c.model_dump() for c in compute_changes(current())]

    @app.get("/api/diff")
    async def diff(path: str | None = None) -> dict[str, str]:
        workspace = current()
        selected = [
            c for c in compute_changes(workspace) if not c.secret and (path is None or c.path == path)
        ]
        return {"patch": build_patch(workspace, selected)}

    @app.get("/api/output.zip")
    async def output_zip() -> Response:
        workspace = current()
        if not any(workspace.output_dir.iterdir()):
            await asyncio.to_thread(build_output, workspace)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(workspace.output_dir.rglob("*")):
                if file.is_file():
                    archive.write(file, file.relative_to(workspace.output_dir).as_posix())
        headers = {"Content-Disposition": f'attachment; filename="{workspace.info.name}-output.zip"'}
        return Response(buffer.getvalue(), media_type="application/zip", headers=headers)

    @app.get("/api/checkpoints")
    async def checkpoints() -> list[dict[str, Any]]:
        return [cp.model_dump() for cp in current().checkpoints.all()]

    # --- settings, doctor, quit ---

    @app.get("/api/config")
    async def config() -> dict[str, Any]:
        host = manager.host
        if host is None:
            from forge.config import CostColors

            return {"roles": {}, "models": [], "cost_colors": CostColors().model_dump()}
        router = host.router
        return {
            "roles": {role: router.model_for_role(role) for role in ROLES},
            "models": sorted(router.config.llm.models),
            "permission_mode": host.agent.gate.mode if host.agent else None,
            "sandbox": router.config.shell.sandbox,
            "limits": router.config.limits.model_dump(),
            "cost_colors": router.config.cost.colors.model_dump(),
        }

    @app.get("/api/doctor")
    async def doctor(offline: bool = True) -> list[dict[str, str]]:
        # offline=True (default): the existing cheap fast path other callers rely on (no live network calls).
        # offline=False: D-145's guided setup screen, run once after the user submits keys (or on first load
        # when secrets already look present) so the connectivity check feels like one continuous flow.
        from forge.doctor import run_doctor

        return [asdict(result) for result in await run_doctor(offline=offline)]

    @app.get("/api/setup")
    async def setup_status() -> dict[str, Any]:
        """Cheap (no live network calls): which required env values are missing, so the frontend can decide
        whether to show the setup screen at all before doing anything else (D-145 — no flash of UI when
        everything's already configured)."""
        from forge.config import forge_home, load_config, load_secrets
        from forge.doctor import missing_secret_names

        home = forge_home()
        try:
            config = load_config(home)
        except ForgeError as error:
            return {"missing": [], "config_error": str(error)[:500]}
        secrets = load_secrets(home)
        return {"missing": missing_secret_names(config, secrets), "config_error": None}

    @app.post("/api/setup/secrets")
    async def setup_secrets(body: SetupSecrets) -> dict[str, bool]:
        """Writes submitted values into Forge's .env. Only names doctor itself lists as required are
        accepted (validated against missing_secret_names/required_secret_names — never an arbitrary-file-
        write primitive). Never echoes a value back, on success or failure."""
        from forge.config import forge_home, load_config, write_secret_values
        from forge.doctor import required_secret_names

        home = forge_home()
        try:
            config = load_config(home)
        except ForgeError as error:
            raise HTTPException(400, str(error)) from error
        allowed = required_secret_names(config)
        unknown = sorted(set(body.values) - allowed)
        if unknown:
            raise HTTPException(400, f"Unrecognized field(s): {', '.join(unknown)}")
        submitted = {name: value for name, value in body.values.items() if value.strip()}
        write_secret_values(submitted, home)
        return {"ok": True}

    @app.post("/api/quit")
    async def quit_server() -> dict[str, bool]:
        await manager.close_session()
        if on_quit is not None:
            asyncio.get_running_loop().call_later(0.2, lambda: asyncio.ensure_future(on_quit()))
        return {"ok": True}

    # --- the event stream and inputs ---

    @app.websocket("/ws")
    async def events(socket: WebSocket) -> None:
        problem = security.check(socket.headers, socket.cookies, None)
        if problem is not None:
            await socket.close(code=4403, reason=problem)
            return
        if accounts and not accounts.signed_in(socket.cookies.get(session_cookie)):
            await socket.close(code=4401, reason="Sign in first")
            return
        await socket.accept()
        client = secrets.token_hex(8)
        try:
            hello = await socket.receive_json()
            await _serve(socket, manager, client, int(hello.get("since", 0)))
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            manager.release(client)

    return app


async def _serve(socket: WebSocket, manager: WebSessionManager, client: str, since: int) -> None:
    """Replays events after `since`, then streams live events while accepting this client's inputs."""
    host = manager.host
    if host is None:
        await socket.send_json({"type": "no_session"})
        await socket.receive_json()  # wait for the page to reconnect after opening a workspace
        return
    controls = manager.claim_control(client)
    await socket.send_json({"type": "hello", "controls": controls, "last_seq": host.bus.last_seq})
    subscription = host.bus.subscribe(since_seq=since)

    async def forward() -> None:
        async for event in subscription:
            await socket.send_json({"type": "event", "event": event.model_dump(mode="json")})

    sender = asyncio.create_task(forward())
    try:
        while True:
            message = await socket.receive_json()
            if message.get("type") == "take_control":
                manager.claim_control(client, take_over=True)
                await socket.send_json({"type": "control", "controls": True})
                continue
            if message.get("type") != "input":
                continue
            if manager.controller != client:
                await socket.send_json({"type": "rejected", "reason": "Another window controls this session"})
                continue
            try:
                await host.submit(parse_user_input(message.get("input") or {}))
            except ValidationError as error:
                await socket.send_json(
                    {"type": "rejected", "reason": f"Invalid input: {error.errors()[0]['msg']}"}
                )
    finally:
        subscription.close()
        sender.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await sender

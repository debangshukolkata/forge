"""`forge ui`: starts the web UI server on 127.0.0.1 and opens it in Edge (spec §15A.1)."""

from __future__ import annotations

import asyncio
import contextlib
import shutil
import socket
import subprocess
import webbrowser
from pathlib import Path

import uvicorn

from forge.config import forge_home
from forge.session import build_session
from forge.web.manager import WebSessionManager
from forge.web.security import ServerSecurity, check_bind_host, check_dev_origin
from forge.web.server import create_app

DEFAULT_PORT = 8765
DEV_ORIGIN = "http://127.0.0.1:5173"  # `npm run dev` (ui-react/vite.config.ts)


def free_port(preferred: int = DEFAULT_PORT) -> int:
    for port in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            chosen: int = probe.getsockname()[1]
            return chosen
    raise OSError("no free port on 127.0.0.1")


def open_browser(url: str) -> None:
    """Edge first (the office laptop's browser), then the default browser."""
    edge = shutil.which("msedge")
    try:
        if edge:
            subprocess.Popen([edge, url])
            return
        subprocess.Popen(["cmd", "/c", "start", "msedge", url])
    except OSError:
        webbrowser.open(url)


async def serve(
    workspace: Path | None,
    port: int | None,
    host: str = "127.0.0.1",
    no_browser: bool = False,
    dev: bool = False,
) -> None:
    bind = check_bind_host(host)
    chosen = free_port(port or DEFAULT_PORT)
    security = ServerSecurity(port=chosen, dev_origin=check_dev_origin(DEV_ORIGIN) if dev else None)
    manager = WebSessionManager(forge_home(), lambda ws: build_session(workspace=ws, orchestrated=True))
    config = uvicorn.Config(None, host=bind, port=chosen, log_level="warning", ws="websockets-sansio")  # type: ignore[arg-type]
    server = uvicorn.Server(config)

    async def stop() -> None:
        server.should_exit = True

    config.app = create_app(manager, security, on_quit=stop)
    if workspace is not None:
        await manager.open_workspace(workspace)
    print(f"Forge web UI: {security.url()}")
    if dev:
        print(f"Dev mode: start the React dev server (cd ui-react; npm run dev); the link opens {DEV_ORIGIN}")
    print("Keep this window open; Ctrl+C stops Forge.")
    if not no_browser:
        open_browser(security.url())
    try:
        await server.serve()
    finally:
        with contextlib.suppress(Exception):
            await manager.close_session()


def run_ui(
    workspace: Path | None,
    port: int | None,
    host: str,
    no_browser: bool,
    dev: bool = False,
) -> int:
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(serve(workspace, port, host, no_browser, dev))
    return 0

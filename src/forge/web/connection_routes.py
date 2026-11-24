"""The connection indicators of the top bar (D-627): one dot per environment DebCraft signs in to and per tunnel.

The state is worked out when it is asked for, never replayed from events: a token ends with time and a tunnel can
close by itself, so only a look at the token store and at the port is true. Names, minutes and the first words of a
reason only; no token ever passes through here. A sign-in or a tunnel is started from here only when the user
clicks its button: reading the state opens no window and starts no program.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from forge.db.tunnel import TunnelError, ensure_tunnel, last_problem, load_tunnels, port_open
from forge.errors import ConfigError
from forge.safety.redact import default_redactor
from forge.toolkit import field_log
from forge.toolkit.app_logins import LOGINS_FILE, TokenStore, load_logins
from forge.toolkit.clipboard import CLEAR_AFTER_S, ClipboardError, clear_now, copy_for_a_minute
from forge.tools.app_login import ensure_token, token_status
from forge.web.manager import WebSessionManager

MAX_REASON = 160


class Named(BaseModel):
    name: str


def _short(text: str) -> str:
    return default_redactor.redact(" ".join(str(text).split()))[:MAX_REASON]


def _last_sign_in(home: Path, env: str) -> dict[str, Any] | None:
    records = [r for r in field_log.read(("sign_in",), home) if r.get("env") == env]
    return records[-1] if records else None


async def _login_item(login: Any, home: Path, check: bool) -> dict[str, Any]:
    status = await token_status(login, home, check=check)
    item: dict[str, Any] = {"kind": "login", "name": login.name, "host": login.host}
    if status.usable:
        left = f"{status.minutes} min left" if status.minutes is not None else "valid"
        return {**item, "state": "ok", "detail": f"signed in, {left}", "minutes": status.minutes}
    last = _last_sign_in(home, login.name)
    if status.state == "rejected" or (last is not None and not last.get("ok")):
        reason = status.detail or str((last or {}).get("detail") or "the sign-in did not work")
        return {**item, "state": "failed", "detail": _short(f"no valid token: {reason}")}
    waiting = (
        "the token has ended; DebCraft signs in again at the next call"
        if status.state == "ended"
        else "not signed in yet; DebCraft signs in at the first call"
    )
    return {**item, "state": "none", "detail": waiting}


def _tunnel_items(home: Path) -> list[dict[str, Any]]:
    try:
        tunnels = load_tunnels(home)
    except ConfigError as error:
        return [{"kind": "tunnel", "name": "tunnels.yaml", "state": "failed", "detail": _short(str(error))}]
    items = []
    for spec in tunnels.values():
        item = {"kind": "tunnel", "name": spec.name, "port": spec.port}
        if port_open(spec.port):
            items.append({**item, "state": "ok", "detail": f"open on port {spec.port}"})
        elif last_problem.get(spec.name):
            items.append({**item, "state": "failed", "detail": _short(last_problem[spec.name])})
        else:
            items.append(
                {**item, "state": "none", "detail": "closed; opens when the Development DB is needed"}
            )
    return items


async def connection_items(home: Path, check: bool = False) -> list[dict[str, Any]]:
    """Every environment of app_logins.yaml and every tunnel of tunnels.yaml with its state: ok, failed or none."""
    try:
        logins = list(load_logins(home).values())
        items = [await _login_item(login, home, check) for login in logins]
    except ConfigError as error:
        items = [{"kind": "login", "name": LOGINS_FILE, "state": "failed", "detail": _short(str(error))}]
    return items + await asyncio.to_thread(_tunnel_items, home)


def add_connection_routes(app: FastAPI, manager: WebSessionManager) -> None:
    @app.get("/api/connections")
    async def connections(check: bool = False) -> dict[str, Any]:
        return {"items": await connection_items(manager.home, check)}

    @app.post("/api/connections/sign-in")
    async def sign_in(body: Named) -> dict[str, Any]:
        """The user clicked "Sign in": the stored token, a quiet sign-in, then the window, as for a call (D-603)."""
        try:
            login = load_logins(manager.home).get(body.name)
        except ConfigError as error:
            raise HTTPException(400, str(error)) from error
        if login is None:
            raise HTTPException(404, "No such environment")
        ensured = await ensure_token(login, manager.home)
        return {
            "ok": bool(ensured.token),
            "message": _short(ensured.message),
            "items": await connection_items(manager.home),
        }

    @app.post("/api/connections/copy-token")
    async def copy_token(body: Named) -> dict[str, Any]:
        """The user clicked "Copy token" (CP1, D-645): this process puts it on the clipboard. The answer never holds it."""
        try:
            login = load_logins(manager.home).get(body.name)
        except ConfigError as error:
            raise HTTPException(400, str(error)) from error
        if login is None:
            raise HTTPException(404, "No such environment")
        token = TokenStore(manager.home).get(login.token_name)
        if token is None:
            return {"ok": False, "message": "There is no valid token. Sign in first."}
        try:
            await asyncio.to_thread(copy_for_a_minute, token)
        except ClipboardError as error:
            field_log.write("token_copied", manager.home, env=login.name, ok=False, detail=str(error))
            return {"ok": False, "message": str(error)}
        field_log.write("token_copied", manager.home, env=login.name, ok=True)
        return {"ok": True, "message": "", "clears_in_s": CLEAR_AFTER_S}

    app.router.add_event_handler("shutdown", clear_now)

    @app.post("/api/connections/tunnel")
    async def tunnel(body: Named) -> dict[str, Any]:
        if body.name not in load_tunnels(manager.home):
            raise HTTPException(404, "No such tunnel")
        message = ""
        try:
            await asyncio.to_thread(ensure_tunnel, body.name, manager.home)
        except TunnelError as error:
            message = _short(str(error))
        return {"ok": not message, "message": message, "items": await connection_items(manager.home)}

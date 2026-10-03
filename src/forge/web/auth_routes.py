"""Login endpoints and the gate in front of everything else (D-184)."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel

from forge.safety.server_security import ServerSecurity
from forge.web.accounts import SESSION_COOKIE, AccountError, AccountStore

# Reachable without signing in: the page itself (so the login screen can load) and the login calls.
OPEN_PREFIXES = ("/assets", "/api/auth")
OPEN_PATHS = ("/", "/favicon.svg")


class Credentials(BaseModel):
    user: str
    password: str


def session_cookie_name(security: ServerSecurity) -> str:
    return f"{SESSION_COOKIE}_{security.port}"  # per port, like the server token cookie


def needs_login(path: str) -> bool:
    return path not in OPEN_PATHS and not path.startswith(OPEN_PREFIXES)


def add_no_login_route(app: FastAPI) -> None:
    """Without an account store (tests only) the UI is told it is already signed in."""

    @app.get("/api/auth")
    async def status() -> dict[str, Any]:
        return {"configured": True, "signed_in": True, "user": None}


def add_auth_routes(app: FastAPI, accounts: AccountStore, security: ServerSecurity) -> None:
    cookie = session_cookie_name(security)

    def set_cookie(response: Response, token: str) -> None:
        response.set_cookie(cookie, token, httponly=True, samesite="strict", path="/")

    @app.get("/api/auth")
    async def status(request: Request) -> dict[str, Any]:
        signed_in = accounts.signed_in(request.cookies.get(cookie))
        return {
            "configured": accounts.configured,
            "signed_in": signed_in,
            "user": accounts.user if signed_in else None,
        }

    @app.post("/api/auth/register")
    async def register(body: Credentials, response: Response) -> dict[str, Any]:
        try:
            token = accounts.create(body.user, body.password)
        except AccountError as error:
            raise HTTPException(400, str(error)) from error
        set_cookie(response, token)
        return {"user": accounts.user}

    @app.post("/api/auth/login")
    async def login(body: Credentials, response: Response) -> dict[str, Any]:
        try:
            token = accounts.login(body.user, body.password)
        except AccountError as error:
            raise HTTPException(401, str(error)) from error
        set_cookie(response, token)
        return {"user": accounts.user}

    @app.post("/api/auth/logout")
    async def logout(request: Request, response: Response) -> dict[str, bool]:
        accounts.logout(request.cookies.get(cookie))
        response.delete_cookie(cookie, path="/")
        return {"ok": True}

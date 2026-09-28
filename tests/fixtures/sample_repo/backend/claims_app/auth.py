"""JWT authentication for API endpoints."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

import jwt
from flask import current_app, g, request
from flask_smorest import abort


def jwt_required(view: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(view)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            abort(401, message="Missing bearer token")
        try:
            claims = jwt.decode(header[len("Bearer ") :], current_app.config["JWT_SECRET"], algorithms=["HS256"])
        except jwt.PyJWTError:
            abort(401, message="Invalid or expired token")
        g.current_user = claims.get("sub")
        return view(*args, **kwargs)

    return wrapper

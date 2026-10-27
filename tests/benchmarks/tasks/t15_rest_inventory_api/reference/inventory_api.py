"""Inventory REST API as a plain WSGI application (standard library only)."""

from __future__ import annotations

import json
import math
import re
from typing import Any, Callable
from urllib.parse import parse_qs

REASONS = {
    200: "OK",
    201: "Created",
    204: "No Content",
    400: "Bad Request",
    404: "Not Found",
    405: "Method Not Allowed",
    409: "Conflict",
    415: "Unsupported Media Type",
}
FIELDS = ("name", "quantity", "price")
ITEM_PATH = re.compile(r"^/items/([1-9][0-9]*)$")


class ApiError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        details: dict[str, str] | None = None,
        headers: list[tuple[str, str]] | None = None,
    ) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message
        self.details, self.headers = details, headers or []


def _reject_constant(name: str) -> Any:
    raise ValueError(name)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_fields(data: dict[str, Any], *, full: bool) -> dict[str, Any]:
    problems: dict[str, str] = {}
    clean: dict[str, Any] = {}
    for key in data:
        if key not in FIELDS:
            problems[key] = "unknown field"
    if "name" in data:
        name = data["name"]
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
            problems["name"] = "must be a string of 1 to 80 characters"
        else:
            clean["name"] = name.strip()
    elif full:
        problems["name"] = "required"
    if "quantity" in data:
        if not _is_int(data["quantity"]) or data["quantity"] < 0:
            problems["quantity"] = "must be an integer >= 0"
        else:
            clean["quantity"] = data["quantity"]
    elif full:
        clean["quantity"] = 0
    if "price" in data:
        if not _is_number(data["price"]) or data["price"] < 0:
            problems["price"] = "must be a number >= 0"
        else:
            clean["price"] = data["price"]
    elif full:
        problems["price"] = "required"
    if not full and not data:
        problems["body"] = "at least one field is required"
    if problems:
        raise ApiError(400, "validation_error", "invalid input", problems)
    return clean


class InventoryApi:
    def __init__(self) -> None:
        self.items: dict[int, dict[str, Any]] = {}
        self.last_id = 0

    def __call__(self, environ: dict[str, Any], start_response: Callable[..., Any]) -> list[bytes]:
        try:
            status, body, headers = self.dispatch(environ)
        except ApiError as error:
            error_body: dict[str, Any] = {"code": error.code, "message": error.message}
            if error.details:
                error_body["details"] = error.details
            status, body, headers = error.status, {"error": error_body}, error.headers
        raw = b"" if body is None else json.dumps(body).encode("utf-8")
        out = [("Content-Length", str(len(raw)))] + headers
        if body is not None:
            out.append(("Content-Type", "application/json"))
        start_response(f"{status} {REASONS[status]}", out)
        return [raw]

    def dispatch(self, environ: dict[str, Any]) -> tuple[int, Any, list[tuple[str, str]]]:
        path, method = environ.get("PATH_INFO", ""), environ.get("REQUEST_METHOD", "GET").upper()
        match = ITEM_PATH.match(path)
        if path == "/items":
            allowed = ("GET", "POST")
        elif match:
            allowed = ("DELETE", "GET", "PATCH", "PUT")
        else:
            raise ApiError(404, "not_found", "no such route")
        if method not in allowed:
            raise ApiError(
                405, "method_not_allowed", f"{method} not allowed", headers=[("Allow", ", ".join(allowed))]
            )
        if not match:
            return self.list_items(environ) if method == "GET" else self.create(environ)
        item_id = int(match.group(1))
        if item_id not in self.items:
            raise ApiError(404, "not_found", f"item {item_id} does not exist")
        if method == "GET":
            return 200, self.items[item_id], []
        if method == "DELETE":
            del self.items[item_id]
            return 204, None, []
        data = self.read_object(environ)
        clean = validate_fields(data, full=method == "PUT")
        self.check_name(clean.get("name"), item_id)
        if method == "PUT":
            self.items[item_id] = {"id": item_id, **clean}
        else:
            self.items[item_id].update(clean)
        return 200, self.items[item_id], []

    def create(self, environ: dict[str, Any]) -> tuple[int, Any, list[tuple[str, str]]]:
        clean = validate_fields(self.read_object(environ), full=True)
        self.check_name(clean["name"], None)
        self.last_id += 1
        item = {"id": self.last_id, **clean}
        self.items[self.last_id] = item
        return 201, item, [("Location", f"/items/{self.last_id}")]

    def list_items(self, environ: dict[str, Any]) -> tuple[int, Any, list[tuple[str, str]]]:
        query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
        problems: dict[str, str] = {}

        def number(name: str, default: int, low: int, high: int | None) -> int:
            raw = query.get(name, [str(default)])[-1]
            if re.fullmatch(r"[0-9]+", raw) and int(raw) >= low and (high is None or int(raw) <= high):
                return int(raw)
            problems[name] = f"must be an integer from {low}" + (f" to {high}" if high else "")
            return default

        page = number("page", 1, 1, None)
        per_page = number("per_page", 10, 1, 100)
        if problems:
            raise ApiError(400, "validation_error", "invalid query", problems)
        needle = query.get("q", [""])[-1].casefold()
        rows = [i for _, i in sorted(self.items.items()) if needle in i["name"].casefold()]
        start = (page - 1) * per_page
        body = {
            "items": rows[start : start + per_page],
            "page": page,
            "per_page": per_page,
            "total": len(rows),
            "pages": math.ceil(len(rows) / per_page),
        }
        return 200, body, []

    def check_name(self, name: str | None, own_id: int | None) -> None:
        if name is None:
            return
        for item in self.items.values():
            if item["id"] != own_id and item["name"].casefold() == name.casefold():
                raise ApiError(409, "conflict", f"name {name!r} is already used")

    def read_object(self, environ: dict[str, Any]) -> dict[str, Any]:
        media = environ.get("CONTENT_TYPE", "").split(";")[0].strip().lower()
        if media != "application/json":
            raise ApiError(415, "unsupported_media_type", "send application/json")
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            length = 0
        raw = environ["wsgi.input"].read(length) if length > 0 else b""
        try:
            data = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
        except (ValueError, UnicodeDecodeError):
            raise ApiError(400, "invalid_json", "body is not valid JSON") from None
        if not isinstance(data, dict):
            raise ApiError(400, "invalid_json", "body must be a JSON object")
        return data


def create_app() -> InventoryApi:
    return InventoryApi()

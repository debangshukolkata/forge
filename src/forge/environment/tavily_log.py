"""Failure logs for the Tavily calls on the company platform (D-548).

The platform's replies differ from Tavily's documented ones and can only be seen on the office laptop, so a failed call writes
what was sent and what came back to `<DebCraft home>/logs/tavily-<tool>-<time>.log`, and the error message names that file.
Nothing secret is written: the bearer token travels only in the Authorization header, which is not logged, the address loses
its query string, and the text passes the token scrub and the redactor before it is saved."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from forge.config import forge_home
from forge.safety.redact import default_redactor

MAX_REPLY_CHARS = 4000
MAX_OUTLINE_LINES = 40


def endpoint_of(url: str) -> str:
    """The address without its query string or fragment, which could carry a key."""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


def outline(value: Any, depth: int = 0, label: str = "reply") -> list[str]:
    """The shape of a reply: which keys sit inside which, with JSON text inside JSON opened up, so a parser fault shows at once."""
    indent = "  " * depth
    if depth > 5:
        return [f"{indent}{label}: ..."]
    if isinstance(value, str) and value.strip()[:1] in ("{", "["):
        try:
            return outline(json.loads(value), depth, f"{label} (JSON text)")
        except ValueError:
            pass
    if isinstance(value, dict):
        lines = [f"{indent}{label}: object with {', '.join(map(str, list(value)[:12])) or 'no keys'}"]
        for key, inner in list(value.items())[:12]:
            if isinstance(inner, (dict, list)) or (
                isinstance(inner, str) and inner.strip()[:1] in ("{", "[")
            ):
                lines += outline(inner, depth + 1, str(key))
        return lines
    if isinstance(value, list):
        lines = [f"{indent}{label}: list of {len(value)}"]
        if value:
            lines += outline(value[0], depth + 1, "first item")
        return lines
    shown = repr(value) if not isinstance(value, str) else f"text, {len(value)} characters"
    return [f"{indent}{label}: {shown}"]


def write_failure_log(
    kind: str,
    url: str,
    tool_id: str,
    body: dict[str, Any],
    status: int | None,
    content_type: str,
    reply_text: str | None,
    error: str,
    token: str,
) -> Path | None:
    """Writes the log and returns its path; None when it cannot be written (a log must never hide the real error)."""
    now = datetime.now()
    lines = [
        f"Tavily {kind} call failed at {now.isoformat(timespec='seconds')}",
        f"Error shown: {error}",
        "",
        f"Endpoint: {endpoint_of(url)}",
        f"Tool number: {tool_id}",
        "Request body (the bearer token is not in it: it travels in the Authorization header, which is not logged):",
        json.dumps(body, indent=2, ensure_ascii=False),
        "",
    ]
    if reply_text is None:
        lines.append("No reply: the request did not complete (network, proxy or timeout).")
    else:
        lines += [f"HTTP status: {status}", f"Content-Type: {content_type or '(none)'}", ""]
        try:
            shape = outline(json.loads(reply_text))
        except ValueError:
            shape = ["reply: not JSON"]
        lines += ["Reply structure:", *shape[:MAX_OUTLINE_LINES], ""]
        lines += [
            f"Reply text ({len(reply_text)} characters, first {min(len(reply_text), MAX_REPLY_CHARS)}):",
            reply_text[:MAX_REPLY_CHARS],
        ]
    text = "\n".join(lines) + "\n"
    if token:
        text = text.replace(token, "***")
    text = default_redactor.redact(text)
    try:
        folder = forge_home() / "logs"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"tavily-{kind}-{now:%Y%m%d-%H%M%S-%f}.log"
        path.write_text(text, encoding="utf-8")
    except OSError:
        return None
    return path

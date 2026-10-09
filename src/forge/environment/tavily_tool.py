"""Web search through the company's Tavily tool, called as an API on the agent platform (D-210).

The Tavily key itself is never used or needed here: from the laptop only the platform's `execute-tool`
endpoint is reachable, so a search is one POST to it with the tool's id and a bearer token. The three
settings come from the user's .env file (never typed into the app):

    TAVILY_TOOL_URL      the execute-tool address
    TAVILY_TOOL_ID       the tool instance id (a number)
    TAVILY_BEARER_TOKEN  the bearer token (it usually expires: a rejected call says so)

Request: {"args": {"query", "topic", "max_result", "exclude_domains", "include_domains"},
          "tool_instance_id": N}
Reply:   wrapped by the platform, sometimes as a JSON string inside JSON; unwrapped here until the search
         output ({"answer", "results": [{title, url, content}]}) is found, so a change in the wrapping does
         not break it."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

TAVILY_NAMES = ("TAVILY_TOOL_URL", "TAVILY_TOOL_ID", "TAVILY_BEARER_TOKEN")
TIMEOUT_S = 65.0  # the platform's own limit for the call is 60 s
FALLBACK_TOPIC = "News"  # known to work on the platform; tried if the configured topic is refused
MAX_UNWRAP = 6


class TavilyToolError(ValueError):
    """The call failed in a way the user can act on (the message says how)."""


class TavilyAuthError(TavilyToolError):
    """The platform refused the bearer token (usually: it expired)."""


class _Refused(TavilyToolError):
    """The platform answered, but did not accept the request (another topic may be accepted)."""


@dataclass(frozen=True)
class TavilySettings:
    url: str
    tool_id: str
    token: str

    @classmethod
    def from_secrets(cls, secrets: Any) -> TavilySettings | None:
        """None unless all three values are in the .env file."""
        if secrets is None:
            return None
        values = [secrets.get(name) for name in TAVILY_NAMES]
        if not all(values):
            return None
        url, tool_id, token = values
        return cls(url, tool_id, clean_token(token))


def clean_token(token: str) -> str:
    """The header is built as "Bearer <token>", so a pasted "Bearer eyJ..." or a quoted token is tidied up."""
    cleaned = token.strip().strip("\"'").strip()
    if cleaned.lower().startswith("bearer "):
        cleaned = cleaned[7:].strip()
    return cleaned


@dataclass
class TavilyReply:
    answer: str
    results: list[dict[str, str]]


def missing_names(secrets: Any) -> list[str]:
    return [name for name in TAVILY_NAMES if secrets is None or not secrets.get(name)]


async def search(
    settings: TavilySettings,
    query: str,
    max_results: int = 5,
    topic: str = "General",
    client_factory: Callable[[], httpx.AsyncClient] | None = None,
) -> TavilyReply:
    try:
        tool_id = int(settings.tool_id)
    except ValueError as error:
        raise TavilyToolError("TAVILY_TOOL_ID must be the tool's number, for example 2361") from error
    topics = [topic] if topic == FALLBACK_TOPIC else [topic, FALLBACK_TOPIC]
    last: TavilyToolError | None = None
    for attempt in topics:
        body = {
            "args": {
                "query": query,
                "topic": attempt,
                "max_result": str(max_results),  # as the platform's own test call sends it
                "exclude_domains": "",
                "include_domains": "",
            },
            "tool_instance_id": tool_id,
        }
        try:
            return await _post(settings, body, client_factory)
        except TavilyAuthError:
            raise  # another topic will not help
        except _Refused as refused:
            last = TavilyToolError(str(refused))
    raise last or TavilyToolError("the search failed")


async def _post(
    settings: TavilySettings,
    body: dict[str, Any],
    client_factory: Callable[[], httpx.AsyncClient] | None,
) -> TavilyReply:
    client = client_factory() if client_factory else httpx.AsyncClient(timeout=TIMEOUT_S)
    headers = {"Authorization": f"Bearer {settings.token}", "Content-Type": "application/json"}
    async with client:
        response = await client.post(settings.url, json=body, headers=headers)
    if response.status_code in (401, 403):
        raise TavilyAuthError(
            f"the platform rejected the bearer token (HTTP {response.status_code}); it has probably "
            "expired: put a fresh one in TAVILY_BEARER_TOKEN in the .env file"
        )
    if response.status_code >= 400:
        shown = _scrub(response.text, settings)[:200]
        raise _Refused(f"the platform answered HTTP {response.status_code}: {shown}")
    try:
        data = response.json()
    except ValueError as error:
        raise TavilyToolError("the platform's reply was not JSON") from error
    return parse_reply(data, settings)


def parse_reply(data: Any, settings: TavilySettings | None = None) -> TavilyReply:
    """Finds the search output inside however the platform wrapped it."""
    found = _unwrap(data, 0)
    if isinstance(found, dict) and ("answer" in found or "results" in found):
        raw = found.get("results")
        results = [
            {
                "title": str(item.get("title", "")),
                "url": str(item["url"]),
                "content": str(item.get("content") or item.get("raw_content") or ""),
            }
            for item in (raw if isinstance(raw, list) else [])
            if isinstance(item, dict) and item.get("url")
        ]
        return TavilyReply(answer=str(found.get("answer") or ""), results=results)
    message = _failure_message(data) or f"the reply had no search output (it held: {_keys(found)})"
    raise TavilyToolError(_scrub(message, settings)[:300])


def _unwrap(value: Any, depth: int) -> Any:
    if depth > MAX_UNWRAP:
        return value
    if isinstance(value, str):
        text = value.strip()
        if text[:1] in ("{", "["):
            try:
                return _unwrap(json.loads(text), depth + 1)
            except ValueError:
                return value
        return value
    if isinstance(value, dict):
        if "answer" in value or "results" in value:
            return value
        for key in ("output", "data", "response", "result"):
            if key in value:
                return _unwrap(value[key], depth + 1)
    return value


def _failure_message(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    inner: dict[str, Any] = data["data"] if isinstance(data.get("data"), dict) else {}
    if data.get("status") is False or inner.get("valid") is False:
        reason = data.get("message") or inner.get("message") or "no message"
        return f"the platform reported a failure: {reason}"
    status = inner.get("status_code")
    if isinstance(status, int) and status >= 400:
        return f"the tool answered HTTP {status}"
    if data.get("error"):
        return f"the platform reported an error: {data['error']}"
    return ""


def _keys(value: Any) -> str:
    return ", ".join(sorted(map(str, value))[:8]) if isinstance(value, dict) else type(value).__name__


def _scrub(text: str, settings: TavilySettings | None) -> str:
    return text.replace(settings.token, "***") if settings is not None else text

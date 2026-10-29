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
from typing import Any, TypeVar

import httpx

from forge.environment.tavily_log import write_failure_log

TAVILY_NAMES = ("TAVILY_TOOL_URL", "TAVILY_TOOL_ID", "TAVILY_BEARER_TOKEN")
TIMEOUT_S = 65.0  # the platform's own limit for the call is 60 s
FALLBACK_TOPIC = "News"  # known to work on the platform; tried if the configured topic is refused
MAX_UNWRAP = 6
Parsed = TypeVar("Parsed")


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


def topic_candidates(topic: str) -> list[str]:
    """The configured topic first, then the same word in the other letter case (the platform's own examples
    use "News"; Tavily's API documents "general", "news" and "finance"), then the known-good fallback."""
    wanted = topic.strip() or "General"
    options = [wanted, wanted.lower(), wanted.capitalize(), FALLBACK_TOPIC, FALLBACK_TOPIC.lower()]
    return list(dict.fromkeys(options))


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
    refusals: list[str] = []
    for attempt in topic_candidates(topic):
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
            return await _exchange(
                "search", settings, body, client_factory, lambda data: parse_reply(data, settings)
            )
        except TavilyAuthError:
            raise  # another topic will not help
        except _Refused as refused:
            refusals.append(f"topic '{attempt}': {refused}")
    raise TavilyToolError("; ".join(refusals) or "the search failed")


async def _exchange(
    kind: str,
    settings: TavilySettings,
    body: dict[str, Any],
    client_factory: Callable[[], httpx.AsyncClient] | None,
    parse: Callable[[Any], Parsed],
) -> Parsed:
    """One POST to the platform and the parse of its reply; any failure writes a log of what was sent and what came back
    and names it in the error, because the platform's replies can only be seen on the office laptop (D-548)."""
    response: httpx.Response | None = None
    try:
        client = client_factory() if client_factory else httpx.AsyncClient(timeout=TIMEOUT_S)
        headers = {"Authorization": f"Bearer {settings.token}", "Content-Type": "application/json"}
        async with client:
            response = await client.post(settings.url, json=body, headers=headers)
        return parse(_reply_data(response, settings))
    except TavilyToolError as error:
        raise _logged(error, kind, settings, body, response) from error
    except httpx.HTTPError as error:
        failure = TavilyToolError(f"the platform could not be reached: {type(error).__name__}: {error}")
        raise _logged(failure, kind, settings, body, None) from error


def _reply_data(response: httpx.Response, settings: TavilySettings) -> Any:
    if response.status_code in (401, 403):
        raise TavilyAuthError(
            f"the platform rejected the bearer token (HTTP {response.status_code}); it has probably "
            "expired: put a fresh one in TAVILY_BEARER_TOKEN in the .env file"
        )
    if response.status_code >= 400:
        shown = _scrub(response.text, settings)[:200]
        raise _Refused(f"the platform answered HTTP {response.status_code}: {shown}")
    try:
        return response.json()
    except ValueError as error:
        raise TavilyToolError("the platform's reply was not JSON") from error


def _logged(
    error: TavilyToolError,
    kind: str,
    settings: TavilySettings,
    body: dict[str, Any],
    response: httpx.Response | None,
) -> TavilyToolError:
    """The same kind of error, its message ending with where the log is."""
    path = write_failure_log(
        kind,
        settings.url,
        settings.tool_id,
        body,
        response.status_code if response is not None else None,
        response.headers.get("content-type", "") if response is not None else "",
        response.text if response is not None else None,
        str(error),
        settings.token,
    )
    where = f" Details: {path}" if path is not None else ""
    return type(error)(f"{error}.{where}")


def _body(settings: TavilySettings, args: dict[str, Any]) -> dict[str, Any]:
    try:
        tool_id = int(settings.tool_id)
    except ValueError as error:
        raise TavilyToolError("the Tavily tool number in .env must be a number, for example 2362") from error
    return {"args": args, "tool_instance_id": tool_id}


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


# --- the other Tavily tools on the same endpoint (D-504): research, extract, crawl ---
# Same URL and bearer token; each tool has its own number in .env and its own `args`. A tool is offered only when its number is set.

KINDS = ("research", "extract", "crawl")
KIND_ID_NAMES = {kind: f"TAVILY_{kind.upper()}_TOOL_ID" for kind in KINDS}
MAX_PAGES = 20
MAX_PAGE_CHARS = 4000


@dataclass
class TavilyReport:
    """What Tavily Research returns: a written report and the sources behind it."""

    report: str
    sources: list[dict[str, str]]


@dataclass
class TavilyPages:
    """What Extract and Crawl return: page texts by address, and the addresses that failed."""

    pages: list[dict[str, str]]
    failed: list[str]
    base_url: str = ""
    note: str = ""  # the platform's own words when it answers in plain text, e.g. "No crawl results found for ..." (D-553)


def kind_settings(secrets: Any, kind: str) -> TavilySettings | None:
    """The shared URL and token with this tool's own number; None unless all three are in .env."""
    if secrets is None:
        return None
    url, token, tool_id = (
        secrets.get("TAVILY_TOOL_URL"),
        secrets.get("TAVILY_BEARER_TOKEN"),
        secrets.get(KIND_ID_NAMES[kind]),
    )
    if not (url and token and tool_id):
        return None
    return TavilySettings(url, tool_id, clean_token(token))


def missing_kind_names(secrets: Any, kind: str) -> list[str]:
    wanted = ("TAVILY_TOOL_URL", KIND_ID_NAMES[kind], "TAVILY_BEARER_TOKEN")
    return [name for name in wanted if secrets is None or not secrets.get(name)]


def _find(value: Any, markers: tuple[str, ...], depth: int = 0) -> Any:
    """Unwraps the platform's wrapping (JSON inside JSON, output/data/response/result) down to the dict that holds one of the markers."""
    if depth > MAX_UNWRAP:
        return value
    if isinstance(value, str):
        text = value.strip()
        if text[:1] in ("{", "["):
            try:
                return _find(json.loads(text), markers, depth + 1)
            except ValueError:
                return value
        return value
    if isinstance(value, dict):
        if any(marker in value for marker in markers):
            return value
        for key in ("output", "data", "response", "result"):
            if key in value:
                return _find(value[key], markers, depth + 1)
    return value


def _sources(raw: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, dict) and item.get("url"):
            out.append({"title": str(item.get("title", "")), "url": str(item["url"])})
        elif isinstance(item, str) and item.startswith("http"):
            out.append({"title": "", "url": item})
    return out


def parse_report(data: Any, settings: TavilySettings | None = None) -> TavilyReport:
    found = _find(data, ("content", "report", "answer", "sources"))
    if isinstance(found, dict) and any(key in found for key in ("content", "report", "answer", "sources")):
        text = found.get("content") or found.get("report") or found.get("answer") or ""
        return TavilyReport(str(text), _sources(found.get("sources") or found.get("results")))
    if isinstance(found, str) and found.strip():  # a tool that answers with the report text itself
        return TavilyReport(found.strip(), [])
    message = _failure_message(data) or f"the reply had no research report (it held: {_keys(found)})"
    raise TavilyToolError(_scrub(message, settings)[:300])


def parse_pages(data: Any, settings: TavilySettings | None = None) -> TavilyPages:
    found = _find(data, ("results", "failed_results", "final_url", "error"))
    if isinstance(found, dict) and "final_url" in found and "results" not in found:
        return _single_page(found, settings)
    if isinstance(found, str) and found.strip() and found.strip()[:1] not in ("{", "["):
        # The platform's Crawl answers in plain text when it found nothing ("No crawl results found for '...'. Suggestions: ...",
        # office laptop 2026-10-29, D-553): an answer, not a failure, and its suggestions are worth passing on.
        return TavilyPages([], [], "", _scrub(found.strip(), settings)[:1000])
    if isinstance(found, dict) and found.get("error") and "results" not in found:
        # Show the tool's own words: the bare key name ("it held: error") hid why the crawl failed (office laptop, 2026-10-29, D-547).
        raise TavilyToolError(_scrub(f"the Tavily tool reported an error: {found['error']}", settings)[:400])
    if isinstance(found, dict) and ("results" in found or "failed_results" in found):
        raw_pages = found.get("results")
        raw_failed = found.get("failed_results")
        pages = [
            {"url": str(item["url"]), "content": str(item.get("raw_content") or item.get("content") or "")}
            for item in (raw_pages if isinstance(raw_pages, list) else [])
            if isinstance(item, dict) and item.get("url")
        ]
        failed = [
            str(item.get("url", item)) if isinstance(item, dict) else str(item)
            for item in (raw_failed if isinstance(raw_failed, list) else [])
        ]
        return TavilyPages(pages, failed, str(found.get("base_url") or ""))
    message = _failure_message(data) or f"the reply had no pages (it held: {_keys(found)})"
    raise TavilyToolError(_scrub(message, settings)[:300])


def _single_page(found: dict[str, Any], settings: TavilySettings | None) -> TavilyPages:
    """The company platform's Extract answers with one fetched page, not Tavily's `results` list:
    {"ok", "status_code", "final_url", "text", "errors", "fetch_timestamp"} (seen on the office laptop, 2026-10-29, D-547)."""
    url = str(found.get("final_url") or "")
    status = found.get("status_code")
    failed = found.get("ok") is False or (isinstance(status, int) and status >= 400)
    if failed:
        reason = found.get("errors") or (f"HTTP {status}" if status else "no reason given")
        raise TavilyToolError(_scrub(f"the page {url} could not be fetched: {reason}", settings)[:400])
    return TavilyPages([{"url": url, "content": str(found.get("text") or "")}], [], "")


async def research(
    settings: TavilySettings,
    query: str,
    topic: str = "General",
    client_factory: Callable[[], httpx.AsyncClient] | None = None,
) -> TavilyReport:
    body = _body(settings, {"query": query, "topic": topic})
    return await _exchange(
        "research", settings, body, client_factory, lambda data: parse_report(data, settings)
    )


async def extract(
    settings: TavilySettings, url: str, client_factory: Callable[[], httpx.AsyncClient] | None = None
) -> TavilyPages:
    body = _body(settings, {"url": url})
    return await _exchange(
        "extract", settings, body, client_factory, lambda data: parse_pages(data, settings)
    )


async def crawl(
    settings: TavilySettings,
    url: str,
    max_depth: int = 1,
    max_breadth: int = 20,
    instructions: str = "",
    chunks_per_source: int = 3,
    client_factory: Callable[[], httpx.AsyncClient] | None = None,
) -> TavilyPages:
    # Numbers as numbers: the platform's Crawl compares them ("'<' not supported between instances of 'str' and 'int'" on the
    # office laptop, 2026-10-29, D-551; the strings came from its sample payload). Tavily documents chunks_per_source (1 to 5)
    # only together with instructions, so the first try leaves it out without them; if the platform refuses that shape, the
    # second try sends it anyway. Each failed try writes its own log (D-548).
    base: dict[str, Any] = {
        "url": url,
        "max_depth": max_depth,
        "max_breadth": max_breadth,
        "instructions": instructions,
    }
    shapes = (
        [{**base, "chunks_per_source": chunks_per_source}]
        if instructions
        else [base, {**base, "chunks_per_source": chunks_per_source}]
    )
    failures: list[str] = []
    for args in shapes:
        try:
            return await _exchange(
                "crawl",
                settings,
                _body(settings, args),
                client_factory,
                lambda data: parse_pages(data, settings),
            )
        except TavilyAuthError:
            raise  # another shape will not help
        except TavilyToolError as error:
            failures.append(str(error))
    raise TavilyToolError(" Then: ".join(failures))

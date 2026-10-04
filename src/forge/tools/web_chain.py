"""Fetching one page through a chain of independent stages (D-209), so a failure of one never means no answer.

    cache -> direct HTTP (retries, guarded redirects) -> headless browser (only if the page came back empty or
    thin) -> Tavily extract (if a key exists) -> an archived copy (archive.org) -> the search snippet we saw

Each stage that cannot help records why and the next one runs. The result says which stage answered and what
the others did, and is 'partial' (not an error) when only a thin page or a snippet could be found."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from typing import Any, Literal
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlparse, urlunparse

import httpx

from forge.tools.web_extract import Extracted, ExtractError, extract, from_html, is_thin
from forge.tools.web_guard import WebPolicy, check_resolving
from forge.tools.web_render import RenderUnavailable, render_html

TAVILY = "https://api.tavily.com"
WAYBACK = "https://archive.org/wayback/available"
FETCH_TIMEOUT_S = 20
MAX_TRIES = 3
RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
MAX_REDIRECTS = 5
MAX_BYTES = 20 * 1024 * 1024
MIN_HOST_INTERVAL_S = 0.4  # politeness: no more than ~2 requests a second to one site
USER_AGENT = "Mozilla/5.0 (compatible; Forge/1.0; documentation reader)"
TRACKING_PARAMS = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid")

Status = Literal["ok", "partial", "failed"]
RenderFunction = Callable[[str, WebPolicy], Awaitable[tuple[str, str]]]
_last_request: dict[str, float] = {}


class BlockedUrl(Exception):
    """The address guard refused a URL (the first one, or a redirect to somewhere internal)."""


@dataclass
class PageResult:
    url: str
    final_url: str = ""
    title: str = ""
    text: str = ""
    via: str = ""  # cache | direct | browser | tavily | archive | snippet
    status: Status = "failed"
    attempts: list[str] = field(default_factory=list)  # what each stage did, for the model and the log
    note: str = ""


@dataclass
class FetchOptions:
    policy: WebPolicy = field(default_factory=WebPolicy)
    tavily_key: str | None = None
    render: bool = True
    archive: bool = True
    cache: Any = None  # WebCache: get(key) / put(key, value)
    client_factory: Callable[[], httpx.AsyncClient] = lambda: httpx.AsyncClient(timeout=FETCH_TIMEOUT_S)
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    render_function: RenderFunction = render_html


def normalise_url(url: str) -> str:
    """The same page under one name: no fragment, no tracking parameters, lower-case scheme and host."""
    parts = urlparse(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith(TRACKING_PARAMS)]
    return urlunparse(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", parts.params, urlencode(query), "")
    )


async def fetch_page(url: str, options: FetchOptions) -> PageResult:
    key = normalise_url(url)
    result = PageResult(url=url, final_url=key)
    reason = await check_resolving(key, options.policy)
    if reason is not None:
        result.attempts.append(f"not fetched: {reason}")
        return result
    cached = options.cache.get(f"page|{key}") if options.cache is not None else None
    if isinstance(cached, dict):
        return PageResult(**{**cached, "via": "cache"})

    thin: list[tuple[str, Extracted, str]] = []  # (stage, content, final url): something, but not enough

    def consider(stage: str, content: Extracted | None, final: str) -> PageResult | None:
        if content is None:
            return None
        if content.text and not is_thin(content.text):
            return _done(result, stage, content, final, "ok")
        if content.text or content.note:
            thin.append((stage, content, final))
            result.attempts.append(f"{stage}: little readable text ({len(content.text.strip())} characters)")
        else:
            result.attempts.append(f"{stage}: no text")
        return None

    async with _client(options) as client:
        content, final, error_kind = await _direct(client, key, options, result.attempts)
        direct_failed = content is None
        if (done := consider("direct", content, final or key)) is not None:
            return _store(done, options)
        is_pdf = content is not None and content.method == "pdf"
        if options.render and not is_pdf and error_kind != "blocked":
            try:
                html, rendered_url = await options.render_function(key, options.policy)
                if (done := consider("browser", from_html(html, rendered_url), rendered_url)) is not None:
                    return _store(done, options)
            except RenderUnavailable as unavailable:
                result.attempts.append(f"browser: unavailable ({unavailable})")
        if options.tavily_key and error_kind != "blocked":
            content = await _tavily(client, options.tavily_key, key, result.attempts)
            if (done := consider("tavily", content, key)) is not None:
                return _store(done, options)
        if options.archive and direct_failed and error_kind != "blocked":
            archived = await _archive(client, key, options, result.attempts)
            if (done := consider("archive", archived, key)) is not None:
                return _store(done, options)

    return _best_effort(result, thin, options, key)


def _done(result: PageResult, stage: str, content: Extracted, final: str, status: Status) -> PageResult:
    result.via, result.status, result.final_url = stage, status, final
    result.title, result.text, result.note = content.title, content.text, content.note
    result.attempts.append(f"{stage}: ok")
    return result


def _store(result: PageResult, options: FetchOptions) -> PageResult:
    if options.cache is not None:
        options.cache.put(f"page|{normalise_url(result.url)}", asdict(result))
    return result


def _best_effort(
    result: PageResult, thin: list[tuple[str, Extracted, str]], options: FetchOptions, key: str
) -> PageResult:
    """Nothing gave a full page: hand over the most we have rather than an error."""
    if thin:
        stage, content, final = max(thin, key=lambda item: len(item[1].text))
        _done(result, stage, content, final, "partial")
        result.attempts.pop()  # _done noted "ok"; this is not
        result.note = (content.note + "; " if content.note else "") + (
            "the page gave little text: it may need a login, or be mostly images or script"
        )
        return result
    snippet = options.cache.get(f"snippet|{key}") if options.cache is not None else None
    if isinstance(snippet, str) and snippet:
        result.via, result.status, result.text = "snippet", "partial", snippet
        result.note = "the page itself could not be read; this is only the search-result snippet"
    return result


def _client(options: FetchOptions) -> httpx.AsyncClient:
    return options.client_factory()


async def _pace(host: str, options: FetchOptions) -> None:
    wait = _last_request.get(host, 0.0) + MIN_HOST_INTERVAL_S - time.monotonic()
    if wait > 0:
        await options.sleep(wait)
    _last_request[host] = time.monotonic()


async def _get_guarded(client: httpx.AsyncClient, url: str, policy: WebPolicy) -> httpx.Response:
    """GET with redirects followed by hand, so every hop passes the address guard."""
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        reason = await check_resolving(current, policy)
        if reason is not None:
            raise BlockedUrl(reason)
        response = await client.get(current, headers={"User-Agent": USER_AGENT}, follow_redirects=False)
        if response.is_redirect and response.headers.get("location"):
            current = urljoin(current, response.headers["location"])
            continue
        return response
    raise httpx.TooManyRedirects(f"more than {MAX_REDIRECTS} redirects")


async def _direct(
    client: httpx.AsyncClient, url: str, options: FetchOptions, attempts: list[str]
) -> tuple[Extracted | None, str, str]:
    """(content, final URL, error kind). Temporary failures are retried with a short backoff."""
    host = urlparse(url).netloc
    last = "no answer"
    for attempt in range(1, MAX_TRIES + 1):
        await _pace(host, options)
        try:
            response = await _get_guarded(client, url, options.policy)
        except BlockedUrl as blocked:
            attempts.append(f"direct: not fetched ({blocked})")
            return None, "", "blocked"
        except (
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.RemoteProtocolError,
            httpx.TooManyRedirects,
        ) as e:
            last = type(e).__name__
            await options.sleep(0.5 * attempt)
            continue
        if response.status_code in RETRY_STATUS:
            last = f"HTTP {response.status_code}"
            await options.sleep(_retry_delay(response, attempt))
            continue
        if response.status_code >= 400:
            attempts.append(f"direct: HTTP {response.status_code}")
            return None, str(response.url), "http"
        if len(response.content) > MAX_BYTES:
            attempts.append("direct: the page is larger than 20 MB")
            return None, str(response.url), "http"
        try:
            content = extract(
                response.headers.get("content-type", ""), response.content, response.text, str(response.url)
            )
        except ExtractError as error:
            attempts.append(f"direct: {error}")
            return None, str(response.url), "type"
        return content, str(response.url), ""
    attempts.append(f"direct: {last} after {MAX_TRIES} tries")
    return None, "", "network"


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    try:
        return min(float(response.headers.get("retry-after", "")), 5.0)
    except ValueError:
        return 0.5 * attempt


async def _tavily(client: httpx.AsyncClient, key: str, url: str, attempts: list[str]) -> Extracted | None:
    try:
        response = await client.post(f"{TAVILY}/extract", json={"api_key": key, "urls": [url]})
        results = response.json().get("results") or [] if response.status_code == 200 else []
    except (httpx.HTTPError, ValueError) as error:
        attempts.append(f"tavily: {type(error).__name__}")  # never the request: it holds the key
        return None
    if results and results[0].get("raw_content"):
        return Extracted("", str(results[0]["raw_content"]), "tavily")
    attempts.append(f"tavily: no content (HTTP {response.status_code})")
    return None


async def _archive(
    client: httpx.AsyncClient, url: str, options: FetchOptions, attempts: list[str]
) -> Extracted | None:
    """The closest archive.org snapshot of a page that cannot be reached now (a dead link, a blocked site)."""
    try:
        listing = await client.get(f"{WAYBACK}?url={quote(url, safe='')}")
        closest = (listing.json().get("archived_snapshots") or {}).get("closest") or {}
        if not closest.get("available"):
            attempts.append("archive: no saved copy")
            return None
        snapshot = str(closest["url"]).replace("http://", "https://", 1)
        response = await _get_guarded(client, snapshot, options.policy)
        if response.status_code >= 400:
            attempts.append(f"archive: HTTP {response.status_code}")
            return None
        content = extract(response.headers.get("content-type", ""), response.content, response.text, snapshot)
    except (httpx.HTTPError, ValueError, ExtractError, BlockedUrl) as error:
        attempts.append(f"archive: {type(error).__name__}")
        return None
    content.note = f"an archived copy from {str(closest.get('timestamp', ''))[:8]}; it may be out of date"
    return content

"""The web fetch chain (D-209): the address guard, text extraction, and the stages that make sure a
failure of one never means no answer. Network is simulated at the HTTP transport; the browser tests use a
local server."""

from __future__ import annotations

import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import httpx
import pytest

from forge.safety.permissions import PermissionGate, PermissionRules, Rule
from forge.subagents.subagent import inherit_web_settings
from forge.toolkit.base import ToolContext
from forge.tools import web_chain, web_extract
from forge.tools.parity import BUILT_IN_TYPES
from forge.tools.web import DIG_DEEPER, WebFetch, searxng_search
from forge.tools.web_chain import FetchOptions, PageResult, fetch_page, normalise_url
from forge.tools.web_guard import WebPolicy, check_resolving, check_url
from forge.tools.web_render import RenderUnavailable, render_html
from tests.test_parity import workspace  # noqa: F401  (fixture)

LONG_TEXT = "Forge reads documentation pages and reports what they say. " * 12
GOOD_PAGE = (
    f"<html><head><title>Docs</title></head><body><main><h1>Docs</h1><p>{LONG_TEXT}</p></main></body></html>"
)


class FakeCache:
    def __init__(self) -> None:
        self.values: dict[str, Any] = {}

    def get(self, key: str) -> Any:
        return self.values.get(key)

    def put(self, key: str, value: Any) -> None:
        self.values[key] = value


def options(handler: Any, **extra: Any) -> tuple[FetchOptions, list[float]]:
    sleeps: list[float] = []

    async def no_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    async def no_browser(url: str, policy: WebPolicy) -> tuple[str, str]:
        raise RenderUnavailable("not in this test")

    base = FetchOptions(
        cache=FakeCache(),
        client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        sleep=no_sleep,
        render_function=no_browser,
    )
    for name, value in extra.items():
        setattr(base, name, value)
    return base, sleeps


def page_response(
    body: str = GOOD_PAGE, status: int = 200, content_type: str = "text/html"
) -> httpx.Response:
    return httpx.Response(status, content=body.encode(), headers={"content-type": content_type})


# --- the address guard ---


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000/x",
        "http://127.0.0.1/",
        "http://10.1.2.3/wiki",
        "http://192.168.0.5/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://100.64.0.1/",
        "http://metadata.google.internal/",
        "http://wiki.corp.local/",
        "http://user:secret@example.com/",  # check_secrets: fake
        "ftp://example.com/file",
        "file:///C:/Windows/win.ini",
    ],
)
def test_internal_and_odd_addresses_are_refused(url: str) -> None:
    assert check_url(url, WebPolicy()) is not None


def test_public_addresses_pass_and_the_user_can_allow_an_internal_host() -> None:
    assert check_url("https://docs.python.org/3/", WebPolicy()) is None
    assert check_url("http://wiki.corp.local/page", WebPolicy(allow_hosts=("wiki.corp.local",))) is None
    assert check_url("http://127.0.0.1:9/", WebPolicy(allow_hosts=("127.0.0.1",))) is None
    assert check_url("http://10.0.0.1/", WebPolicy(allow_hosts=("127.0.0.1",))) is not None


def test_domain_lists() -> None:
    deny = WebPolicy(deny_domains=("evil.example",))
    assert (
        check_url("https://sub.evil.example/x", deny) is not None
        and check_url("https://ok.example/", deny) is None
    )
    only = WebPolicy(allow_domains=("python.org",))
    assert check_url("https://docs.python.org/", only) is None
    assert check_url("https://pypi.org/", only) is not None


async def test_a_name_that_resolves_to_an_internal_address_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_getaddrinfo(self: Any, host: str, port: Any, **kwargs: Any) -> list[Any]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.9.9.9", 0))]

    monkeypatch.setattr("asyncio.base_events.BaseEventLoop.getaddrinfo", fake_getaddrinfo)
    reason = await check_resolving("https://innocent-looking.example/", WebPolicy())
    assert reason is not None and "resolves to an internal address" in reason


# --- extraction ---


def make_pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    body = b"%PDF-1.4\n"
    offsets = []
    for number, content in enumerate(objects, start=1):
        offsets.append(len(body))
        body += f"{number} 0 obj\n{content}\nendobj\n".encode()
    xref = len(body)
    body += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    body += "".join(f"{offset:010d} 00000 n \n" for offset in offsets).encode()
    body += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return body


def test_html_is_extracted_with_or_without_trafilatura(monkeypatch: pytest.MonkeyPatch) -> None:
    basic = web_extract.from_html(GOOD_PAGE, "https://x.example/")
    assert "Forge reads documentation" in basic.text
    monkeypatch.setitem(sys.modules, "trafilatura", None)  # as if the optional package were not installed
    fallback = web_extract.from_html(GOOD_PAGE, "https://x.example/")
    assert fallback.method == "basic" and "Forge reads documentation" in fallback.text


def test_pdf_text_and_a_pdf_without_text() -> None:
    result = web_extract.extract(
        "application/pdf", make_pdf("Hello from the PDF"), "", "https://x.example/a.pdf"
    )
    assert result.method == "pdf" and "Hello from the PDF" in result.text
    broken = web_extract.extract("application/pdf", b"%PDF-1.4 not really", "", "https://x.example/b.pdf")
    assert broken.text == "" and broken.note  # a reason, not an exception


def test_text_json_and_binary() -> None:
    assert web_extract.extract("application/json", b"{}", "{}", "u").text == "{}"
    with pytest.raises(web_extract.ExtractError):
        web_extract.extract("image/png", b"\x89PNG", "", "u")


def test_thin_pages_are_recognised() -> None:
    assert web_extract.is_thin("short")
    assert web_extract.is_thin("Please enable JavaScript to view this site. " * 3)
    assert not web_extract.is_thin(LONG_TEXT)


def test_urls_are_normalised() -> None:
    assert (
        normalise_url("HTTPS://Docs.Example.com/a?utm_source=x&id=2#frag")
        == "https://docs.example.com/a?id=2"
    )


# --- the chain ---


async def test_a_good_page_is_fetched_then_served_from_the_cache() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return page_response()

    opts, _ = options(handler)
    first = await fetch_page("https://docs.example/a#intro", opts)
    assert first.status == "ok" and first.via == "direct" and first.title == "Docs"
    second = await fetch_page("https://docs.example/a?utm_medium=mail", opts)
    assert second.via == "cache" and len(calls) == 1


async def test_a_temporary_error_is_retried_with_a_pause() -> None:
    tries: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        tries.append(1)
        return httpx.Response(429, headers={"retry-after": "2"}) if len(tries) == 1 else page_response()

    opts, sleeps = options(handler)
    result = await fetch_page("https://docs.example/b", opts)
    assert result.status == "ok" and len(tries) == 2 and 2.0 in sleeps


async def test_a_script_built_page_falls_back_to_the_browser() -> None:
    shell = "<html><body><div id='app'></div><script>build()</script></body></html>"

    async def browser(url: str, policy: WebPolicy) -> tuple[str, str]:
        return GOOD_PAGE, url

    opts, _ = options(lambda request: page_response(shell), render_function=browser)
    result = await fetch_page("https://app.example/", opts)
    assert result.status == "ok" and result.via == "browser"
    assert any(line.startswith("direct:") for line in result.attempts)  # the plain fetch is on record


async def test_a_page_that_stays_thin_is_partial_not_an_error() -> None:
    thin = "<html><body><p>Sign in to continue.</p></body></html>"
    opts, _ = options(lambda request: page_response(thin))
    result = await fetch_page("https://private.example/", opts)
    assert (
        result.status == "partial"
        and "Sign in" in result.text
        and "browser: unavailable" in " ".join(result.attempts)
    )


async def test_a_dead_page_comes_from_the_archive() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "archive.org":
            return httpx.Response(
                200,
                json={
                    "archived_snapshots": {
                        "closest": {
                            "available": True,
                            "timestamp": "20240101000000",
                            "url": "http://web.archive.org/web/2024/https://gone.example/",
                        }
                    }
                },
            )
        if request.url.host == "web.archive.org":
            return page_response()
        return httpx.Response(503)

    opts, _ = options(handler)
    result = await fetch_page("https://gone.example/", opts)
    assert result.status == "ok" and result.via == "archive" and "archived copy from 20240101" in result.note


async def test_when_nothing_else_works_the_search_snippet_is_returned() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={}) if request.url.host == "archive.org" else httpx.Response(503)

    opts, _ = options(handler)
    opts.cache.put("snippet|https://down.example/", "The snippet the search showed.")
    result = await fetch_page("https://down.example/", opts)
    assert result.status == "partial" and result.via == "snippet" and "snippet" in result.text


async def test_total_failure_still_says_what_was_tried() -> None:
    opts, _ = options(lambda request: httpx.Response(503))
    result = await fetch_page("https://down.example/", opts)
    assert result.status == "failed" and result.text == ""
    assert any("503" in line for line in result.attempts) and any(
        "archive" in line for line in result.attempts
    )


async def test_a_missing_page_is_reported_as_missing_and_no_browser_is_tried() -> None:
    rendered: list[str] = []

    async def browser(url: str, policy: WebPolicy) -> tuple[str, str]:
        rendered.append(url)
        return GOOD_PAGE, url

    def handler(request: httpx.Request) -> httpx.Response:
        return (
            httpx.Response(404, json={})
            if request.url.host == "archive.org"
            else httpx.Response(404, text="gone")
        )

    opts, _ = options(handler, render_function=browser)
    result = await fetch_page("https://example.invalid/this-page-does-not-exist", opts)
    assert result.status == "failed" and rendered == []  # an error page is not the page
    assert any("HTTP 404" in line for line in result.attempts)
    assert any("archive" in line for line in result.attempts)  # an archived copy may still exist


async def test_a_redirect_into_the_intranet_is_not_followed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://10.0.0.7/admin"})

    opts, _ = options(handler)
    result = await fetch_page("https://innocent.example/", opts)
    assert result.status == "failed" and any("not fetched" in line for line in result.attempts)


async def test_a_pdf_is_read() -> None:
    pdf = make_pdf("PDF body. " * 60)
    opts, _ = options(
        lambda request: httpx.Response(200, content=pdf, headers={"content-type": "application/pdf"})
    )
    result = await fetch_page("https://docs.example/spec.pdf", opts)
    assert result.status == "ok" and "PDF body." in result.text


async def test_the_tool_reports_partial_and_failed_results_helpfully(
    monkeypatch: pytest.MonkeyPatch,
    workspace: Any,  # noqa: F811
) -> None:
    results = iter(
        [
            PageResult(
                url="u",
                final_url="u",
                text="a snippet",
                via="snippet",
                status="partial",
                attempts=["direct: HTTP 503"],
                note="only a snippet",
            ),
            PageResult(url="u", attempts=["direct: HTTP 503", "archive: no saved copy"]),
        ]
    )

    async def fake_fetch(url: str, opts: FetchOptions) -> PageResult:
        return next(results)

    monkeypatch.setattr("forge.tools.web.fetch_page", fake_fetch)
    context = ToolContext(workspace=workspace)
    partial = await WebFetch().run(WebFetch.Args(url="https://x.example/"), context)
    assert (
        partial.ok
        and "PARTIAL" in partial.content
        and DIG_DEEPER in partial.content
        and "a snippet" in partial.content
    )
    failed = await WebFetch().run(WebFetch.Args(url="https://x.example/"), context)
    assert not failed.ok and "What was tried" in failed.content and "researcher" in failed.content


# --- permission rules, subagents, search ---


def test_ask_before_the_first_fetch_from_a_site(tmp_path: Path) -> None:
    gate = PermissionGate("default", tmp_path / "permissions.json")
    url = "https://docs.example/a"
    assert gate.decide("web_fetch", True, url, None).verdict == "allow"  # off by default
    gate.ask_new_domains = True
    asked = gate.decide("web_fetch", True, url, None)
    assert asked.verdict == "ask" and asked.command_prefix == "docs.example"
    gate.allow_prefix("docs.example")
    assert gate.decide("web_fetch", True, url, None).verdict == "allow"  # remembered for that host
    assert gate.decide("web_fetch", True, "https://other.example/", None).verdict == "ask"
    gate.mode = "auto"
    assert gate.decide("web_fetch", True, "https://other.example/", None).verdict == "allow"


def test_a_deny_rule_can_name_a_site(tmp_path: Path) -> None:
    rules = PermissionRules(deny=(Rule.parse("web_fetch(*evil.example*)"),))
    gate = PermissionGate("default", tmp_path / "permissions.json", rules)
    assert gate.decide("web_fetch", True, "https://evil.example/x", None).verdict == "deny"
    assert gate.decide("web_fetch", True, "https://good.example/x", None).verdict == "allow"


def test_subagents_search_under_the_same_rules(workspace: Any) -> None:  # noqa: F811
    parent = ToolContext(
        workspace=workspace,
        sensitive_terms=("acme_billing",),
        web_search_order=("duckduckgo",),
        web_policy=WebPolicy(deny_domains=("x.example",)),
        web_render=False,
    )
    child = ToolContext(workspace=workspace)
    inherit_web_settings(parent, child)
    assert child.sensitive_terms == ("acme_billing",) and child.web_policy == parent.web_policy
    assert child.web_search_order == ("duckduckgo",) and child.web_render is False
    assert "researcher" in BUILT_IN_TYPES


async def test_searxng_results_are_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/search" and request.url.params["format"] == "json"
        return httpx.Response(
            200, json={"results": [{"title": "T", "url": "https://a.example/", "content": "C"}, {"x": 1}]}
        )

    real = httpx.AsyncClient
    monkeypatch.setattr(
        "forge.tools.web.httpx.AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler))
    )
    assert await searxng_search("https://search.example/", "q", 5) == [
        {"title": "T", "url": "https://a.example/", "content": "C"}
    ]


# --- the headless browser (a real one, against a local server) ---


class _Pages(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = {
            "/js": "<html><body><div id=a></div><script>document.getElementById('a').textContent = "
            + repr(LONG_TEXT)
            + ";</script></body></html>",
            "/probe": "<html><body><p id=r>waiting</p><script>fetch('http://localhost:"
            + str(self.server.other_port)  # type: ignore[attr-defined]
            + "/secret')"
            ".then(()=>document.getElementById('r').textContent='REACHED')"
            ".catch(()=>document.getElementById('r').textContent='BLOCKED')</script></body></html>",
        }.get(self.path, "<html><body>other</body></html>")
        self.send_response(404 if self.path == "/missing" else 200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *args: Any) -> None:
        pass


@pytest.fixture
def local_server() -> Any:
    servers = [HTTPServer(("127.0.0.1", 0), _Pages) for _ in range(2)]
    for server in servers:
        server.other_port = servers[1].server_port  # type: ignore[attr-defined]
        threading.Thread(target=server.serve_forever, daemon=True).start()
    yield servers[0].server_port, servers[1].server_port
    for server in servers:
        server.shutdown()


async def test_the_browser_renders_script_built_pages_and_blocks_internal_sub_requests(
    local_server: Any,
) -> None:
    port, _ = local_server
    policy = WebPolicy(allow_hosts=("127.0.0.1",))  # the page's own host is allowed; localhost is not
    try:
        html, _ = await render_html(f"http://127.0.0.1:{port}/js", policy)
        probe, _ = await render_html(f"http://127.0.0.1:{port}/probe", policy)
    except RenderUnavailable as unavailable:
        pytest.skip(f"headless browser not available: {unavailable}")
    assert "Forge reads documentation" in html
    with pytest.raises(
        RenderUnavailable, match="HTTP 404"
    ):  # an error page is not rendered as if it were the page
        await render_html(f"http://127.0.0.1:{port}/missing", policy)
    assert '<p id="r">BLOCKED</p>' in probe  # the page's own request to localhost was refused

    # And through the chain: with the default policy nothing local is fetched at all.
    refused = await fetch_page(f"http://127.0.0.1:{port}/js", FetchOptions(cache=FakeCache()))
    assert refused.status == "failed" and "not fetched" in refused.attempts[0]
    allowed = await fetch_page(
        f"http://127.0.0.1:{port}/js", FetchOptions(policy=policy, cache=FakeCache(), archive=False)
    )
    assert allowed.status == "ok" and allowed.via == "browser"


def test_module_state_is_reset_between_tests() -> None:
    web_chain._last_request.clear()  # per-host pacing is process-wide; nothing here depends on it

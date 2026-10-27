"""D-504: Tavily Research, Extract and Crawl on the same platform endpoint: requests, the platform's wrapping of replies, offering a tool only when
its number is set, the guards, and the environment checks. No network: the transport is simulated."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from forge.config import Secrets
from forge.environment import checks
from forge.environment.tavily_tool import (
    KIND_ID_NAMES,
    TavilyAuthError,
    TavilySettings,
    TavilyToolError,
    crawl,
    extract,
    kind_settings,
    parse_pages,
    parse_report,
    research,
)
from forge.toolkit.base import ToolContext
from forge.tools.tavily_tools import TavilyCrawl, TavilyExtract, TavilyResearch, tavily_tools
from tests.test_parity import workspace  # noqa: F401  (fixture)

URL = "https://platform.example/execute-tool"
SETTINGS = TavilySettings(url=URL, tool_id="2362", token="tok-123")  # check_secrets: fake
ALL = {
    "TAVILY_TOOL_URL": URL,
    "TAVILY_BEARER_TOKEN": "tok-123",  # check_secrets: fake
    "TAVILY_RESEARCH_TOOL_ID": "2362",
    "TAVILY_EXTRACT_TOOL_ID": "2408",
    "TAVILY_CRAWL_TOOL_ID": "2411",
}
REPORT = {
    "content": "Python is a language.",
    "sources": [{"title": "Docs", "url": "https://python.org"}, {"nourl": 1}],
}
PAGES = {
    "base_url": "https://docs.example",
    "results": [{"url": "https://docs.example/a", "raw_content": "Page A text"}, {"nourl": True}],
    "failed_results": [{"url": "https://docs.example/b", "error": "timeout"}],
}


def client_for(handler: Any) -> Any:
    return lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))


def reply(payload: Any) -> Any:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append({"body": json.loads(request.content), "auth": request.headers["authorization"]})
        return httpx.Response(200, json=payload)

    handler.seen = seen  # type: ignore[attr-defined]
    return handler


# --- requests ---


async def test_research_sends_its_own_number_and_args() -> None:
    handler = reply({"output": REPORT})
    result = await research(SETTINGS, "what is python", "News", client_for(handler))
    assert handler.seen[0]["body"] == {
        "args": {"query": "what is python", "topic": "News"},
        "tool_instance_id": 2362,
    }
    assert handler.seen[0]["auth"] == "Bearer tok-123"
    assert result.report == "Python is a language."
    assert result.sources == [{"title": "Docs", "url": "https://python.org"}]


async def test_extract_and_crawl_payloads() -> None:
    handler = reply(PAGES)
    pages = await extract(SETTINGS, "https://docs.example/a", client_for(handler))
    assert handler.seen[0]["body"]["args"] == {"url": "https://docs.example/a"}
    assert pages.pages == [{"url": "https://docs.example/a", "content": "Page A text"}]
    assert pages.failed == ["https://docs.example/b"]
    await crawl(SETTINGS, "https://docs.example", 2, 5, "find the auth guide", 3, client_for(handler))
    assert handler.seen[1]["body"]["args"] == {
        "url": "https://docs.example",
        "max_depth": "2",
        "max_breadth": "5",
        "instructions": "find the auth guide",
        "chunks_per_source": "3",
    }
    await crawl(SETTINGS, "https://docs.example", client_factory=client_for(handler))
    assert handler.seen[2]["body"]["args"]["chunks_per_source"] == "0"  # chunks only apply with instructions


# --- the platform's wrapping ---


@pytest.mark.parametrize(
    "wrapped",
    [
        REPORT,
        {"output": REPORT},
        {"data": {"response": json.dumps({"output": REPORT})}, "status": True},
        json.dumps({"result": REPORT}),
    ],
)
def test_the_report_is_found_however_it_is_wrapped(wrapped: Any) -> None:
    assert parse_report(wrapped).report == "Python is a language."


def test_a_plain_text_reply_is_the_report() -> None:
    assert parse_report({"output": "Just text."}).report == "Just text."


def test_pages_are_found_inside_the_wrapping() -> None:
    wrapped = {"data": {"response": json.dumps({"output": PAGES})}, "status": True}
    assert parse_pages(wrapped).base_url == "https://docs.example"


def test_a_failure_message_is_reported_without_the_token() -> None:
    with pytest.raises(TavilyToolError, match="reported a failure") as caught:
        parse_pages({"status": False, "message": "bad tok-123 url"}, SETTINGS)
    assert "tok-123" not in str(caught.value)


async def test_an_expired_token_is_named() -> None:
    unauthorised = client_for(lambda r: httpx.Response(401, text="no"))
    with pytest.raises(TavilyAuthError, match="TAVILY_BEARER_TOKEN"):
        await extract(SETTINGS, "https://x.example", unauthorised)
    broken = client_for(lambda r: httpx.Response(500, text="boom"))
    with pytest.raises(TavilyToolError, match="HTTP 500"):
        await research(SETTINGS, "q", client_factory=broken)


# --- offering the tools ---


def test_a_tool_is_offered_only_when_its_number_is_set() -> None:
    names = [t.name for t in tavily_tools(Secrets(dict(ALL), None))]
    assert names == ["tavily_research", "tavily_extract", "tavily_crawl"]
    partial = {k: v for k, v in ALL.items() if k != KIND_ID_NAMES["extract"]}
    assert [t.name for t in tavily_tools(Secrets(partial, None))] == ["tavily_research", "tavily_crawl"]
    assert tavily_tools(Secrets({}, None)) == []
    no_token = Secrets({k: v for k, v in ALL.items() if k != "TAVILY_BEARER_TOKEN"}, None)
    assert kind_settings(no_token, "crawl") is None


def test_the_networked_tools_are_checked_for_leaks() -> None:
    assert TavilyResearch.sends_outside and TavilyExtract.sends_outside and TavilyCrawl.sends_outside


# --- the tools ---


def patched(monkeypatch: pytest.MonkeyPatch, payload: Any) -> None:
    real = httpx.AsyncClient
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=payload))
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: real(transport=transport))


async def test_extract_tool_returns_untrusted_page_text(
    workspace: Any,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patched(monkeypatch, PAGES)
    context = ToolContext(workspace=workspace, secrets=Secrets(dict(ALL), None))
    result = await TavilyExtract().run(TavilyExtract.Args(url="https://docs.example/a"), context)
    assert result.ok and "untrusted" in result.content and "Page A text" in result.content
    assert "Could not be read: https://docs.example/b" in result.content


async def test_crawl_refuses_internal_addresses_and_an_unset_tool_says_what_is_missing(
    workspace: Any,  # noqa: F811
) -> None:
    context = ToolContext(workspace=workspace, secrets=Secrets(dict(ALL), None))
    refused = await TavilyCrawl().run(TavilyCrawl.Args(url="http://localhost:8000/admin"), context)
    assert not refused.ok and "Not sent" in refused.content
    bare = ToolContext(workspace=workspace, secrets=Secrets({}, None))
    unset = await TavilyResearch().run(TavilyResearch.Args(query="q"), bare)
    assert not unset.ok and "TAVILY_RESEARCH_TOOL_ID" in unset.content


async def test_research_tool_lists_sources_and_masks_host_terms(
    workspace: Any,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patched(monkeypatch, {"output": REPORT})
    context = ToolContext(workspace=workspace, secrets=Secrets(dict(ALL), None))
    result = await TavilyResearch().run(TavilyResearch.Args(query="python"), context)
    assert result.ok and "Python is a language." in result.content and "https://python.org" in result.content
    context.sensitive_terms = ("AcmeCorp",)
    blocked = await TavilyResearch().run(TavilyResearch.Args(query="why does AcmeCorp billing fail"), context)
    assert not blocked.ok and "host-identifying" in blocked.content


# --- the environment checks ---


@pytest.mark.parametrize("kind", ["research", "extract", "crawl"])
def test_the_environment_check_reports_missing_values_and_success(
    kind: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FORGE_HOME", str(tmp_path))
    monkeypatch.setenv("FORGE_ENV_FILE", str(tmp_path / "none.env"))
    for name in ALL:
        monkeypatch.delenv(name, raising=False)
    missing = checks.check_tavily_kind(kind)
    assert missing.status == "fail" and KIND_ID_NAMES[kind] in missing.detail
    for name, value in ALL.items():
        monkeypatch.setenv(name, value)
    patched(monkeypatch, {"output": REPORT} if kind == "research" else PAGES)
    ok = checks.check_tavily_kind(kind)
    assert ok.status == "ok", ok.detail


def test_the_new_checks_are_known_and_asked() -> None:
    wanted = {"tavily_research", "tavily_extract", "tavily_crawl"}
    assert wanted <= set(checks.KNOWN_IDS) and wanted <= set(checks.ASKED_IDS)

"""The company's Tavily tool, called through the agent platform's execute-tool API (D-210): the
request, the platform's wrapping of the reply, expired tokens and the fallbacks. No network: the transport
is simulated."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from forge.config import Secrets
from forge.environment import checks, store
from forge.environment.tavily_tool import (
    TavilyAuthError,
    TavilyReply,
    TavilySettings,
    TavilyToolError,
    parse_reply,
    search,
)
from forge.safety.redact import default_redactor
from forge.toolkit.base import ToolContext
from forge.tools.web import WebSearch
from tests.test_parity import workspace  # noqa: F401  (fixture)

SETTINGS = TavilySettings(
    url="https://platform.example/wnxt/api/agent/tool-operation/execute-tool",
    tool_id="2361",
    token="bearer-abc-123",  # check_secrets: fake
)
OUTPUT = {
    "query": "flydubai",
    "follow_up_questions": None,
    "answer": "An incident occurred on a Flydubai flight.",
    "results": [
        {"title": "News A", "url": "https://news.example/a", "content": "First report.", "score": 0.9},
        {"title": "No link", "content": "dropped"},
    ],
}
# What the platform's own test call returns: the search output is a JSON string inside JSON.
VALIDATE_ENVELOPE = {
    "message": "API Validated successfully",
    "data": {"valid": True, "status_code": 200, "response": json.dumps({"output": OUTPUT})},
    "status": True,
    "checks": [["URL check", True], ["Auth Token check", True]],
}


def client_for(handler: Any) -> Any:
    return lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))


# --- reading the reply ---


@pytest.mark.parametrize(
    "wrapped",
    [
        VALIDATE_ENVELOPE,
        {"output": OUTPUT},
        {"response": json.dumps({"output": OUTPUT})},
        OUTPUT,
        json.dumps(VALIDATE_ENVELOPE),
    ],
)
def test_the_reply_is_found_however_the_platform_wraps_it(wrapped: Any) -> None:
    reply = parse_reply(wrapped)
    assert reply.answer.startswith("An incident")
    assert reply.results == [{"title": "News A", "url": "https://news.example/a", "content": "First report."}]


def test_an_answer_without_results_still_counts() -> None:
    reply = parse_reply({"output": {"answer": "Just this."}})
    assert reply.answer == "Just this." and reply.results == []


def test_a_failed_or_unrecognised_reply_says_why() -> None:
    with pytest.raises(TavilyToolError, match="reported a failure: bad tool"):
        parse_reply({"status": False, "message": "bad tool", "data": {}}, SETTINGS)
    with pytest.raises(TavilyToolError, match="tool answered HTTP 500"):
        parse_reply({"status": True, "data": {"status_code": 500, "response": "x"}}, SETTINGS)
    with pytest.raises(TavilyToolError, match="held: status, weird"):
        parse_reply({"status": True, "weird": 1}, SETTINGS)


# --- the call ---


async def test_the_request_matches_the_platforms_own_call() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=VALIDATE_ENVELOPE)

    reply = await search(SETTINGS, "flydubai", 5, client_factory=client_for(handler))
    request = seen[0]
    assert str(request.url) == SETTINGS.url and request.headers["authorization"] == "Bearer bearer-abc-123"
    body = json.loads(request.content)
    assert body == {
        "args": {
            "query": "flydubai",
            "topic": "General",
            "max_result": "5",
            "exclude_domains": "",
            "include_domains": "",
        },
        "tool_instance_id": 2361,
    }
    assert isinstance(reply, TavilyReply) and len(reply.results) == 1


async def test_an_expired_token_says_so_and_never_shows_the_token() -> None:
    handler = lambda request: httpx.Response(401, text="Unauthorized bearer-abc-123")  # noqa: E731
    with pytest.raises(TavilyAuthError) as raised:
        await search(SETTINGS, "q", client_factory=client_for(handler))
    assert "TAVILY_BEARER_TOKEN" in str(raised.value) and "bearer-abc-123" not in str(raised.value)


async def test_a_refused_topic_is_retried_with_the_known_good_one() -> None:
    topics: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        topic = json.loads(request.content)["args"]["topic"]
        topics.append(topic)
        return (
            httpx.Response(422, text="bad topic") if topic == "General" else httpx.Response(200, json=OUTPUT)
        )

    reply = await search(SETTINGS, "q", topic="General", client_factory=client_for(handler))
    assert topics == ["General", "News"] and reply.results


async def test_errors_never_carry_the_token() -> None:
    handler = lambda request: httpx.Response(500, text="boom bearer-abc-123 boom")  # noqa: E731
    with pytest.raises(TavilyToolError) as raised:
        await search(SETTINGS, "q", topic="News", client_factory=client_for(handler))
    assert "bearer-abc-123" not in str(raised.value) and "***" in str(raised.value)


async def test_a_tool_id_that_is_not_a_number_is_explained() -> None:
    bad = TavilySettings(SETTINGS.url, "not-a-number", SETTINGS.token)
    with pytest.raises(TavilyToolError, match="must be the tool's number"):
        await search(bad, "q")


def test_settings_need_all_three_values() -> None:
    names = {
        "TAVILY_TOOL_URL": SETTINGS.url,
        "TAVILY_TOOL_ID": "2361",
        "TAVILY_BEARER_TOKEN": "t",  # check_secrets: fake
    }
    assert TavilySettings.from_secrets(Secrets(names, None)) == TavilySettings(SETTINGS.url, "2361", "t")
    assert TavilySettings.from_secrets(Secrets({**names, "TAVILY_TOOL_ID": ""}, None)) is None
    assert TavilySettings.from_secrets(None) is None


def test_the_token_is_registered_for_redaction(isolated_forge_home: Path) -> None:
    from forge.config import load_secrets

    (isolated_forge_home / ".env").write_text(
        "TAVILY_BEARER_TOKEN=zz-secret-token-9876\n",
        encoding="utf-8",  # check_secrets: fake
    )
    load_secrets(isolated_forge_home)
    assert "zz-secret-token-9876" not in default_redactor.redact("calling with zz-secret-token-9876 now")


# --- as a search provider ---


def secrets_with_tavily() -> Secrets:
    return Secrets(
        {
            "TAVILY_TOOL_URL": SETTINGS.url,
            "TAVILY_TOOL_ID": "2361",
            "TAVILY_BEARER_TOKEN": "bearer-abc-123",  # check_secrets: fake
        },
        None,
    )


async def test_the_search_tool_uses_the_platform_and_shows_the_answer(
    monkeypatch: pytest.MonkeyPatch,
    workspace: Any,  # noqa: F811
    isolated_forge_home: Path,
) -> None:
    calls: list[str] = []

    async def fake_search(settings: TavilySettings, query: str, max_results: int, topic: str) -> TavilyReply:
        calls.append(f"{query}|{max_results}|{topic}")
        return parse_reply(VALIDATE_ENVELOPE)

    monkeypatch.setattr("forge.tools.web.tavily_tool_search", fake_search)
    context = ToolContext(workspace=workspace, secrets=secrets_with_tavily(), web_search_provider="tavily")
    result = await WebSearch().run(WebSearch.Args(query="flydubai", max_results=3), context)
    assert result.ok and "(search: tavily)" in result.content
    assert "Answer: An incident occurred" in result.content and "https://news.example/a" in result.content
    assert calls == ["flydubai|3|General"]
    again = await WebSearch().run(WebSearch.Args(query="flydubai", max_results=3), context)
    assert again.ok and calls == ["flydubai|3|General"]  # the second one came from the cache


async def test_when_the_platform_fails_search_moves_on_to_the_next_provider(
    monkeypatch: pytest.MonkeyPatch,
    workspace: Any,  # noqa: F811
    isolated_forge_home: Path,
) -> None:
    async def expired(*args: Any) -> TavilyReply:
        raise TavilyAuthError("the platform rejected the bearer token (HTTP 401)")

    async def duck(query: str, max_results: int) -> list[dict[str, str]]:
        return [{"title": "Docs", "url": "https://docs.example/", "content": "Found elsewhere."}]

    monkeypatch.setattr("forge.tools.web.tavily_tool_search", expired)
    monkeypatch.setattr("forge.tools.web.duckduckgo_search", duck)
    context = ToolContext(
        workspace=workspace,
        secrets=secrets_with_tavily(),
        web_search_order=("tavily", "duckduckgo"),
    )
    result = await WebSearch().run(WebSearch.Args(query="docs"), context)
    assert result.ok and "(search: duckduckgo)" in result.content
    assert "earlier providers failed" in result.content and "bearer token" in result.content


# --- the drawer ---


def test_the_drawer_check_reports_missing_values_expired_tokens_and_success(
    monkeypatch: pytest.MonkeyPatch, isolated_forge_home: Path
) -> None:
    from forge.config import load_config

    env = isolated_forge_home / ".env"
    monkeypatch.setenv("FORGE_ENV_FILE", str(env))
    for name in ("TAVILY_TOOL_URL", "TAVILY_TOOL_ID", "TAVILY_BEARER_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    config = load_config(isolated_forge_home)

    missing = checks.check_tavily(config)
    assert (
        missing.status == "fail"
        and "TAVILY_TOOL_URL" in missing.detail
        and missing.steps == checks.TAVILY_STEPS
    )

    env.write_text(
        f"TAVILY_TOOL_URL={SETTINGS.url}\nTAVILY_TOOL_ID=2361\n"
        "TAVILY_BEARER_TOKEN=zz-token-1\n",  # check_secrets: fake
        encoding="utf-8",
    )

    async def expired(*args: Any) -> TavilyReply:
        raise TavilyAuthError("the platform rejected the bearer token (HTTP 401); it has probably expired")

    monkeypatch.setattr(checks, "tavily_search", expired)
    rejected = checks.check_tavily(config)
    assert (
        rejected.status == "fail"
        and "fresh bearer token" in rejected.hint
        and "zz-token-1" not in str(rejected)
    )

    async def works(*args: Any) -> TavilyReply:
        return parse_reply(VALIDATE_ENVELOPE)

    monkeypatch.setattr(checks, "tavily_search", works)
    ok = checks.check_tavily(config)
    assert ok.status == "ok" and "1 result" in ok.detail


def test_answering_no_keeps_tavily_out_of_the_search_order(isolated_forge_home: Path) -> None:
    assert store.tavily_declined(isolated_forge_home) is False  # no answer yet: tried if it is set up
    store.save_answer(isolated_forge_home, "tavily", False)
    assert store.tavily_declined(isolated_forge_home) is True
    store.save_answer(isolated_forge_home, "tavily", True)
    assert store.tavily_declined(isolated_forge_home) is False

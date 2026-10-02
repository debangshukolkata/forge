"""Failure handling, with failures injected at the HTTP transport layer (DECISIONS D-008)."""

from __future__ import annotations

import json

import httpx2
import pytest

from forge.errors import LLMAuthError, LLMContextLengthError
from forge.llm.azure_openai import AzureOpenAIProvider
from forge.llm.base import ChatRequest, Message
from forge.llm.tool_args import parse_error_result
from tests.helpers import (
    chat_body,
    error_body,
    function_call_output,
    json_response,
    mocked_router,
    responses_body,
    text_output,
)

HELLO = ChatRequest(messages=[Message.user("hello")])


def is_responses(request: httpx2.Request) -> bool:
    return request.url.path.endswith("/responses")


async def test_429_is_retried_honouring_retry_after() -> None:
    calls: list[int] = []
    sleeps: list[float] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        if len(calls) == 1:
            return json_response(429, error_body("429", "Rate limit"), headers={"retry-after": "7"})
        return json_response(200, responses_body([text_output("ok")]))

    response = await mocked_router(handler, sleeps).chat("coder", HELLO)

    assert response.text == "ok"
    assert len(calls) == 2
    assert sleeps == [7.0]


async def test_retry_after_ms_takes_precedence() -> None:
    sleeps: list[float] = []
    calls: list[int] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        if len(calls) == 1:
            return json_response(429, error_body("429", "slow down"), headers={"retry-after-ms": "1500"})
        return json_response(200, responses_body([text_output("ok")]))

    await mocked_router(handler, sleeps).chat("coder", HELLO)

    assert sleeps == [1.5]


async def test_server_errors_back_off_then_fall_back_to_the_fallback_model() -> None:
    notices: list[tuple[str, dict[str, object]]] = []
    deployments: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        deployments.append(body["model"])
        if body["model"] == "primary-deployment":
            return json_response(503, error_body("503", "Service unavailable"))
        return json_response(200, responses_body([text_output("from fallback")], model="gpt-4.1"))

    async def on_notice(kind: str, data: dict[str, object]) -> None:
        notices.append((kind, data))

    sleeps: list[float] = []
    response = await mocked_router(handler, sleeps, on_notice=on_notice).chat("coder", HELLO)

    assert response.text == "from fallback"
    assert deployments.count("primary-deployment") == 6  # max_attempts
    assert len(sleeps) == 5 and sleeps == sorted(sleeps)  # exponential backoff
    assert [kind for kind, _ in notices].count("fallback") == 1


async def test_context_length_error_is_not_retried() -> None:
    calls: list[int] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        return json_response(400, error_body("context_length_exceeded", "maximum context length is 272000"))

    with pytest.raises(LLMContextLengthError):
        await mocked_router(handler).chat("coder", HELLO)
    assert len(calls) == 1


async def test_auth_error_is_not_retried_and_hides_the_key() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return json_response(401, error_body("401", "Access denied, key unit-test-key-0123456789 invalid"))

    with pytest.raises(LLMAuthError) as raised:
        await mocked_router(handler).chat("coder", HELLO)
    assert "check the key" in str(raised.value)


async def test_missing_responses_api_falls_back_to_chat_completions() -> None:
    paths: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        paths.append(request.url.path)
        if is_responses(request):
            return json_response(404, error_body("404", "Resource not found"))
        return json_response(200, chat_body("via chat"))

    router = mocked_router(handler)
    response = await router.chat("coder", HELLO)

    assert response.text == "via chat"
    provider = router.provider("gpt51")
    assert isinstance(provider, AzureOpenAIProvider) and provider.fell_back_to_chat
    await router.chat("coder", HELLO)
    assert sum(is_responses_path(p) for p in paths) == 1  # remembered; not retried every call


def is_responses_path(path: str) -> bool:
    return path.endswith("/responses")


async def test_malformed_tool_json_is_bounced_back_to_the_model() -> None:
    bodies: list[dict[str, object]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        if len(bodies) == 1:
            return json_response(
                200, responses_body([function_call_output("write_file", '{"path": "a.py",')])
            )
        return json_response(200, responses_body([text_output("fixed")]))

    router = mocked_router(handler)
    first = await router.chat("coder", HELLO)
    call = first.tool_calls[0]
    assert call.parse_error is not None

    history = [*HELLO.messages, first.to_message("gpt51"), parse_error_result(call)]
    await router.chat("coder", ChatRequest(messages=history))

    sent_back = [item for item in bodies[1]["input"] if item.get("type") == "function_call_output"]  # type: ignore[union-attr]
    assert "not valid JSON" in sent_back[0]["output"]


async def test_outbound_requests_are_redacted() -> None:
    bodies: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(request.content.decode())
        return json_response(200, responses_body([text_output("ok")]))

    from forge.safety.redact import Redactor

    redactor = Redactor()
    redactor.register("canary-secret-9876543210", "CANARY")
    router = mocked_router(handler, redactor=redactor)

    await router.chat("coder", ChatRequest(messages=[Message.user("my key is canary-secret-9876543210")]))

    assert "canary-secret-9876543210" not in bodies[0]
    assert "[REDACTED:CANARY]" in bodies[0]


async def test_reasoning_settings_follow_model_and_role() -> None:
    bodies: list[dict[str, object]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        return json_response(200, responses_body([text_output("ok")]))

    router = mocked_router(handler)
    await router.chat("coder", HELLO)
    await router.chat("summariser", HELLO)
    await router.chat("reviewer", HELLO)  # gpt-4.1: no reasoning parameters at all

    assert bodies[0]["reasoning"] == {"effort": "medium"}
    assert bodies[1]["reasoning"] == {"effort": "medium"}  # no low-effort override by default (D-161)
    assert "reasoning" not in bodies[2] and "include" not in bodies[2]
    assert bodies[0]["store"] is False


async def test_served_model_is_looked_up_once_when_response_names_the_deployment() -> None:
    info_requests: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.method == "GET":
            info_requests.append(request.url.path)
            return json_response(200, {"id": "primary-deployment", "model": "gpt-5.1"})
        return json_response(200, responses_body([text_output("ok")], model="primary-deployment"))

    router = mocked_router(handler)
    first = await router.chat("coder", HELLO)
    second = await router.chat("coder", HELLO)

    assert first.served_model == second.served_model == "gpt-5.1"
    assert info_requests == ["/openai/deployments/primary-deployment"]


def test_connection_errors_name_the_real_cause() -> None:
    # Seen on the office laptop: doctor said only "Connection error." for both models.
    import ssl

    import openai

    from forge.llm.azure_errors import map_openai_error
    from forge.net import connection_hint

    error = openai.APIConnectionError(request=httpx2.Request("POST", "https://x.openai.azure.com/"))
    error.__cause__ = ssl.SSLCertVerificationError("certificate verify failed: unable to get local issuer")
    mapped = str(map_openai_error(error))
    assert "SSLCertVerificationError" in mapped and "Windows certificate store" in mapped
    assert "resolved" in connection_hint("getaddrinfo failed")
    assert "HTTPS_PROXY" in connection_hint("ConnectTimeout: timed out")

"""Shared test helpers. Network failures are simulated at the HTTP transport layer (DECISIONS D-008)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import httpx2

from forge.config import ForgeConfig, Secrets, load_default_config_data
from forge.llm.azure_openai import AzureOpenAIProvider
from forge.llm.router import LLMRouter

FAKE_SECRETS = {
    "AZURE_OPENAI_ENDPOINT": "https://unit-test.openai.azure.com/",
    "AZURE_OPENAI_API_KEY": "unit-test-key-0123456789",
    "AZURE_OPENAI_API_VERSION": "2025-04-01-preview",
    "AZURE_OPENAI_DEPLOYMENT": "primary-deployment",
    "AZURE_OPENAI_SECONDARY_DEPLOYMENT": "secondary-deployment",
}

Handler = Callable[[httpx2.Request], httpx2.Response]


def default_config() -> ForgeConfig:
    return ForgeConfig.model_validate(load_default_config_data())


def fake_secrets() -> Secrets:
    return Secrets(dict(FAKE_SECRETS), source=None)


def mocked_router(handler: Handler, sleeps: list[float] | None = None, **router_kwargs: Any) -> LLMRouter:
    config = default_config()
    secrets = fake_secrets()

    def factory(model_key: str) -> AzureOpenAIProvider:
        client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
        return AzureOpenAIProvider(
            model_key, config.llm.models[model_key], config.llm.providers.azure, secrets, http_client=client
        )

    async def record_sleep(seconds: float) -> None:
        if sleeps is not None:
            sleeps.append(seconds)

    return LLMRouter(config, secrets, provider_factory=factory, sleep=record_sleep, **router_kwargs)


def responses_body(output: list[dict[str, Any]], model: str = "gpt-5.1-2025-11-13") -> dict[str, Any]:
    return {
        "id": "resp_test",
        "object": "response",
        "created_at": 0,
        "model": model,
        "status": "completed",
        "output": output,
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
        "usage": {
            "input_tokens": 100,
            "input_tokens_details": {"cached_tokens": 40},
            "output_tokens": 20,
            "output_tokens_details": {"reasoning_tokens": 5},
            "total_tokens": 120,
        },
    }


def text_output(text: str) -> dict[str, Any]:
    return {
        "type": "message",
        "id": "msg_1",
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": text, "annotations": []}],
    }


def function_call_output(name: str, arguments: str, call_id: str = "call_1") -> dict[str, Any]:
    return {
        "type": "function_call",
        "id": "fc_1",
        "call_id": call_id,
        "name": name,
        "arguments": arguments,
        "status": "completed",
    }


def chat_body(content: str, model: str = "gpt-4.1-2025-04-14") -> dict[str, Any]:
    return {
        "id": "chatcmpl_test",
        "object": "chat.completion",
        "created": 0,
        "model": model,
        "choices": [
            {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
    }


def json_response(
    status: int, body: dict[str, Any], headers: dict[str, str] | None = None
) -> httpx2.Response:
    return httpx2.Response(
        status, content=json.dumps(body), headers={"content-type": "application/json", **(headers or {})}
    )


def error_body(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


def sse_response(body: dict[str, Any]) -> httpx2.Response:
    """A streamed Responses-API reply (server-sent events) carrying the final response object."""
    events = []
    for item in body.get("output", []):
        for part in item.get("content", []) if item.get("type") == "message" else []:
            events.append(
                {
                    "type": "response.output_text.delta",
                    "delta": part.get("text", ""),
                    "item_id": item.get("id", "msg"),
                    "output_index": 0,
                    "content_index": 0,
                    "sequence_number": len(events),
                }
            )
    final_type = "response.incomplete" if body.get("status") == "incomplete" else "response.completed"
    events.append({"type": final_type, "response": body, "sequence_number": len(events)})
    stream = "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events)
    return httpx2.Response(200, content=stream.encode(), headers={"content-type": "text/event-stream"})


def reply(request: httpx2.Request, body: dict[str, Any]) -> httpx2.Response:
    """JSON or server-sent events, whichever the request asked for."""
    streaming = bool(json.loads(request.content or b"{}").get("stream"))
    return sse_response(body) if streaming else json_response(200, body)


async def run_pytest(context: ToolContext, selector: str = "") -> tuple[bool, str, TestReport]:
    """Runs pytest through the shell tool, as the model does (D-159); returns (ok, summary, report)."""
    from forge.toolkit.powershell import ps_quote
    from forge.toolkit.pytest_report import parse_pytest
    from forge.toolkit.shell import execute

    assert context.shell is not None
    python = context.shell.python or "python"
    result = await execute(
        context,
        f"& {ps_quote(python)} -m pytest -rfE --tb=short --no-header -p no:cacheprovider {selector}".rstrip(),
        300,
        context.workspace.info.app_subfolder or None,
    )
    report = parse_pytest(result.content)
    return (report.passed if report.ran else result.ok), result.content[-1500:], report


if TYPE_CHECKING:
    from forge.toolkit.base import ToolContext
    from forge.toolkit.pytest_report import TestReport

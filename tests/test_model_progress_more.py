"""D-367: a model call made by a tool, and a Gemini stream, tell the activity line what they are doing."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from google.genai import types

from forge.config import ModelConfig
from forge.llm.base import ChatRequest, LLMResponse, Message
from forge.llm.gemini import GeminiProvider, function_calls
from forge.toolkit.base import ToolContext


class _SlowRouter:
    async def chat(self, role: str, request: ChatRequest, on_text_delta: Any = None) -> LLMResponse:
        await asyncio.sleep(0.35)
        return LLMResponse(text="done")


async def test_a_tool_making_a_slow_model_call_reports_what_it_asks_and_for_how_long(
    original_repo: Any, tmp_path: Any
) -> None:
    from forge.workspace.create import create_workspace

    context = ToolContext(
        workspace=create_workspace(original_repo, tmp_path / "ws", "backend"), router=_SlowRouter()
    )
    seen: list[tuple[str, dict[str, Any]]] = []

    async def publish(kind: str, payload: dict[str, Any]) -> None:
        seen.append((kind, payload))

    context.publish = publish
    response = await context.ask_model(
        "vision", ChatRequest(messages=[Message.user("hi")]), "looking at the picture", beat_s=0.1
    )
    assert response.text == "done"
    lines = [p["line"] for kind, p in seen if kind == "tool_progress"]
    assert lines and all("asking the vision model: looking at the picture" in line for line in lines)
    count = len(lines)
    await asyncio.sleep(0.3)
    assert (
        len([1 for kind, _ in seen if kind == "tool_progress"]) == count
    )  # the heartbeat stops with the call


def _chunk(*parts: types.Part, finish: bool = False) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=list(parts)),
                finish_reason=types.FinishReason.STOP if finish else None,
            )
        ],
        model_version="gemini-x",
    )


def test_function_calls_of_a_chunk_are_named_with_their_size() -> None:
    chunk = _chunk(
        types.Part(
            function_call=types.FunctionCall(name="write_file", args={"path": "a.py", "content": "x" * 300})
        )
    )
    ((name, size),) = function_calls(chunk)
    assert name == "write_file" and size > 300
    assert function_calls(_chunk(types.Part(text="hello"))) == []


async def test_a_gemini_stream_reports_thinking_writing_and_preparing_a_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from forge.llm import base

    monkeypatch.setattr(base.StreamProgress, "INTERVAL_S", 0.0)
    chunks = [
        _chunk(types.Part(text="Comparing two layouts", thought=True)),
        _chunk(types.Part(text="Here is the plan. ")),
        _chunk(
            types.Part(function_call=types.FunctionCall(name="write_file", args={"content": "y" * 500})),
            finish=True,
        ),
    ]

    async def stream(**kwargs: Any) -> Any:
        async def gen() -> Any:
            for chunk in chunks:
                yield chunk

        return gen()

    provider = object.__new__(GeminiProvider)
    provider.model_key = "gem"
    provider.model = ModelConfig(
        label="g", provider="gemini", model_name="gemini-x", context_window=1000, max_output=100
    )
    provider.model_name = "gemini-x"
    provider._client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content_stream=stream))
    )  # type: ignore[assignment]
    seen: list[dict[str, Any]] = []

    async def on_progress(info: dict[str, Any]) -> None:
        seen.append(info)

    async def on_text(text: str) -> None:
        return None

    await provider.chat(
        ChatRequest(messages=[Message.user("go")], on_progress=on_progress, on_thinking=None), on_text
    )
    stages = [s["stage"] for s in seen]
    assert stages[0] == "waiting" and "writing" in stages and stages[-1] == "calling"
    assert seen[-1]["tool"] == "write_file" and seen[-1]["chars"] >= 500

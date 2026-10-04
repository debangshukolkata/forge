"""Live check of Forge's Gemini provider. Run on a machine with Google ADC (the office laptop); it cannot pass
on a machine without credentials.

    set GOOGLE_CLOUD_PROJECT=<project>  &  set GOOGLE_CLOUD_LOCATION=us-central1
    .venv\\Scripts\\python scripts\\dev\\gemini_smoke.py [model-name]

Each step prints OK or FAIL, so a failure says which piece of the adapter to look at.
"""

from __future__ import annotations

import asyncio
import base64
import io
import sys

from forge.config import GeminiProviderConfig, ModelConfig, Secrets
from forge.llm.base import ChatRequest, Message, ToolSpec
from forge.llm.gemini import GeminiProvider

READ_FILE = ToolSpec(
    name="read_file",
    description="Read a file's contents",
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "File path"}},
        "required": ["path"],
        "additionalProperties": False,
    },
)


def red_square_data_url() -> str:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), (220, 0, 0)).save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


async def step(name: str, coroutine) -> object | None:  # type: ignore[no-untyped-def]
    try:
        result = await coroutine
        print(f"OK   {name}")
        return result
    except Exception as error:  # a smoke script reports every failure rather than stopping at the first
        print(f"FAIL {name}: {type(error).__name__}: {str(error)[:300]}")
        return None


async def main(model_name: str) -> None:
    model = ModelConfig(
        provider="gemini", label=model_name, model_name=model_name, context_window=1_000_000, max_output=8192
    )
    provider = GeminiProvider("smoke", model, GeminiProviderConfig(), Secrets({}, None))

    reply = await step(
        "plain text", provider.chat(ChatRequest(messages=[Message.user("Reply with the single word: ready")]))
    )
    print("     ", getattr(reply, "text", None), getattr(reply, "usage", None))

    chunks: list[str] = []

    async def on_text(text: str) -> None:
        chunks.append(text)

    await step(
        "streaming", provider.chat(ChatRequest(messages=[Message.user("Count from 1 to 5.")]), on_text)
    )
    print("      chunks:", len(chunks))

    request = ChatRequest(
        messages=[Message.user("Read the file config.yaml and tell me what's in it.")], tools=[READ_FILE]
    )
    first = await step("tool call (Forge's own JSON schema)", provider.chat(request))
    calls = getattr(first, "tool_calls", [])
    if calls:
        print("      call:", calls[0].name, calls[0].arguments)
        history = [
            *request.messages,
            first.to_message("smoke"),
            Message.tool_result(calls[0].id, "port: 8080\nmode: dev"),
        ]  # type: ignore[union-attr]
        final = await step(
            "tool result round trip", provider.chat(ChatRequest(messages=history, tools=[READ_FILE]))
        )
        print("      ", getattr(final, "text", "")[:200])

    thoughts: list[str] = []

    async def on_thinking(text: str) -> None:
        thoughts.append(text)

    thinking = ChatRequest(
        messages=[Message.user("What's 17 * 23? Show your reasoning briefly.")],
        reasoning_effort="low",
        on_thinking=on_thinking,
    )
    answer = await step("thinking budget + thought summaries", provider.chat(thinking, on_text))
    print(
        "      reasoning tokens:",
        getattr(getattr(answer, "usage", None), "reasoning_tokens", None),
        "summaries:",
        len(thoughts),
    )

    picture = Message(
        role="user", content="What colour is this image? One word.", images=[red_square_data_url()]
    )
    seen = await step("image input", provider.chat(ChatRequest(messages=[picture])))
    print("     ", getattr(seen, "text", None))
    await provider.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "gemini-2.5-flash-lite"))

"""Live tests against the real Azure OpenAI deployments (DECISIONS D-008). Run with: pytest -m live"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx2
import pytest

from forge.config import ForgeConfig, Secrets, load_config, load_secrets
from forge.doctor import run_doctor
from forge.engine.events import EventBus, EventType
from forge.engine.inputs import Interrupt, SendMessage
from forge.engine.session_host import SessionHost
from forge.llm.azure_openai import AzureOpenAIProvider
from forge.llm.base import ChatRequest, Message, ToolSpec
from forge.llm.router import LLMRouter
from forge.safety.redact import Redactor
from tests.conftest import REPO_ROOT

pytestmark = pytest.mark.live

CLAIM_TOOL = ToolSpec(
    name="get_claim_amount",
    description="Look up the claimed amount (in rupees) for an insurance claim by its numeric id.",
    parameters={
        "type": "object",
        "properties": {"claim_id": {"type": "integer"}},
        "required": ["claim_id"],
        "additionalProperties": False,
    },
)


@pytest.fixture
def live(isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[ForgeConfig, Secrets]:
    env_file = REPO_ROOT / ".env"
    monkeypatch.setenv("FORGE_ENV_FILE", str(env_file))
    secrets = load_secrets(isolated_forge_home)
    if not secrets.get("AZURE_OPENAI_API_KEY"):
        pytest.skip("AZURE_OPENAI_* not configured in .env")
    return load_config(isolated_forge_home), secrets


def router_for(
    config: ForgeConfig,
    secrets: Secrets,
    api: str = "responses",
    redactor: Redactor | None = None,
    captured_bodies: list[str] | None = None,
) -> LLMRouter:
    config = config.model_copy(deep=True)
    config.llm.providers.azure.api = api  # type: ignore[assignment]

    async def capture(request: httpx2.Request) -> None:
        if captured_bodies is not None:
            captured_bodies.append(request.content.decode("utf-8", errors="replace"))

    def factory(model_key: str) -> AzureOpenAIProvider:
        client = httpx2.AsyncClient(event_hooks={"request": [capture]}, timeout=180)
        return AzureOpenAIProvider(
            model_key, config.llm.models[model_key], config.llm.providers.azure, secrets, http_client=client
        )

    kwargs = {"redactor": redactor} if redactor else {}
    return LLMRouter(config, secrets, provider_factory=factory, **kwargs)


async def test_streaming_text_round_trip(live: tuple[ForgeConfig, Secrets]) -> None:
    router = router_for(*live)
    deltas: list[str] = []

    async def on_delta(text: str) -> None:
        deltas.append(text)

    response = await router.chat(
        "coder", ChatRequest(messages=[Message.user("Count from 1 to 5, comma separated.")]), on_delta
    )

    assert "".join(deltas) == response.text
    assert "1" in response.text and "5" in response.text
    assert "gpt-5.1" in response.served_model
    assert router.cost.total_usd > 0


@pytest.mark.parametrize(
    ("model_key", "api"),
    [
        ("gpt51", "responses"),
        ("gpt51", "chat_completions"),
        ("gpt41", "responses"),
        ("gpt41", "chat_completions"),
    ],
)
async def test_tool_call_round_trip(live: tuple[ForgeConfig, Secrets], model_key: str, api: str) -> None:
    router = router_for(*live, api=api)
    router.set_role_model("coder", model_key)
    history = [
        Message.system("Use the tools you are given. Answer briefly."),
        Message.user("What is the claimed amount for claim 7? Reply with that amount doubled, digits only."),
    ]

    first = await router.chat("coder", ChatRequest(messages=history, tools=[CLAIM_TOOL]))

    assert first.finish_reason == "tool_calls"
    call = first.tool_calls[0]
    assert call.name == "get_claim_amount" and call.arguments == {"claim_id": 7}
    if model_key == "gpt51" and api == "responses":
        assert any(item["type"] == "reasoning" for item in first.provider_items or [])

    history += [first.to_message(model_key), Message.tool_result(call.id, json.dumps({"amount": 45000}))]
    second = await router.chat("coder", ChatRequest(messages=history, tools=[CLAIM_TOOL]))

    assert "90000" in second.text.replace(",", "")


async def collect_until(bus: EventBus, wanted: EventType, timeout: float = 120) -> list[EventType]:
    seen: list[EventType] = []
    subscription = bus.subscribe(since_seq=0)
    try:
        async with asyncio.timeout(timeout):
            async for event in subscription:
                seen.append(event.type)
                if event.type == wanted:
                    return seen
    finally:
        subscription.close()
    return seen


async def test_session_streams_message_events(live: tuple[ForgeConfig, Secrets], tmp_path: Path) -> None:
    host = SessionHost(router_for(*live), EventBus(tmp_path / "events.jsonl"))
    runner = asyncio.create_task(host.run())
    await host.submit(SendMessage(text="Reply with exactly the word: pong"))

    seen = await collect_until(host.bus, EventType.COST_UPDATED)
    await host.close()
    runner.cancel()

    events = host.bus.events_since(0)
    streamed = "".join(e.payload["text"] for e in events if e.type == EventType.MESSAGE_DELTA)
    done = next(e for e in events if e.type == EventType.MESSAGE_DONE)
    assert EventType.MESSAGE_DELTA in seen
    assert streamed == done.payload["text"]
    assert "pong" in streamed.lower()
    assert done.payload["served_model"].startswith("gpt-5.1")


async def test_interrupt_stops_a_long_answer(live: tuple[ForgeConfig, Secrets], tmp_path: Path) -> None:
    host = SessionHost(router_for(*live), EventBus(tmp_path / "events.jsonl"))
    runner = asyncio.create_task(host.run())
    await host.submit(SendMessage(text="Write a 1200-word essay about the river Hooghly."))

    await collect_until(host.bus, EventType.MESSAGE_DELTA)
    await host.submit(Interrupt())
    await collect_until(host.bus, EventType.NOTICE, timeout=30)
    await asyncio.sleep(0.2)

    kinds = [e.payload.get("kind") for e in host.bus.events_since(0) if e.type == EventType.NOTICE]
    assert "interrupted" in kinds
    assert not any(e.type == EventType.MESSAGE_DONE for e in host.bus.events_since(0))
    assert host.history[-1].content.endswith("[interrupted]")
    assert not host.busy
    await host.close()
    runner.cancel()


async def test_canary_secret_never_reaches_the_llm_or_the_log(
    live: tuple[ForgeConfig, Secrets], tmp_path: Path
) -> None:
    canary = "canary-7f3a9c2e41b8"
    redactor = Redactor()
    redactor.register(canary, "CANARY")
    bodies: list[str] = []
    log = tmp_path / "events.jsonl"
    host = SessionHost(router_for(*live, redactor=redactor, captured_bodies=bodies), EventBus(log, redactor))
    runner = asyncio.create_task(host.run())

    await host.submit(SendMessage(text=f"Repeat this token back to me exactly: {canary}"))
    await collect_until(host.bus, EventType.COST_UPDATED)
    await host.close()
    runner.cancel()

    assert bodies, "no request was captured"
    assert all(canary not in body for body in bodies)
    assert "[REDACTED:CANARY]" in bodies[0]
    assert canary not in log.read_text(encoding="utf-8")


async def test_doctor_reports_both_models(live: tuple[ForgeConfig, Secrets]) -> None:
    results = {result.name: result for result in await run_doctor()}

    assert all(result.status != "fail" for result in results.values()), results
    # "ok" only when the served model (not the deployment name) matches the configured label.
    assert results["Model gpt51"].status == "ok", results["Model gpt51"].detail
    assert results["Model gpt41"].status == "ok", results["Model gpt41"].detail
    assert results["Model gpt51"].detail.startswith("serves gpt-5.1")

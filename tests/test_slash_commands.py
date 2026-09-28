"""Slash commands need no LLM call, so they are tested offline."""

from __future__ import annotations

import asyncio

from forge.engine.events import EventBus, EventType
from forge.engine.inputs import SlashCommand
from forge.engine.session_host import SessionHost
from forge.safety.redact import Redactor
from tests.helpers import mocked_router


def unreachable(request: object) -> object:
    raise AssertionError("slash commands must not call the LLM")


async def run_commands(*commands: str) -> tuple[SessionHost, list[str]]:
    host = SessionHost(mocked_router(unreachable), EventBus(redactor=Redactor()))  # type: ignore[arg-type]
    runner = asyncio.create_task(host.run())
    for command in commands:
        await host.submit(SlashCommand(text=command))
    await asyncio.sleep(0.05)
    runner.cancel()
    outputs = [e.payload["text"] for e in host.bus.events_since(0) if e.type == EventType.NOTICE]
    return host, outputs


async def test_model_command_switches_role_models() -> None:
    host, outputs = await run_commands("/model reviewer gpt51", "/model gpt41")

    assert host.router.role_models["reviewer"] == "gpt51"
    assert host.router.role_models["coder"] == "gpt41"
    assert "coder       gpt41" in outputs[-1]


async def test_unknown_model_is_reported_not_crashing() -> None:
    host, outputs = await run_commands("/model coder gpt99")

    assert host.router.role_models["coder"] == "gpt51"
    assert "Unknown model 'gpt99'" in outputs[-1]


async def test_cost_help_clear_and_exit() -> None:
    host, outputs = await run_commands("/cost", "/help", "/clear", "/exit")

    assert outputs[0].startswith("Spent $0.0000 of $20.0000")
    assert "/model <role> <model>" in outputs[1]
    assert host.closed

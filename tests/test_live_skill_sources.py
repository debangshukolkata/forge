"""Live (real Azure model, real GitHub download): a design skill that is not part of DebCraft is fetched on first
use (D-562). `named`: the user asks for the taste skill, the model loads it, the download is approved and the
skill is installed and drives the page. `plain`: a page request that names no skill uses the built-in skill and
downloads nothing. Set SKILL_SOURCES_LOG to a file to get one JSON line per run."""

from __future__ import annotations

import asyncio
import json
import os

import pytest

from forge.config import forge_home
from forge.engine.headless import auto_reply
from forge.protocol.events import EventType
from forge.protocol.inputs import SendMessage
from tests.test_live_agent import make_host  # noqa: F401  (a fixture)

pytestmark = pytest.mark.live

TASTE = "design-taste-frontend"
SCENARIOS = {
    "named": "Use the taste skill to build a landing page for a small coffee shop called Kettle & Bean.",
    "plain": "Build a landing page for a small coffee shop called Kettle & Bean.",
}


@pytest.mark.parametrize("scenario", list(SCENARIOS))
async def test_a_named_design_skill_is_downloaded_and_the_built_in_one_is_the_default(
    scenario: str,
    make_host,  # noqa: F811
) -> None:  # type: ignore[no-untyped-def]
    host = make_host("auto")
    loads: list[str] = []
    questions: list[str] = []
    calls: list[str] = []
    after_load = 0
    runner = asyncio.create_task(host.run())
    subscription = host.bus.subscribe(since_seq=host.bus.last_seq)
    await host.submit(SendMessage(text=SCENARIOS[scenario]))
    try:
        async with asyncio.timeout(600):
            async for event in subscription:
                if (reply := auto_reply(event, auto_approve=True)) is not None:
                    await host.submit(reply)
                if event.type == EventType.QUESTION_ASKED:
                    questions.append(str(event.payload.get("question", ""))[:120])
                if event.type == EventType.TOOL_CALL_STARTED:
                    name = event.payload["name"]
                    calls.append(name)
                    if name == "load_skill":
                        loads.append(str(event.payload["arguments"]))
                    elif loads:
                        after_load += 1
                        if after_load >= 3 or name in ("write_file", "run_command"):
                            break  # the skill is in use: the rest of the build is not what this test measures
                if event.type in (EventType.COST_UPDATED, EventType.ERROR):
                    break
    finally:
        subscription.close()
        runner.cancel()
        await host.close()
    installed = (forge_home() / "skills" / TASTE / "SKILL.md").is_file()
    exempt = bool(host.agent and host.agent.context.design_exempt)
    log = os.environ.get("SKILL_SOURCES_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "scenario": scenario,
                        "loads": loads,
                        "questions": questions,
                        "installed": installed,
                        "design_gate_stands_aside": exempt,
                        "calls": calls,
                    }
                )
                + "\n"
            )
    print(f"\nSCENARIO {scenario}: loads={loads} questions={questions} installed={installed} exempt={exempt}")
    if scenario == "named":
        assert any(TASTE in text for text in loads), f"the taste skill was not loaded: {loads}"
        assert any("Download the skill" in text for text in questions), questions
        assert installed and exempt
    else:
        assert any("ui-design-quality" in text for text in loads), f"expected the built-in skill: {loads}"
        assert not installed and not any("Download the skill" in text for text in questions)

"""Live (real Azure model): which skills the model opens for different requests, with the user's installed skills
grouped into a pack (D-480). Each run stops at the first tool that is not load_skill: only the skill choice is checked.
Needs the skills in ~/.forge/skills; skipped when there are none."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path

import pytest

from forge.config import forge_home
from forge.engine.headless import auto_reply
from forge.protocol.events import EventType
from forge.protocol.inputs import SendMessage
from tests.test_live_agent import make_host  # noqa: F401  (a fixture)

pytestmark = pytest.mark.live

RUNS = int(os.environ.get("SKILL_LOADING_RUNS", "2"))

# Reading around and planning come before the skill in some runs; the first tool that changes or builds something ends the run.
LOOKING_TOOLS = (
    "ask_user",
    "todo_write",
    "list_dir",
    "read_file",
    "search",
    "grep",
    "glob",
    "find_asset",
    "design_kb_search",
    "library_api",
    "memory_write",
    "spawn_subagent",  # its inner tool calls are not on the event bus, so the run goes on to see whether the main agent loads the skill afterwards
)

# (request, skill names that count as a good choice; empty = the model should load nothing)
SCENARIOS = {
    "good_site": ("Build me a good looking landing page for a small coffee shop.", {"ui-design-quality"}),
    "ui_bad": ("The dashboard in this app looks bad. Improve the UI and UX.", {"ui-design-quality"}),
    "brutalist": (
        "I want the website to have a raw brutalist look, thick borders and monospace type.",
        {"ui-design-quality", "industrial-brutalist-ui", "design-extras"},
    ),
    "deck": ("Create a PowerPoint deck of five slides on our Q3 results.", {"make-presentation", "slides"}),
    "brand": (
        "Create brand guidelines and a colour palette for our new product.",
        {"brand", "brandkit", "design-extras"},
    ),
    "tests_first": ("Add a new validation rule to the claims form, test first.", {"test-first"}),
    "debug": ("Our claims endpoint returns a 500 for some inputs. Find out why.", {"debugging"}),
    "named_style": (
        "Restyle the landing page in a minimalist style, using one of the design skills you have installed.",
        {"minimalist-ui", "design-extras", "ui-design-quality"},
    ),
    "image_to_code": (
        "Here is a screenshot of a page I like. Turn it into code, use the image-to-code skill.",
        {"image-to-code", "design-extras"},
    ),
    "premium": ("Make the homepage feel more premium.", {"ui-design-quality", "design-extras"}),
    "portfolio": (
        "Build a portfolio site for a photographer, it has to stand out.",
        {"ui-design-quality", "design-extras"},
    ),
    "redesign": (
        "Redesign the existing pages, they look generic and templated.",
        {"ui-design-quality", "design-extras"},
    ),
    "typo": ("Fix the typo 'recieve' in the README.", set()),
}


@pytest.mark.parametrize("run", range(1, RUNS + 1))
@pytest.mark.parametrize("scenario", list(SCENARIOS))
async def test_skill_choice(scenario: str, run: int, make_host) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    request, good = SCENARIOS[scenario]
    real = Path.home() / ".forge" / "skills"
    if not real.is_dir():
        pytest.skip("no installed skills in ~/.forge/skills")
    shutil.copytree(real, forge_home() / "skills", dirs_exist_ok=True)
    host = make_host("auto")
    loaded: list[str] = []
    spawned: list[str] = []
    other_tool = ""
    said = ""
    runner = asyncio.create_task(host.run())
    subscription = host.bus.subscribe(since_seq=host.bus.last_seq)
    await host.submit(SendMessage(text=request))
    try:
        async with asyncio.timeout(420):
            async for event in subscription:
                if (reply := auto_reply(event, auto_approve=False)) is not None:
                    await host.submit(
                        reply
                    )  # a question the model asks first is answered with its own recommendation
                if event.type == EventType.TOOL_CALL_STARTED:
                    if event.payload["name"] == "spawn_subagent":
                        spawned.append(str(event.payload["arguments"])[:60])
                    if event.payload["name"] == "load_skill":
                        loaded.append(str(event.payload["arguments"]))
                    elif event.payload["name"] not in LOOKING_TOOLS:
                        other_tool = event.payload["name"]
                        break
                if event.type == EventType.MESSAGE_DONE:
                    said = str(event.payload.get("text", ""))[:300]
                if event.type in (EventType.COST_UPDATED, EventType.ERROR):
                    break
    finally:
        subscription.close()
        runner.cancel()
        await host.close()
    log = os.environ.get("SKILL_LOADING_LOG")
    if log:  # with parallel workers the printed lines are not shown, so each run also appends one line here
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "scenario": scenario,
                        "run": run,
                        "loaded": loaded,
                        "tool": other_tool,
                        "spawned": spawned,
                        "said": said[:120],
                    }
                )
                + "\n"
            )
    print(
        f"\nSCENARIO {scenario} run={run}: loaded={loaded} first_other_tool={other_tool!r} said={said.encode('ascii', 'replace').decode()!r}"
    )
    if scenario == "brand" and other_tool == "save_brand":
        return  # Forge's own brand tool is as good an answer as the pack
    if good and not loaded and not other_tool:
        pytest.skip(f"answered in text without any tool: {said[:80]!r}")
    if good:
        assert any(name in text for text in loaded for name in good), f"expected one of {good}, got {loaded}"
    else:
        assert not loaded, f"expected no skill, got {loaded}"

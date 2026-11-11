"""Live (real Azure model): does the model load a deferred tool when a task needs one (D-561)?

Each scenario is a request whose right answer uses a tool that is NOT in the starting tool list. A run passes
when the model calls one of the expected tools (after `tool_search`, after a skill that loads it, or directly);
it fails when the model does the job by hand first (shell, Python, or editing the file itself) or ends its turn
without the tool. One scenario checks the other side: a small edit must not trigger a search.
Set TOOL_SEARCH_LOG to a file to get one JSON line per run (parallel workers do not show printed lines)."""

from __future__ import annotations

import asyncio
import json
import os

import pytest

from forge.engine.headless import auto_reply
from forge.protocol.events import EventType
from forge.protocol.inputs import SendMessage
from tests.test_live_agent import make_host  # noqa: F401  (a fixture)

pytestmark = pytest.mark.live

RUNS = int(os.environ.get("TOOL_SEARCH_RUNS", "2"))
SHELL = {"run_command", "python_run", "start_background"}
EDITS = {"write_file", "edit_file", "multi_edit"}
NOTEBOOK = json.dumps(
    {
        "cells": [
            {
                "cell_type": "code",
                "metadata": {},
                "source": ["import math\n"],
                "outputs": [],
                "execution_count": 1,
            },
            {
                "cell_type": "code",
                "metadata": {},
                "source": ["print(math.sqrt(2))\n"],
                "outputs": [],
                "execution_count": 2,
            },
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
)

# name -> (request, tools that count as right, tools that mean "did it by hand")
SCENARIOS: dict[str, tuple[str, set[str], set[str]]] = {
    "notebook": (
        "Add a markdown cell at the top of analysis.ipynb (in the repository root) that says in one line what the notebook does.",
        {"notebook_read", "notebook_edit_cell"},
        SHELL | EDITS,
    ),
    "exact_lookup": (
        "Pick the main function of the claims service and list every place it is used. I want exact results, "
        "resolved the way Python resolves names, not a text search.",
        {"find_references", "find_definition", "list_symbols"},
        SHELL,
    ),
    "excel": (
        "Make an Excel workbook budget.xlsx with a monthly budget table for a team of five and a total row.",
        {"build_workbook"},
        SHELL,
    ),
    "font": (
        "Download the Inter font files into the project so the page can use the font without the internet.",
        {"find_font", "fetch_font"},
        SHELL,
    ),
    "mutation": (
        "Are the tests of the claims service any good? Check with mutation testing whether they would catch a bug.",
        {"mutation_check"},
        EDITS,
    ),
    "pdf": (
        "Create a one-page PDF named summary.pdf that says what this repository does.",
        {"build_pdf"},
        SHELL,
    ),
    "picture": (
        "Find a free-licence photo of a coffee cup and save it in the project's assets folder.",
        {"find_image", "fetch_image", "generate_image"},
        SHELL,
    ),
    "deck": (
        "Create a PowerPoint deck of three slides on what this repository does.",
        {"build_presentation"},
        SHELL,
    ),
    "typo": ("Fix the typo 'recieve' in the README.", set(), set()),
}


@pytest.mark.parametrize("run", range(1, RUNS + 1))
@pytest.mark.parametrize("scenario", list(SCENARIOS))
async def test_the_model_loads_the_tool_the_task_needs(scenario: str, run: int, make_host) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    request, right, by_hand = SCENARIOS[scenario]
    host = make_host("auto")
    if scenario == "notebook":
        (host.workspace.repo_dir / "analysis.ipynb").write_text(NOTEBOOK, encoding="utf-8")
    calls: list[str] = []
    searches: list[str] = []
    outcome = "ended without the tool"
    said = ""
    runner = asyncio.create_task(host.run())
    subscription = host.bus.subscribe(since_seq=host.bus.last_seq)
    await host.submit(SendMessage(text=request))
    try:
        async with asyncio.timeout(480):
            async for event in subscription:
                if (reply := auto_reply(event, auto_approve=True)) is not None:
                    await host.submit(reply)
                if event.type == EventType.TOOL_CALL_STARTED:
                    name = event.payload["name"]
                    calls.append(name)
                    if name in ("tool_search", "load_skill"):
                        searches.append(f"{name} {event.payload['arguments']}"[:120])
                    if name in right:
                        outcome = "used the tool"
                        break
                    if name in by_hand:
                        outcome = f"by hand: {name}"
                        break
                if event.type == EventType.MESSAGE_DONE:
                    said = str(event.payload.get("text", ""))[:300]
                if event.type in (EventType.COST_UPDATED, EventType.ERROR):
                    break
    finally:
        subscription.close()
        runner.cancel()
        await host.close()
    log = os.environ.get("TOOL_SEARCH_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "scenario": scenario,
                        "run": run,
                        "outcome": outcome,
                        "searches": searches,
                        "calls": calls,
                        "said": said[:160],
                    }
                )
                + "\n"
            )
    print(f"\nSCENARIO {scenario} run={run}: {outcome}; searches={searches}; calls={calls}")
    if right:
        assert outcome == "used the tool", f"{outcome}; calls={calls}; said={said[:120]!r}"
    else:
        assert "tool_search" not in calls, f"a small edit should not search for tools: {calls}"

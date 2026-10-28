"""Live (real Azure model, TODO L0 g): does the model find and bring in the right catalogue asset from a plain request?

Each scenario is a request a user might type, without naming a tool. The run stops at the first tool that is not reading, planning or looking
(a file write, a command) or when the turn ends: by then the model has either used find_asset and add_asset or has not. A run passes when the first asset it adds is one
of the acceptable ids; it fails when it adds a different one or never uses the catalogue. The deterministic search is tested in tests/test_assets.py;
this tests the model's use of it. Run with: pytest -m live -s -n 4 tests/test_live_asset_retrieval.py (RETRIEVAL_RUNS sets the repeats, default 2);
RETRIEVAL_LOG=<file> appends one JSON line per run."""

from __future__ import annotations

import asyncio
import json
import os

import pytest

from forge.engine.headless import auto_reply
from forge.protocol.events import EventType
from forge.protocol.inputs import SendMessage
from forge.tools.registry import default_tools
from tests.test_live_agent import make_host  # noqa: F401  (a fixture)

pytestmark = pytest.mark.live
RUNS = int(os.environ.get("RETRIEVAL_RUNS", "2"))
# Every read-only tool counts as looking, not building: the tool list changes, so it is read from the registry (a hand-kept list was missing code_outline,
# design_md_from_project and web_search, which ended runs early).
LOOKING_TOOLS = tuple(
    sorted(
        {tool.name for tool in default_tools() if tool.read_only}
        | {"ask_user", "todo_write", "load_skill", "find_asset", "memory_write", "spawn_subagent"}
    )
)

# (request, acceptable asset ids)
SCENARIOS = {
    "charity": (
        "Build a warm landing page for a blood donation charity.",
        {"tpl-landing-charity", "dir-soft-editorial", "ds-tpl-charity", "pal-warm-trust"},
    ),
    "festival": (
        "Make a loud poster-style page for a music festival.",
        {"dir-bold-poster", "ds-bold-poster", "tpl-event-conference"},
    ),
    "dashboard": (
        "I need a dark analytics dashboard with dense tables.",
        {
            "dir-dark-dashboard",
            "ds-dark-dashboard",
            "app-dashboard-analytics",
            "app-react-dashboard-analytics",
            "pal-dark-mode-product",
        },
    ),
    "portfolio": (
        "Build a minimal portfolio site for an architect.",
        {
            "tpl-landing-portfolio",
            "dir-minimal-monochrome",
            "ds-minimal-monochrome",
            "ds-tpl-portfolio",
            "lay-portfolio-casestudies",
            "lay-react-portfolio-casestudies",
        },
    ),
    "bento": ("Show our features as a bento grid.", {"sec-features-bento", "dir-bento", "ds-bento"}),
    "faq": ("Add an FAQ accordion to the page.", {"sec-faq-list"}),
    "count_up": (
        "The stats section should have numbers that count up when they scroll into view.",
        {"fx-count-up", "fx-scroll-reveal"},
    ),
    "float_label": (
        "Make the form inputs have a label that floats above the field when focused.",
        {"mi-input-float-label"},
    ),
    "sun_moon": ("Add a dark mode toggle that looks like a sun turning into a moon.", {"mi-toggle-sunmoon"}),
    "clinic": ("Pick a colour palette for a hospital website.", {"pal-calm-clinical"}),
    "table": (
        "Add a sortable, searchable table of orders.",
        {"cmp-data-table", "app-data-table", "app-react-data-table"},
    ),
    "marquee": (
        "Add a logo strip of our customers that scrolls endlessly.",
        {"fx-marquee", "sec-logo-strip"},
    ),
}


@pytest.mark.parametrize("run", range(1, RUNS + 1))
@pytest.mark.parametrize("scenario", list(SCENARIOS))
async def test_asset_retrieval(scenario: str, run: int, make_host) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    request, good = SCENARIOS[scenario]
    host = make_host("auto")
    searched: list[str] = []
    added: list[str] = []
    stopped_on = ""
    runner = asyncio.create_task(host.run())
    subscription = host.bus.subscribe(since_seq=host.bus.last_seq)
    await host.submit(SendMessage(text=request))
    try:
        async with asyncio.timeout(420):
            async for event in subscription:
                if (reply := auto_reply(event, auto_approve=False)) is not None:
                    await host.submit(reply)
                if event.type == EventType.TOOL_CALL_STARTED:
                    name = event.payload["name"]
                    arguments = event.payload.get("arguments") or {}
                    if name == "find_asset":
                        searched.append(str(arguments.get("query", arguments)))
                    elif name == "add_asset":
                        added.append(str(arguments.get("id", "")))
                        break
                    elif name not in LOOKING_TOOLS:
                        stopped_on = name
                        break
                if event.type in (
                    EventType.COST_UPDATED,
                    EventType.ERROR,
                ):  # the turn is over; a message on its way to a tool call is not
                    break
    finally:
        subscription.close()
        runner.cancel()
        await host.close()
    verdict = "hit" if added and added[0] in good else ("wrong" if added else "no add_asset")
    if log := os.environ.get("RETRIEVAL_LOG"):
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "scenario": scenario,
                        "run": run,
                        "verdict": verdict,
                        "searched": searched,
                        "added": added,
                        "stopped_on": stopped_on,
                    }
                )
                + "\n"
            )
    print(
        f"\nRETRIEVAL {scenario} run={run}: {verdict} searched={searched} added={added} stopped_on={stopped_on!r}"
    )
    assert verdict == "hit", f"{verdict}: searched {searched}, added {added}, expected one of {sorted(good)}"

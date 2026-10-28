"""Live (real Azure model, D-520): after the design skill was split, does the model open the moved file when its job needs it?

Each scenario is a request that belongs to one of the moved sections (an application screen, several design options, restyling an existing UI, a named
product's feel, motion). The run goes on until the first tool that is not reading or looking, and records every `load_skill` call with its `file`. A run passes
when the skill was loaded and the expected moved file was opened before that point, or when the model used the tool the section points to (`build_variants`,
`add_asset` on an application screen). Run with: pytest -m live -s -n 3 tests/test_live_skill_split.py (SKILL_SPLIT_RUNS repeats, default 2);
SKILL_SPLIT_LOG=<file> appends one JSON line per run."""

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
RUNS = int(os.environ.get("SKILL_SPLIT_RUNS", "2"))
LOOKING_TOOLS = tuple(
    sorted(
        {tool.name for tool in default_tools() if tool.read_only}
        | {"ask_user", "todo_write", "load_skill", "find_asset", "memory_write", "spawn_subagent"}
    )
)

# (request, the moved file that should be opened, tools that also count as having followed the section)
SCENARIOS = {
    "app_screen": (
        "Build a sales dashboard screen for our internal admin tool: KPIs, a chart and a table of recent orders.",
        "skill-applications.md",
        ("add_asset",),
    ),
    "variants": (
        "Give me three different design options for the homepage of a small bakery so I can choose one.",
        "skill-variants.md",
        ("build_variants",),
    ),
    "improve": (
        "The pricing page in this web app looks bad. Improve the UI and UX.",
        "skill-improving.md",
        (),
    ),
    "named_product": (
        "Make the settings page feel like Linear: dense, fast, keyboard friendly.",
        "skill-named-products.md",
        (),
    ),
    "motion": (
        "Add tasteful animation and motion effects to the landing page hero.",
        "skill-motion.md",
        ("add_asset",),
    ),
}

WEB_FILES = {
    "web/package.json": json.dumps(
        {
            "name": "shop",
            "private": True,
            "dependencies": {"react": "^19.0.0", "react-dom": "^19.0.0"},
            "devDependencies": {"@tailwindcss/vite": "^4.0.0", "tailwindcss": "^4.0.0", "vite": "^6.0.0"},
        }
    ),
    "web/src/index.css": '@import "tailwindcss";\n',
    "web/src/App.tsx": 'export default function App() {\n  return <main className="p-8"><h1 className="text-3xl">Harbour Street Shop</h1><p>Pricing: $10 a month.</p></main>;\n}\n',
}


@pytest.mark.parametrize("run", range(1, RUNS + 1))
@pytest.mark.parametrize("scenario", list(SCENARIOS))
async def test_the_moved_file_is_opened(scenario: str, run: int, make_host) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    request, expected_file, also_counts = SCENARIOS[scenario]
    host = make_host("auto")
    for relative, text in WEB_FILES.items():
        target = host.workspace.app_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    loads: list[tuple[str, str]] = []
    followed = False
    stopped_on = ""
    runner = asyncio.create_task(host.run())
    subscription = host.bus.subscribe(since_seq=host.bus.last_seq)
    await host.submit(SendMessage(text=request))
    try:
        async with asyncio.timeout(600):
            async for event in subscription:
                if (reply := auto_reply(event, auto_approve=False)) is not None:
                    await host.submit(reply)
                if event.type == EventType.TOOL_CALL_STARTED:
                    name = event.payload["name"]
                    arguments = event.payload.get("arguments") or {}
                    if name == "load_skill":
                        loads.append((str(arguments.get("name", "")), str(arguments.get("file") or "")))
                        if expected_file in str(arguments.get("file") or ""):
                            followed = True
                            break
                    elif name in also_counts:
                        followed = True
                        break
                    elif name not in LOOKING_TOOLS:
                        stopped_on = name
                        break
                if event.type in (EventType.COST_UPDATED, EventType.ERROR):
                    break
    finally:
        subscription.close()
        runner.cancel()
        await host.close()
    if log := os.environ.get("SKILL_SPLIT_LOG"):
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "scenario": scenario,
                        "run": run,
                        "followed": followed,
                        "loads": loads,
                        "stopped_on": stopped_on,
                    }
                )
                + "\n"
            )
    print(f"\nSKILL-SPLIT {scenario} run={run}: followed={followed} loads={loads} stopped_on={stopped_on!r}")
    if (
        not followed and scenario == "variants"
    ):  # the same with the unsplit skill (measured 2026-10-28, D-524), so not a split problem: open item in the TODO
        pytest.xfail(
            "the model ends this request without calling build_variants, with or without the split (TODO)"
        )
    assert followed, f"opened {loads}, expected a file containing {expected_file}; stopped on {stopped_on!r}"

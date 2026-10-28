"""Live (real Azure model, TODO L0 g): the same twelve plain requests as tests/test_live_asset_retrieval.py, in a workspace that already holds a small
React + Tailwind web app, and without stopping at the first message.

The first test uses the claims-app fixture (a Flask back end), where a request such as "Add an FAQ accordion" has nowhere to go, and it stops at the
first question or search, so it understates what happens in a real design job. Here the model has a web project to work in and the run goes on until the
first asset is added or the first file is written (a model that never looks in the catalogue ends there). A run passes when the first asset it adds is one
of the acceptable ids. Run with: pytest -m live -s -n 4 tests/test_live_asset_retrieval_web.py (RETRIEVAL_RUNS repeats, default 2);
RETRIEVAL_LOG=<file> appends one JSON line per run."""

from __future__ import annotations

import asyncio
import json
import os

import pytest

from forge.engine.headless import auto_reply
from forge.protocol.events import EventType
from forge.protocol.inputs import SendMessage
from tests.test_live_agent import make_host  # noqa: F401  (a fixture)
from tests.test_live_asset_retrieval import LOOKING_TOOLS, SCENARIOS

pytestmark = pytest.mark.live
RUNS = int(os.environ.get("RETRIEVAL_RUNS", "2"))
WRITING_TOOLS = ("write_file", "edit_file", "multi_edit", "run_command", "shadcn_setup", "create_project")

WEB_FILES = {
    "web/package.json": json.dumps(
        {
            "name": "shop-site",
            "private": True,
            "scripts": {"dev": "vite", "build": "tsc --noEmit && vite build"},
            "dependencies": {"react": "^19.0.0", "react-dom": "^19.0.0"},
            "devDependencies": {
                "@tailwindcss/vite": "^4.0.0",
                "tailwindcss": "^4.0.0",
                "typescript": "^5.6.0",
                "vite": "^6.0.0",
            },
        },
        indent=2,
    ),
    "web/src/index.css": '@import "tailwindcss";\n',
    "web/src/main.tsx": 'import { createRoot } from "react-dom/client";\nimport App from "./App";\nimport "./index.css";\n\ncreateRoot(document.getElementById("root")!).render(<App />);\n',
    "web/src/App.tsx": 'export default function App() {\n  return <main className="p-8"><h1 className="text-3xl font-semibold">Harbour Street Shop</h1></main>;\n}\n',
}


@pytest.mark.parametrize("run", range(1, RUNS + 1))
@pytest.mark.parametrize("scenario", list(SCENARIOS))
async def test_asset_retrieval_in_a_web_project(scenario: str, run: int, make_host) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    request, good = SCENARIOS[scenario]
    host = make_host("auto")
    for relative, text in WEB_FILES.items():
        target = host.workspace.app_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    searched: list[str] = []
    added: list[str] = []
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
                    if name == "find_asset":
                        searched.append(str(arguments.get("query", arguments)))
                    elif name == "add_asset":
                        added.append(str(arguments.get("id", "")))
                        break
                    elif name in WRITING_TOOLS and name not in LOOKING_TOOLS:
                        stopped_on = name
                        break
                if event.type in (EventType.COST_UPDATED, EventType.ERROR):
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
        f"\nRETRIEVAL-WEB {scenario} run={run}: {verdict} searched={searched} added={added} stopped_on={stopped_on!r}"
    )
    assert verdict == "hit", f"{verdict}: searched {searched}, added {added}, expected one of {sorted(good)}"

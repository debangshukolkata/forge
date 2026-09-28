"""`forge new` / `forge export` and the workspace slash commands (no LLM involved)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from forge.cli import main
from forge.engine.events import EventBus, EventType
from forge.engine.inputs import SlashCommand
from forge.engine.session_host import SessionHost
from forge.safety.redact import Redactor
from forge.workspace.workspace import Workspace
from tests.helpers import mocked_router


def test_new_then_export(original_repo: Path, tmp_path: Path, isolated_forge_home: Path) -> None:
    workspace_path = tmp_path / "req-1"

    assert main(["new", "--repo", str(original_repo), "--workspace", str(workspace_path)]) == 0
    workspace = Workspace.open(workspace_path)
    workspace.write_text("backend/claims_app/added.py", "added = True\n")
    assert main(["export", "--workspace", str(workspace_path)]) == 0

    assert workspace.info.app_subfolder == "backend"  # auto-detected: the only candidate
    assert (workspace_path / "output" / "backend" / "claims_app" / "added.py").is_file()
    remembered = json.loads((isolated_forge_home / "repos.json").read_text(encoding="utf-8"))
    assert list(remembered.values()) == [{"app_subfolder": "backend"}]


def test_new_refuses_a_workspace_inside_the_repo(original_repo: Path) -> None:
    assert main(["new", "--repo", str(original_repo), "--workspace", str(original_repo / "ws")]) == 1


async def run_commands(workspace: Workspace, *commands: str) -> list[str]:
    def unreachable(request: object) -> object:
        raise AssertionError("no LLM call expected")

    host = SessionHost(mocked_router(unreachable), EventBus(redactor=Redactor()), workspace=workspace)  # type: ignore[arg-type]
    runner = asyncio.create_task(host.run())
    for command in commands:
        await host.submit(SlashCommand(text=command))
    await asyncio.sleep(0.2)
    runner.cancel()
    return [e.payload["text"] for e in host.bus.events_since(0) if e.type == EventType.NOTICE]


async def test_workspace_slash_commands(original_repo: Path, tmp_path: Path) -> None:
    from forge.workspace.create import create_workspace

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    workspace.write_text("backend/claims_app/a.py", "a = 1\n")
    workspace.write_text("backend/claims_app/b.py", "b = 2\n")

    outputs = await run_commands(workspace, "/checkpoints", "/undo", "/export", "/rewind 1", "/undo")

    assert "write backend/claims_app/a.py" in outputs[0] and "write backend/claims_app/b.py" in outputs[0]
    assert outputs[1] == "Undid checkpoint 2: write backend/claims_app/b.py"
    assert outputs[2] == "output/ rebuilt: 1 added, 0 modified, 0 deleted."
    assert outputs[3] == "Rewound 1 checkpoint(s): write backend/claims_app/a.py"
    assert outputs[4] == "Nothing to undo."
    assert not workspace.path_of("backend/claims_app/a.py").exists()


async def test_workspace_commands_without_a_workspace_explain_how() -> None:
    def unreachable(request: object) -> object:
        raise AssertionError("no LLM call expected")

    host = SessionHost(mocked_router(unreachable), EventBus(redactor=Redactor()))  # type: ignore[arg-type]
    runner = asyncio.create_task(host.run())
    await host.submit(SlashCommand(text="/undo"))
    await asyncio.sleep(0.05)
    runner.cancel()

    assert "--workspace" in host.bus.events_since(0)[-1].payload["text"]

"""M10E: Claude Code parity — FORGE.md instructions and '#', @-mentions and long pastes, effort and style,
skills, custom subagents, notebook tools, local git history, sessions/export-chat, and the MCP client."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

from forge.config import McpServerConfig
from forge.engine.session_host import SessionHost
from forge.parity.agents import load_agents
from forge.parity.history import History
from forge.parity.mcp_client import McpHub
from forge.parity.mentions import LONG_PASTE_CHARS, expand
from forge.parity.sessions import export_chat
from forge.parity.skills import discover
from forge.protocol.events import EventBus, EventType
from forge.protocol.inputs import Answer
from forge.safety.permissions import PermissionGate
from forge.safety.redact import Redactor
from forge.toolkit.base import ToolContext
from forge.tools.notebook import NotebookEditCell, NotebookRead
from forge.tools.parity import LoadSkill
from forge.workspace.create import create_workspace
from forge.workspace.workspace import Workspace
from tests.helpers import mocked_router


def unreachable(request: object) -> object:
    raise AssertionError("no LLM call expected")


@pytest.fixture
def workspace(original_repo: Path, tmp_path: Path) -> Workspace:
    return create_workspace(original_repo, tmp_path / "ws", "backend")


@pytest.fixture
def host(workspace: Workspace) -> SessionHost:
    return SessionHost(mocked_router(unreachable), EventBus(redactor=Redactor()), workspace=workspace)


def test_instruction_files_are_pinned_in_order(
    host: SessionHost, workspace: Workspace, isolated_forge_home: Path
) -> None:
    (isolated_forge_home / "FORGE.md").write_text("- Always use type hints.", encoding="utf-8")
    (workspace.root / "FORGE.md").write_text(
        "- This requirement: keep the old endpoint working.", encoding="utf-8"
    )
    host.refresh_instructions()
    pinned = host.context_manager.pinned.get("instructions") or ""
    assert pinned.index("type hints") < pinned.index("old endpoint")
    host.style = "learning"
    host.refresh_instructions()
    assert "TODO(you)" in (host.context_manager.pinned.get("instructions") or "")
    assert "flask-smorest-endpoint" in (host.context_manager.pinned.get("skills") or "")


async def test_hash_line_saves_an_instruction_after_asking(host: SessionHost, workspace: Workspace) -> None:
    subscription = host.bus.subscribe(since_seq=host.bus.last_seq)

    async def answer() -> None:
        async for event in subscription:
            if event.type == EventType.QUESTION_ASKED:
                subscription.close()
                await host.submit(Answer(question_id=event.payload["id"], choice="workspace"))
                return

    responder = asyncio.create_task(answer())
    assert await host._prepare_message("# never touch the sql folder") is None
    await responder
    assert "never touch the sql folder" in (workspace.root / "FORGE.md").read_text(encoding="utf-8")
    assert "never touch the sql folder" in (host.context_manager.pinned.get("instructions") or "")


async def test_think_hard_raises_effort_for_one_turn(host: SessionHost) -> None:
    text = await host._prepare_message("think hard: why does the triage graph loop?")
    assert text == "why does the triage graph loop?"
    assert host.agent is not None and host.agent.turn_effort == "high"


def test_mentions_files_ranges_objects_images_and_long_pastes(workspace: Workspace, tmp_path: Path) -> None:
    image = tmp_path / "scan.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    lookup = {"DBR": lambda ident: f"request {ident}" if ident == "DBR-7" else None}
    result = expand(
        f"Look at @backend/claims_app/errors.py:1-3 and @DBR-7, plus @{image} and @backend/.env",
        workspace,
        lookup,
    )
    assert "[@backend/claims_app/errors.py lines 1-3]" in result.text and "request DBR-7" in result.text
    assert result.images and result.images[0].parent == workspace.forge_dir / "inputs"
    assert "SECRET" not in result.text and ".env]" not in result.text  # secret files are never inlined
    long = expand("x" * (LONG_PASTE_CHARS + 10), workspace)
    assert "read it with read_file" in long.text and len(long.text) < 2000


def test_skills_and_custom_agents(isolated_forge_home: Path) -> None:
    folder = isolated_forge_home / "skills" / "our-logging"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(
        "---\nname: our-logging\ndescription: Log with our JSON logger.\n---\nUse log.info(...).",
        encoding="utf-8",
    )
    skills = discover(isolated_forge_home / "skills")
    assert "our-logging" in skills and "pytest-patterns" in skills
    assert skills["our-logging"].body() == "Use log.info(...)."
    agents_dir = isolated_forge_home / "agents"
    agents_dir.mkdir()
    (agents_dir / "sql-reviewer.md").write_text(
        "---\ndescription: Reviews SQL\ntools: read_file, grep\nmodel: reviewer\neffort: high\n---\nReview SQL for injection.",
        encoding="utf-8",
    )
    agent = load_agents(isolated_forge_home)["sql-reviewer"]
    assert agent.tools == ["read_file", "grep"] and agent.role == "reviewer" and agent.effort == "high"


async def test_load_skill_tool(workspace: Workspace) -> None:
    result = await LoadSkill().run(LoadSkill.Args(name="sql-migration-raw"), ToolContext(workspace=workspace))
    assert result.ok and "rollback" in result.content.lower()
    missing = await LoadSkill().run(LoadSkill.Args(name="nope"), ToolContext(workspace=workspace))
    assert not missing.ok and "pytest-patterns" in missing.content


async def test_notebook_read_and_edit(workspace: Workspace) -> None:
    notebook = {
        "cells": [
            {"cell_type": "markdown", "metadata": {}, "source": ["# Title\n"]},
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 1,
                "source": ["print(1)\n"],
                "outputs": [{"output_type": "stream", "name": "stdout", "text": ["1\n"]}],
            },
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    workspace.write_text("backend/analysis.ipynb", json.dumps(notebook))
    context = ToolContext(workspace=workspace)
    read = await NotebookRead().run(NotebookRead.Args(path="backend/analysis.ipynb"), context)
    assert "[1] code" in read.content and "print(1)" in read.content and "--- output ---\n1" in read.content
    edit = NotebookEditCell.Args(
        path="backend/analysis.ipynb", index=1, source="print(2)\n", clear_outputs=True
    )
    assert (await NotebookEditCell().run(edit, context)).ok
    insert = NotebookEditCell.Args(
        path="backend/analysis.ipynb", index=2, action="insert", source="x = 3", cell_type="code"
    )
    assert (await NotebookEditCell().run(insert, context)).ok
    saved = json.loads(workspace.path_of("backend/analysis.ipynb").read_text(encoding="utf-8"))
    assert "".join(saved["cells"][1]["source"]) == "print(2)\n" and saved["cells"][1]["outputs"] == []
    assert len(saved["cells"]) == 3
    stale_ctx = ToolContext(workspace=workspace)  # never read in this context
    assert not (await NotebookEditCell().run(edit, stale_ctx)).ok


def test_local_history_commits_per_task_outside_the_repo_copy(workspace: Workspace) -> None:
    history = History(workspace)
    if not history.available:
        pytest.skip("git not installed")
    assert history.ensure()  # sessions take the baseline at start, before any work
    workspace.write_text("backend/claims_app/new.py", "X = 1\n")
    commit = history.commit("T1: add new module")
    assert commit and "T1: add new module" in history.log()
    assert "claims_app/new.py" in history.diff("T1")
    assert (
        not (workspace.repo_dir / ".git").exists() and (workspace.forge_dir / "history.git" / "HEAD").exists()
    )
    assert history.commit("T2: nothing changed") is None
    assert ".env" not in history.diff("T1")


def test_export_chat_writes_markdown(host: SessionHost, workspace: Workspace) -> None:
    from forge.protocol.events import Event

    events = [
        Event(seq=1, type=EventType.USER_MESSAGE, ts="", payload={"text": "Add an endpoint"}),
        Event(seq=2, type=EventType.MESSAGE_DONE, ts="", payload={"text": "Done: added GET /x"}),
    ]
    path = export_chat(workspace, events)
    text = path.read_text(encoding="utf-8")
    assert "## You\n\nAdd an endpoint" in text and "## Forge\n\nDone: added GET /x" in text


MCP_SERVER = '''from mcp.server.mcpserver import MCPServer

server = MCPServer("demo")


@server.tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


server.run()
'''


async def test_mcp_tools_are_listed_called_and_gated(tmp_path: Path) -> None:
    pytest.importorskip("mcp")
    script = tmp_path / "demo_server.py"
    script.write_text(MCP_SERVER, encoding="utf-8")
    hub = McpHub({"demo": McpServerConfig(command=sys.executable, args=[str(script)])})
    try:
        tools = await asyncio.wait_for(hub.start(), 60)
        assert [t.name for t in tools] == ["mcp__demo__add"], hub.errors
        spec = tools[0].spec()
        assert spec.parameters["properties"]["a"]["type"] == "integer"
        result = await tools[0].run(tools[0].Args.model_validate({"a": 2, "b": 3}), None)  # type: ignore[arg-type]
        assert result.ok and result.content.strip() == "5"
        gate = PermissionGate("default", tmp_path / "permissions.json")
        assert gate.decide("mcp__demo__add", False, None, None).verdict == "ask"
        assert (
            PermissionGate("auto", tmp_path / "p2.json").decide("mcp__demo__add", False, None, None).verdict
            == "allow"
        )
        assert "demo: connected (1 tools)" in hub.describe()
    finally:
        await hub.close()


def test_custom_agent_files_can_set_max_steps_and_a_write_folder(isolated_forge_home: Path) -> None:
    from forge.parity.agents import load_agents

    folder = isolated_forge_home / "agents"
    folder.mkdir()
    (folder / "scribe.md").write_text(
        "---\ndescription: writes notes\ntools: read_file, write_file\nmax_steps: 5\n"
        "write_only_under: docs/notes\n---\nYou write notes.\n",
        encoding="utf-8",
    )
    (folder / "plain.md").write_text("---\ndescription: plain\nmax_steps: 9999\n---\nx\n", encoding="utf-8")
    agents = load_agents(isolated_forge_home)
    assert agents["scribe"].max_steps == 5 and agents["scribe"].write_only_under == "docs/notes/"
    assert (
        agents["plain"].max_steps is None and agents["plain"].write_only_under is None
    )  # 9999 is out of range


async def test_a_custom_agent_with_unknown_tools_is_rejected_clearly(
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path
) -> None:
    import httpx2

    from forge.engine.session_host import SessionHost
    from forge.protocol.events import EventBus
    from forge.safety.redact import Redactor
    from forge.subagents.spawn_tool import SpawnSubagent
    from forge.workspace.create import create_workspace
    from tests.helpers import mocked_router

    folder = isolated_forge_home / "agents"
    folder.mkdir()
    (folder / "odd.md").write_text("---\ntools: read_file, teleport\n---\nx\n", encoding="utf-8")
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    host = SessionHost(
        mocked_router(lambda r: httpx2.Response(500)), EventBus(redactor=Redactor()), workspace=workspace
    )
    assert host.agent is not None
    result = await SpawnSubagent().run(SpawnSubagent.Args(agent="odd", task="go"), host.agent.context)
    assert not result.ok and "unknown tools: teleport" in result.content


async def test_load_skill_lists_and_reads_files_inside_its_folder(
    workspace: Workspace, isolated_forge_home: Path
) -> None:
    folder = isolated_forge_home / "skills" / "with-data"
    (folder / "data").mkdir(parents=True)
    (folder / "SKILL.md").write_text(
        "---\nname: with-data\ndescription: Has data.\n---\nSee data.", encoding="utf-8"
    )
    (folder / "data" / "styles.csv").write_text("name\nglass\n", encoding="utf-8")
    (isolated_forge_home / "secret.txt").write_text("not for the model", encoding="utf-8")
    context = ToolContext(workspace=workspace)

    body = await LoadSkill().run(LoadSkill.Args(name="with-data"), context)
    assert body.ok and "data/styles.csv" in body.content and "asks for approval" in body.content
    data = await LoadSkill().run(LoadSkill.Args(name="with-data", file="data/styles.csv"), context)
    assert data.ok and "glass" in data.content
    for outside in ("../../secret.txt", r"..\..\secret.txt", "C:/Windows/win.ini"):
        refused = await LoadSkill().run(LoadSkill.Args(name="with-data", file=outside), context)
        assert not refused.ok and "not a file inside the skill folder" in refused.content

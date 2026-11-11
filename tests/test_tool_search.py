"""Deferred tools and `tool_search` (D-561): only the core tools are sent; the rest are loaded on demand."""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

import httpx2

from forge.engine.session_host import SessionHost
from forge.llm.base import Message, ToolCall
from forge.llm.tokens import count_tools_tokens
from forge.parity.skills import discover
from forge.protocol.events import EventBus
from forge.safety.redact import Redactor
from forge.toolkit.base import ToolContext, ToolResult
from forge.tools.deferred import DEFERRED_GROUPS, GROUP_OF, expand
from forge.tools.parity import LoadSkill
from forge.tools.registry import MAX_TOOLS_PER_REQUEST, ToolRegistry, default_tools
from forge.tools.tool_search import ToolSearch
from forge.tools.vision import ocr_tools
from forge.workspace.create import create_workspace
from tests.helpers import mocked_router

CORE = {
    "read_file",
    "write_file",
    "edit_file",
    "grep",
    "glob",
    "run_command",
    "python_run",
    "web_search",
    "web_fetch",
    "load_skill",
    "install_skill",
    "browser_open",
    "browser_screenshot",
    "view_image",
    "read_pdf",
    "read_document",
    "archive",
    "todo_write",
}


def _names(registry: ToolRegistry, read_only_only: bool = False) -> set[str]:
    return {spec.name for spec in registry.specs(read_only_only)}


def _search(registry: ToolRegistry) -> ToolSearch:
    tool = registry.get("tool_search")
    assert isinstance(tool, ToolSearch)
    return tool


async def _run(registry: ToolRegistry, query: str, tmp_path: Path, **more: int) -> ToolResult:
    context = ToolContext(workspace=None)  # type: ignore[arg-type]  # tool_search never touches the workspace
    return await _search(registry).run(ToolSearch.Args(query=query, **more), context)


def test_only_the_core_tools_are_sent_and_the_list_is_much_lighter() -> None:
    everything = ToolRegistry()
    light = ToolRegistry(defer=True)
    sent = _names(light)
    assert sent >= CORE and "tool_search" in sent
    assert not sent & set(GROUP_OF)  # no deferred tool is sent before it is loaded
    assert len(sent) < 50 < len(everything.specs())
    assert count_tools_tokens(light.specs()) < count_tools_tokens(everything.specs()) / 2
    assert "tool_search" not in _names(everything)  # a registry that defers nothing has nothing to search


def test_every_deferred_name_is_a_real_tool_and_is_listed_for_the_model() -> None:
    real = {tool.name for tool in [*default_tools(), *ocr_tools()]}
    assert set(GROUP_OF) <= real, set(GROUP_OF) - real
    registry = ToolRegistry([*default_tools(), *ocr_tools()], defer=True)
    description = next(spec for spec in registry.specs() if spec.name == "tool_search").description
    for group, (_, names) in DEFERRED_GROUPS.items():
        assert f"[{group}]" in description
        for name in names:
            assert f"- {name} - " in description, name


async def test_select_loads_tools_by_name_and_by_group_and_shows_their_arguments(tmp_path: Path) -> None:
    registry = ToolRegistry(defer=True)
    before = next(spec for spec in registry.specs() if spec.name == "tool_search").description

    result = await _run(registry, "select:build_workbook, check_workbook", tmp_path)
    assert result.ok and result.meta["loaded"] == ["build_workbook", "check_workbook"]
    assert '"properties"' in result.content  # the schema, so the model can call it right
    assert {"build_workbook", "check_workbook"} <= _names(registry)
    assert "edit_workbook" not in _names(registry)

    group = await _run(registry, "select:pdf", tmp_path)
    assert group.ok and {"build_pdf", "redact_pdf", "split_pdf"} <= _names(registry)

    after = next(spec for spec in registry.specs() if spec.name == "tool_search").description
    assert after == before  # the list never changes mid-session: the prompt cache stays valid


async def test_keywords_find_the_right_tools(tmp_path: Path) -> None:
    for query, expected in [
        ("redact pdf", "redact_pdf"),
        ("excel formulas check", "check_workbook"),
        ("powerpoint slides build", "build_presentation"),
        ("download a font", "fetch_font"),
        ("jupyter notebook", "notebook_read"),
        ("where is this function defined", "find_definition"),
        ("generate an image", "generate_image"),
    ]:
        registry = ToolRegistry(defer=True)
        result = await _run(registry, query, tmp_path)
        assert result.ok and expected in result.meta["loaded"], (query, result.meta)
        assert len(result.meta["loaded"]) <= 5

    registry = ToolRegistry(defer=True)
    capped = await _run(registry, "presentation", tmp_path, max_results=2)
    assert len(capped.meta["loaded"]) == 2


async def test_a_search_that_finds_nothing_says_so_and_a_core_tool_is_pointed_at(tmp_path: Path) -> None:
    registry = ToolRegistry(defer=True)
    nothing = await _run(registry, "zzzz quantum teleport", tmp_path)
    assert not nothing.ok and "presentations" in nothing.content
    core = await _run(registry, "select:read_file", tmp_path)
    assert core.ok and "Already in your tool list" in core.content
    partly = await _run(registry, "select:build_pdf,not_a_tool", tmp_path)
    assert partly.ok and partly.meta["loaded"] == ["build_pdf"] and "not_a_tool" in partly.content


def test_plan_mode_still_offers_only_read_only_tools_after_loading() -> None:
    registry = ToolRegistry(defer=True, loaded=["spreadsheets"])
    plan = _names(registry, read_only_only=True)
    assert "read_workbook" in plan and "tool_search" in plan
    assert "build_workbook" not in plan and "build_workbook" in _names(registry)


def test_the_provider_limit_is_a_hard_stop_that_drops_the_oldest_loaded_tools() -> None:
    class Extra(default_tools()[0].__class__):  # type: ignore[misc]
        pass

    extras = []
    for number in range(MAX_TOOLS_PER_REQUEST):
        extra = Extra()
        extra.name = f"extra_{number}"
        extras.append(extra)
    registry = ToolRegistry([*default_tools(), *extras], defer=True, loaded=["build_pdf", "redact_pdf"])
    names = [spec.name for spec in registry.specs()]
    assert len(names) == MAX_TOOLS_PER_REQUEST
    assert {"read_file", "write_file", "run_command", "tool_search"} <= set(names)
    assert "build_pdf" not in names  # loaded first, so first to go; tool_search can load it again


def test_group_and_tool_names_expand_in_order_without_repeats() -> None:
    assert expand(["notebooks", "notebook_read", " build_pdf ", ""]) == [
        "notebook_read",
        "notebook_edit_cell",
        "build_pdf",
    ]


def test_built_in_skills_name_only_real_deferred_tools() -> None:
    real = {tool.name for tool in [*default_tools(), *ocr_tools()]}
    skills = discover()
    with_tools = {name: skill.tools for name, skill in skills.items() if skill.tools}
    assert {
        "make-presentation",
        "make-document",
        "make-spreadsheet",
        "pdf-toolkit",
        "ui-design-quality",
    } <= set(with_tools)
    for name, tools in with_tools.items():
        for tool in expand(tools):
            assert tool in real and tool in GROUP_OF, (name, tool)


def _host(original_repo: Path, tmp_path: Path) -> SessionHost:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    host = SessionHost(
        mocked_router(lambda request: httpx2.Response(500)),
        EventBus(redactor=Redactor()),
        workspace=workspace,
    )
    assert host.agent is not None
    return host


async def _call(host: SessionHost, name: str, arguments: dict[str, object]) -> str:
    assert host.agent is not None
    results: dict[str, Message] = {}
    call = ToolCall(id="c1", name=name, raw_arguments=json.dumps(arguments), arguments=arguments)
    await host.agent._run_calls([call], results)
    return str(results["c1"].content)


async def test_a_session_defers_and_loading_a_skill_loads_its_tools(
    original_repo: Path, tmp_path: Path
) -> None:
    host = _host(original_repo, tmp_path)
    assert host.agent is not None
    assert "build_workbook" not in _names(host.agent.tools) and "tool_search" in _names(host.agent.tools)

    meta = (await LoadSkill().run(LoadSkill.Args(name="make-spreadsheet"), host.agent.context)).meta
    assert "spreadsheets" in meta["attach_tools"]

    text = await _call(host, "load_skill", {"name": "make-spreadsheet"})
    assert "[Tools loaded with this" in text and "build_workbook" in text
    assert {"build_workbook", "edit_workbook", "check_workbook", "preview_file"} <= _names(host.agent.tools)
    assert "build_presentation" not in _names(host.agent.tools)

    plain = await _call(host, "load_skill", {"name": "debugging"})  # a skill without tools adds no note
    assert "[Tools loaded with this" not in plain


async def test_a_deferred_tool_called_without_a_search_is_loaded_and_the_model_gets_its_schema(
    original_repo: Path, tmp_path: Path
) -> None:
    host = _host(original_repo, tmp_path)
    assert host.agent is not None
    wrong = await _call(host, "image_info", {"file": "x.png"})
    assert "invalid arguments" in wrong and "was not loaded" in wrong and '"path"' in wrong
    assert "image_info" in _names(host.agent.tools)

    # With arguments that happen to be right it simply runs (here: the tool's own answer about a missing file).
    ran = await _call(host, "notebook_read", {"path": "missing.ipynb"})
    assert "was not loaded" not in ran and "invalid arguments" not in ran
    assert "notebook_read" in _names(host.agent.tools)

    again = await _call(host, "image_info", {"file": "x.png"})  # loaded by now: a plain argument error
    assert "invalid arguments" in again and "was not loaded" not in again


async def test_a_reopened_session_gets_back_the_tools_it_used(original_repo: Path, tmp_path: Path) -> None:
    host = _host(original_repo, tmp_path)
    assert host.agent is not None
    earlier = ToolCall(id="old", name="redact_pdf", raw_arguments="{}", arguments={})
    history = [
        Message.user("redact the report"),
        Message(role="assistant", content="", tool_calls=[earlier]),
        Message.tool_result("old", "done"),
        Message.user("and the next one"),
    ]
    assert "redact_pdf" not in _names(host.agent.tools)

    async def ignore(text: str) -> None:
        return None

    with contextlib.suppress(Exception):  # the mocked model answers 500; the tools are restored before that
        await host.agent._chat(history, ignore)
    assert "redact_pdf" in _names(host.agent.tools)

"""The tools available to the agent, filtered by permission mode (plan mode: read-only only)."""

from __future__ import annotations

from collections.abc import Iterable

from forge.llm.base import ToolSpec
from forge.toolkit.background import Monitor, ReadBackground, StartBackground, StopBackground
from forge.toolkit.base import Tool
from forge.toolkit.shell import PythonRun, RunCommand
from forge.tools.app_keys_tool import app_keys_tools
from forge.tools.archive import archive_tools
from forge.tools.assets import AddAsset, FindAsset
from forge.tools.brand_file import SaveBrand
from forge.tools.browser import browser_tools
from forge.tools.code_intel import code_intel_tools
from forge.tools.code_map_tool import CodeMapTool
from forge.tools.code_outline import code_outline_tools
from forge.tools.db import (
    DbCopyTable,
    DbQuery,
    DbRequestTool,
    DbSchema,
    MarkServerRun,
    ScratchExec,
    UseScratchDatabase,
)
from forge.tools.deferred import expand, is_deferrable
from forge.tools.design_candidates import design_candidate_tools
from forge.tools.design_inspire import design_inspire_tools
from forge.tools.design_knowledge import design_knowledge_tools
from forge.tools.design_md import design_md_tools
from forge.tools.design_palette import design_palette_tools
from forge.tools.document import document_tools
from forge.tools.document_preview import document_preview_tools
from forge.tools.files import DeleteFile, EditFile, MoveFile, MultiEdit, ReadFile, WriteFile
from forge.tools.findimage import findimage_tools
from forge.tools.fonts import font_tools
from forge.tools.imagegen import imagegen_tools
from forge.tools.knowledge_tools import KnowledgeSearch, KnowledgeWrite
from forge.tools.library_api import LibraryApi
from forge.tools.memory import InstructionsWrite, MemoryForget, MemoryRead, MemoryWrite
from forge.tools.model_switch import model_switch_tools
from forge.tools.notebook import NotebookEditCell, NotebookRead
from forge.tools.parity import LoadSkill
from forge.tools.pdf_toolkit import pdf_toolkit_tools
from forge.tools.presentation import presentation_tools
from forge.tools.presentation_raw import raw_tools
from forge.tools.presentation_sources import source_tools
from forge.tools.search import Glob, Grep, ListDir
from forge.tools.shadcn import AddUiComponent, ShadcnSetup
from forge.tools.show_app import ShowApp
from forge.tools.skill_install_tool import InstallSkill
from forge.tools.test_quality import MutationCheck
from forge.tools.theme_search import theme_search_tools
from forge.tools.todo import TodoWrite
from forge.tools.tool_search import ToolSearch
from forge.tools.vision import vision_tools
from forge.tools.visual_diff import CompareDesigns, VisualBaseline, VisualCheck
from forge.tools.web import WebFetch, WebSearch
from forge.tools.workbook import workbook_tools

MAX_TOOLS_PER_REQUEST = (
    128  # Azure OpenAI refuses a request with more tools (a 400 that ended the turn, D-462)
)


def default_tools() -> list[Tool]:
    return [
        ReadFile(),
        WriteFile(),
        EditFile(),
        MultiEdit(),
        DeleteFile(),
        MoveFile(),
        Glob(),
        ListDir(),
        Grep(),
        RunCommand(),
        MutationCheck(),
        CompareDesigns(),
        VisualBaseline(),
        VisualCheck(),
        PythonRun(),
        LibraryApi(),
        CodeMapTool(),
        KnowledgeSearch(),
        KnowledgeWrite(),
        *code_outline_tools(),
        *code_intel_tools(),
        SaveBrand(),
        ShadcnSetup(),
        AddUiComponent(),
        StartBackground(),
        ReadBackground(),
        StopBackground(),
        MarkServerRun(),
        WebSearch(),
        WebFetch(),
        MemoryRead(),
        MemoryWrite(),
        MemoryForget(),
        TodoWrite(),
        Monitor(),
        InstructionsWrite(),
        LoadSkill(),
        FindAsset(),
        AddAsset(),
        InstallSkill(),
        NotebookRead(),
        NotebookEditCell(),
        *browser_tools(),
        ShowApp(),
        *vision_tools(),
        *presentation_tools(),
        *raw_tools(),
        *source_tools(),
        *workbook_tools(),
        *design_md_tools(),
        *design_inspire_tools(),
        *design_knowledge_tools(),
        *design_candidate_tools(),
        *design_palette_tools(),
        *theme_search_tools(),
        *document_tools(),
        *document_preview_tools(),
        *pdf_toolkit_tools(),
        *archive_tools(),
        *app_keys_tools(),
        *imagegen_tools(),
        *findimage_tools(),
        *font_tools(),
        *model_switch_tools(),
    ]


def session_tools(mode_b: bool) -> list[Tool]:
    """The default tools of a session. A project that starts from nothing (Mode B) has no repository to map."""
    repository_only = {CodeMapTool.name, KnowledgeSearch.name, KnowledgeWrite.name}
    return [tool for tool in default_tools() if not (mode_b and tool.name in repository_only)]


def db_tools() -> list[Tool]:
    """Only offered when a database is configured (M7)."""
    return [DbSchema(), DbQuery(), ScratchExec(), DbRequestTool(), DbCopyTable(), UseScratchDatabase()]


class ToolRegistry:
    """The tools of one agent. With `defer=True` (the sessions and their subagents) only the core tools are sent
    to the model; the ones named in `tools/deferred.py` wait until `tool_search`, a skill or a direct call
    loads them (D-561). Without it every tool is sent, which is what a small hand-picked list wants."""

    def __init__(
        self, tools: list[Tool] | None = None, defer: bool = False, loaded: Iterable[str] = ()
    ) -> None:
        self._tools = {tool.name: tool for tool in (tools or default_tools())}
        self._defer = defer
        self._loaded: dict[str, None] = {}  # deferred tools loaded so far, oldest first
        if defer and self.deferrable():
            # First in the list, so the hard stop at the provider's limit can never cut it off.
            self._tools = {ToolSearch.name: ToolSearch(self), **self._tools}
        self.attach(loaded)

    def add(self, tool: Tool) -> None:
        self._tools[tool.name] = tool
        if self._defer and is_deferrable(tool.name) and ToolSearch.name not in self._tools:
            # First in the list, so the hard stop at the provider's limit can never cut it off.
            self._tools = {ToolSearch.name: ToolSearch(self), **self._tools}

    def remove(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def deferrable(self) -> list[Tool]:
        """The tools that are not sent until loaded, whether loaded by now or not."""
        return [tool for tool in self._tools.values() if self._defer and is_deferrable(tool.name)]

    def is_waiting(self, name: str) -> bool:
        """True for a tool the model cannot see yet."""
        return self._defer and name in self._tools and is_deferrable(name) and name not in self._loaded

    def loaded(self) -> list[str]:
        return list(self._loaded)

    def attach(self, names: Iterable[str]) -> list[str]:
        """Loads deferred tools (tool or group names) for the rest of the session; returns the ones that are
        tools of this registry, in the order given."""
        present = [name for name in expand(names) if name in self._tools]
        for name in present:
            if self._defer and is_deferrable(name):
                self._loaded.setdefault(name, None)
        return present

    def specs(self, read_only_only: bool = False) -> list[ToolSpec]:
        tools = [
            tool
            for tool in self._tools.values()
            if (tool.read_only or not read_only_only) and not self.is_waiting(tool.name)
        ]
        return [tool.spec() for tool in self.fit_request_limit(tools)]

    def all_specs(self) -> list[ToolSpec]:
        """Every tool, loaded or waiting (for checks that look at each schema)."""
        return [tool.spec() for tool in self._tools.values()]

    def fit_request_limit(self, tools: list[Tool]) -> list[Tool]:
        """A hard stop at the provider's limit. Only reachable with many MCP tools or after loading dozens of
        deferred ones: the deferred tools loaded longest ago go first (tool_search can load them again)."""
        excess = len(tools) - MAX_TOOLS_PER_REQUEST
        if excess <= 0:
            return tools
        dropped = set(list(self._loaded)[:excess])
        return [tool for tool in tools if tool.name not in dropped][:MAX_TOOLS_PER_REQUEST]

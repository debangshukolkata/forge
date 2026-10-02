"""The tools available to the agent, filtered by permission mode (plan mode: read-only only)."""

from __future__ import annotations

from forge.llm.base import ToolSpec
from forge.toolkit.background import ReadBackground, StartBackground, StopBackground
from forge.toolkit.base import Tool
from forge.toolkit.shell import PythonRun, RunCommand
from forge.tools.browser import browser_tools
from forge.tools.db import DbQuery, DbRequestTool, DbSchema, MarkServerRun, ScratchExec
from forge.tools.files import DeleteFile, EditFile, MoveFile, MultiEdit, ReadFile, WriteFile
from forge.tools.kb import FindReferences, FindSymbol, KbRead, KbSearch, ListSymbols
from forge.tools.memory import MemoryForget, MemoryRead, MemoryWrite
from forge.tools.notebook import NotebookEditCell, NotebookRead
from forge.tools.parity import LoadSkill
from forge.tools.search import Glob, Grep, ListDir
from forge.tools.verify import LangGraphCheck, OpenApiCheck, RunTests, Verify
from forge.tools.vision import vision_tools
from forge.tools.web import WebFetch, WebSearch


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
        KbSearch(),
        KbRead(),
        FindSymbol(),
        FindReferences(),
        ListSymbols(),
        RunCommand(),
        PythonRun(),
        StartBackground(),
        ReadBackground(),
        StopBackground(),
        MarkServerRun(),
        RunTests(),
        Verify(),
        OpenApiCheck(),
        LangGraphCheck(),
        WebSearch(),
        WebFetch(),
        MemoryRead(),
        MemoryWrite(),
        MemoryForget(),
        LoadSkill(),
        NotebookRead(),
        NotebookEditCell(),
        *browser_tools(),
        *vision_tools(),
    ]


def db_tools() -> list[Tool]:
    """Only offered when a database is configured (M7)."""
    return [DbSchema(), DbQuery(), ScratchExec(), DbRequestTool()]


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools = {tool.name: tool for tool in (tools or default_tools())}

    def add(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def specs(self, read_only_only: bool = False) -> list[ToolSpec]:
        return [tool.spec() for tool in self._tools.values() if tool.read_only or not read_only_only]

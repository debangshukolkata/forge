"""The tools available to the agent, filtered by permission mode (plan mode: read-only only)."""

from __future__ import annotations

from forge.llm.base import ToolSpec
from forge.toolkit.background import Monitor, ReadBackground, StartBackground, StopBackground
from forge.toolkit.base import Tool
from forge.toolkit.shell import PythonRun, RunCommand
from forge.tools.app_keys_tool import app_keys_tools
from forge.tools.archive import archive_tools
from forge.tools.assets import AddAsset, FindAsset
from forge.tools.brand_file import SaveBrand
from forge.tools.browser import browser_tools
from forge.tools.db import DbQuery, DbRequestTool, DbSchema, MarkServerRun, ScratchExec
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
from forge.tools.todo import TodoWrite
from forge.tools.vision import vision_tools
from forge.tools.visual_diff import CompareDesigns, VisualBaseline, VisualCheck
from forge.tools.web import WebFetch, WebSearch
from forge.tools.workbook import workbook_tools

MAX_TOOLS_PER_REQUEST = 128
# Rarely needed or overlapping tools, first to go when a session has more than the provider's limit.
LEAVE_OUT_FIRST = (
    "synth_samples",
    "run_eval",
    "design_md_diff",
    "design_kb_add",
    "compare_designs",
    "visual_baseline",
    "mutation_check",
    "merge_presentations",
    "split_presentation",
    "unpack_presentation",
    "pack_presentation",
    "notebook_edit_cell",
    "notebook_read",
    "design_md_export",
    "split_pdf",
    "extract_pdf_images",
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


def db_tools() -> list[Tool]:
    """Only offered when a database is configured (M7)."""
    return [DbSchema(), DbQuery(), ScratchExec(), DbRequestTool()]


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools = {tool.name: tool for tool in (tools or default_tools())}

    def add(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def remove(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def specs(self, read_only_only: bool = False) -> list[ToolSpec]:
        tools = [tool for tool in self._tools.values() if tool.read_only or not read_only_only]
        return [tool.spec() for tool in self.fit_request_limit(tools)]

    @staticmethod
    def fit_request_limit(tools: list[Tool]) -> list[Tool]:
        """Azure OpenAI rejects a request with more than 128 tools (a 400 that ended the whole turn, D-462).
        Over the limit, the tools least likely to be needed go first, in LEAVE_OUT_FIRST order; the rest stay."""
        excess = len(tools) - MAX_TOOLS_PER_REQUEST
        if excess <= 0:
            return tools
        present = {tool.name for tool in tools}
        dropped = {name for name in LEAVE_OUT_FIRST if name in present}
        dropped = set(sorted(dropped, key=LEAVE_OUT_FIRST.index)[:excess])
        kept = [tool for tool in tools if tool.name not in dropped]
        return kept[:MAX_TOOLS_PER_REQUEST]  # a hard stop if even the whole list was not enough

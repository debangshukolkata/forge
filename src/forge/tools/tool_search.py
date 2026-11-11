"""`tool_search`: finds deferred tools and loads them into the session (D-561), the way Claude Code does.

The tool's own description carries the list of deferred tools (name and one line each, by group), so the
model always knows what exists without paying for every schema. The list does not change when a tool is
loaded: a stable description keeps the provider's prompt cache.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from pydantic import Field

from forge.llm.base import ToolSpec
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools.deferred import DEFERRED_GROUPS, GROUP_OF, expand

if TYPE_CHECKING:
    from forge.tools.registry import ToolRegistry

SELECT = "select:"
LINE_CHARS = 110
MAX_RESULTS = 10
HEAD = (
    "Load tools that are not in your tool list yet. Only the core tools are loaded at the start; the tools "
    "listed below exist but cannot be called until you load them here. Call this BEFORE you do by hand (with "
    "run_command, python_run or write_file) a job one of them does, and before you tell the user something "
    "cannot be done. Query forms: `select:build_workbook,check_workbook` loads those tools by name; "
    "`select:spreadsheets` loads a whole group; any other text is a keyword search (e.g. `redact pdf`) that "
    "loads the best matches. The result shows each loaded tool's arguments; call the tool from your next "
    "step. A loaded tool stays loaded for the rest of the session, so do not load it twice."
)


def one_line(description: str) -> str:
    text = " ".join(description.split())
    return text if len(text) <= LINE_CHARS else text[: LINE_CHARS - 3].rsplit(" ", 1)[0] + "..."


class ToolSearch(Tool):
    name = "tool_search"
    read_only = True
    description = HEAD

    class Args(ToolArgs):
        query: str
        max_results: int = Field(default=5, ge=1, le=MAX_RESULTS)

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def spec(self) -> ToolSpec:
        spec = super().spec()
        return ToolSpec(
            name=spec.name, description=HEAD + "\n\n" + self.listing(), parameters=spec.parameters
        )

    def listing(self) -> str:
        """Every deferrable tool of this session by group, loaded or not (the text must not change mid-session)."""
        by_group: dict[str, list[Tool]] = {group: [] for group in DEFERRED_GROUPS}
        for tool in self._registry.deferrable():
            by_group.setdefault(GROUP_OF.get(tool.name, "other"), []).append(tool)
        lines = ["Deferred tools (group: purpose, then name - what it does):"]
        for group, tools in by_group.items():
            if not tools:
                continue
            purpose = DEFERRED_GROUPS[group][0] if group in DEFERRED_GROUPS else "other tools of this session"
            lines.append(f"[{group}] {purpose}")
            lines += [f"- {tool.name} - {one_line(tool.description)}" for tool in tools]
        return "\n".join(lines)

    def summary(self, args: ToolSearch.Args) -> str:
        return f"tool_search {args.query}"

    async def run(self, args: ToolSearch.Args, context: ToolContext) -> ToolResult:
        query = args.query.strip()
        deferrable = {tool.name: tool for tool in self._registry.deferrable()}
        if query.lower().startswith(SELECT):
            asked = expand(query[len(SELECT) :].split(","))
            names = [name for name in asked if name in deferrable]
            missing = [name for name in asked if name not in deferrable]
        else:
            names = self._ranked(query, list(deferrable.values()))[: args.max_results]
            missing = []
        if not names:
            core = [name for name in missing if self._registry.get(name) is not None]
            if core and len(core) == len(missing):
                return ToolResult(
                    ok=True, content=f"Already in your tool list: {', '.join(core)}. Call it directly."
                )
            return ToolResult(
                ok=False,
                content=(
                    f"No deferred tool matches {query!r}. Groups: {', '.join(DEFERRED_GROUPS)}. "
                    "Use `select:<tool or group name>` with a name from this tool's description, or other keywords. "
                    "A skill is not a tool: load it with load_skill, which also loads the tools it names."
                ),
            )
        self._registry.attach(names)
        blocks = [
            f"## {name}\n{deferrable[name].description}\nArguments (JSON schema): "
            + json.dumps(deferrable[name].spec().parameters, separators=(",", ":"))
            for name in names
        ]
        note = f"\n\nNot found: {', '.join(missing)}." if missing else ""
        return ToolResult(
            ok=True,
            content=f"Loaded {len(names)} tool(s): {', '.join(names)}. They are in your tool list from your "
            "next step; call them directly.\n\n" + "\n\n".join(blocks) + note,
            meta={"loaded": names},
        )

    @staticmethod
    def _ranked(query: str, tools: list[Tool]) -> list[str]:
        words = [word for word in re.findall(r"[a-z0-9]+", query.lower()) if len(word) > 1]
        scored: list[tuple[int, str]] = []
        for tool in tools:
            name_words = set(tool.name.split("_"))
            group = GROUP_OF.get(tool.name, "")
            group_text = (group + " " + DEFERRED_GROUPS[group][0]).lower() if group else ""
            text = tool.description.lower()
            score = sum(
                (6 if word in name_words or word.rstrip("s") in name_words else 0)
                + (3 if word in tool.name else 0)
                + (2 if word in group_text else 0)
                + (1 if word in text else 0)
                for word in words
            )
            if score:
                scored.append((score, tool.name))
        return [name for _, name in sorted(scored, key=lambda item: (-item[0], item[1]))]

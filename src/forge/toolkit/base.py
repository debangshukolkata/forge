"""Tool framework (spec §9): pydantic argument models, generated JSON schemas, uniform results."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict

from forge.llm.base import ToolSpec
from forge.llm.tokens import head_and_tail
from forge.workspace.workspace import Workspace

if TYPE_CHECKING:
    from forge.kb.knowledge import KnowledgeBase
    from forge.toolkit.background import BackgroundManager
    from forge.toolkit.shell import ShellSession

# Per-call output caps in tokens (spec §10.3); configured by context.tool_output_cap / shell_output_cap.
DEFAULT_TOOL_CAP_TOKENS = 6000
DEFAULT_SHELL_CAP_TOKENS = 4000
OutputKind = Literal["tool", "shell"]


class ToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolResult(BaseModel):
    ok: bool
    content: str
    meta: dict[str, Any] = {}
    full_output_path: str | None = None


class ReadTracker:
    """Read-before-edit (spec §8): remembers the hash of each file as the model last saw it."""

    def __init__(self) -> None:
        self._hashes: dict[str, str] = {}

    def record(self, relative: str, data: bytes) -> None:
        self._hashes[relative] = hashlib.sha256(data).hexdigest()

    def check(self, relative: str, current: bytes) -> str | None:
        """None if the model may edit the file; otherwise the reason it must read it first."""
        seen = self._hashes.get(relative)
        if seen is None:
            return f"You have not read {relative} yet. Read it with read_file before editing it."
        if seen != hashlib.sha256(current).hexdigest():
            return f"{relative} changed on disk since you last read it. Read it again before editing it."
        return None


PublishCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


@dataclass
class ToolContext:
    workspace: Workspace
    shell: ShellSession | None = None
    background: BackgroundManager | None = None
    kb: KnowledgeBase | None = None
    db: Any = None  # forge.db.session.DbSession, when a database is configured
    secrets: Any = None  # forge.config.Secrets: optional service keys (e.g. TAVILY_API_KEY); never shown
    summarise: Callable[[str, str], Awaitable[str]] | None = None  # (text, instruction) -> summary
    browser: Any = None  # forge.tools.browser.BrowserSession, started on first use
    web_search_provider: str = "auto"  # config web.search_provider
    web_search_order: tuple[str, ...] = ("duckduckgo", "serpapi", "azure", "tavily")  # web.search_order
    profile: Any = None  # forge.modeb.profile.HostProfile (Mode B)
    router: Any = None  # forge.llm.router.LLMRouter, for tools that run subagents
    sensitive_terms: tuple[str, ...] = ()  # Mode B: host-identifying words that must never reach a web search
    hosted_search: Callable[[str], Awaitable[tuple[str, list[dict[str, str]]]]] | None = None  # azure search
    interaction: Any = None  # the orchestrator (tools/interaction.Interaction), when orchestrated
    end_turn: bool = False  # a phase tool finished its phase: the agent loop stops after this step
    step: int = 0  # increases with every tool call; used for 'no claim without evidence'
    last_edit_step: int = 0
    last_verified_step: int = 0
    reads: ReadTracker = field(default_factory=ReadTracker)
    publish: PublishCallback | None = None  # engine event publisher (file diffs, etc.)
    tool_cap_tokens: int = DEFAULT_TOOL_CAP_TOKENS
    shell_cap_tokens: int = DEFAULT_SHELL_CAP_TOKENS

    async def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.publish is not None:
            await self.publish(event_type, payload)

    def cap_output(self, text: str, kind: OutputKind = "tool") -> tuple[str, str | None]:
        """Keeps the head and tail of long output (spec §10.3) and saves the full text to
        .forge/tool_outputs so it can be re-read in ranges."""
        cap = self.shell_cap_tokens if kind == "shell" else self.tool_cap_tokens
        head, tail, omitted = head_and_tail(text, cap)
        if omitted == 0:
            return text, None
        folder = self.workspace.jail.check(self.workspace.forge_dir / "tool_outputs")
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}.txt"
        path.write_text(text, encoding="utf-8")
        relative = path.relative_to(self.workspace.root).as_posix()
        marker = (
            f"\n\n[... {omitted} tokens omitted. Full output: {relative} — read it in ranges with "
            "read_file offset/limit, or narrow the command ...]\n\n"
        )
        return head + marker + tail, str(path)


class Tool:
    """Subclasses set name/description/Args/read_only and implement run()."""

    name: ClassVar[str]
    description: ClassVar[str]
    Args: ClassVar[type[ToolArgs]]
    read_only: ClassVar[bool] = False
    output_kind: ClassVar[OutputKind] = "tool"  # which token cap applies to its output

    async def run(self, args: Any, context: ToolContext) -> ToolResult:
        raise NotImplementedError

    def spec(self) -> ToolSpec:
        schema = inline_schema(self.Args.model_json_schema())
        return ToolSpec(name=self.name, description=self.description, parameters=schema)

    def summary(self, args: Any) -> str:
        """One line for UIs and approval prompts."""
        return f"{self.name} {args.model_dump(exclude_defaults=True)}"

    def command(self, args: Any, context: ToolContext) -> str | None:
        """The shell command this call would run, for the permission gate; None for non-shell tools."""
        return None

    def own_files_only(self, args: Any, context: ToolContext) -> bool:
        """True when the call only touches files Forge created in this workspace (none of the user's), so an
        always-ask tool may fall back to the ordinary approval rules."""
        return False


def inline_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Resolves $ref/$defs and drops titles: flat schemas work with every provider (Gemini rejects $ref)."""
    definitions = schema.get("$defs", {})

    def resolve(node: Any, is_property_map: bool = False) -> Any:
        if isinstance(node, dict):
            if is_property_map:  # keys are argument names (one may be called "title"), values are schemas
                return {name: resolve(value) for name, value in node.items()}
            if "$ref" in node:
                return resolve(definitions[node["$ref"].split("/")[-1]])
            return {
                key: resolve(value, is_property_map=(key == "properties"))
                for key, value in node.items()
                if key not in ("$defs", "title")
            }
        if isinstance(node, list):
            return [resolve(item) for item in node]
        return node

    resolved = resolve(schema)
    assert isinstance(resolved, dict)  # a schema object resolves to a schema object
    return resolved


def relative_display(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)

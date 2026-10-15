"""Tool framework (spec §9): pydantic argument models, generated JSON schemas, uniform results."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import time
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

    def paths(self) -> list[str]:
        return list(self._hashes)

    def check(self, relative: str, current: bytes) -> str | None:
        """None if the model may edit the file; otherwise the reason it must read it first."""
        seen = self._hashes.get(relative)
        if seen is None:
            return f"You have not read {relative} yet. Read it with read_file before editing it."
        if seen != hashlib.sha256(current).hexdigest():
            return f"{relative} changed on disk since you last read it. Read it again before editing it."
        return None


PublishCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


STATIC_SUFFIXES = (
    ".html",
    ".htm",
    ".css",
    ".scss",
    ".sass",
    ".less",
    ".svg",
    ".md",
    ".txt",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
)


@dataclass
class ToolContext:
    workspace: Workspace
    shell: ShellSession | None = None
    background: BackgroundManager | None = None
    db: Any = None  # forge.db.session.DbSession, when a database is configured
    image_candidates: dict[str, Any] = field(
        default_factory=dict
    )  # find_image results of this session, by id (for fetch_image)
    last_image_query: str = (
        ""  # the last find_image query: its words tag the picture fetch_image keeps in the library
    )
    images_generated: int = 0  # pictures made by generate_image in this session (a cap stops a runaway loop)
    secrets: Any = None  # forge.config.Secrets: optional service keys (e.g. SERPAPI_API_KEY); never shown
    summarise: Callable[[str, str], Awaitable[str]] | None = None  # (text, instruction) -> summary
    browser: Any = None  # forge.tools.browser.BrowserSession, started on first use
    web_search_provider: str = "auto"  # config web.search_provider
    web_search_order: tuple[str, ...] = (
        "searxng",
        "tavily",
        "duckduckgo",
        "serpapi",
        "azure",
    )  # web.search_order
    web_tavily_topic: str = "General"  # web.tavily_topic: the topic sent to the Tavily tool (D-210)
    web_policy: Any = None  # forge.tools.web_guard.WebPolicy: which addresses web_fetch may reach (D-209)
    web_render: bool = True  # web.render: use the headless browser for pages that need JavaScript
    web_archive: bool = True  # web.archive_fallback
    profile: Any = None  # forge.modeb.profile.HostProfile (Mode B)
    router: Any = None  # forge.llm.router.LLMRouter, for tools that run subagents
    sensitive_terms: tuple[str, ...] = ()  # Mode B: host-identifying words that must never reach a web search
    hosted_search: Callable[[str], Awaitable[tuple[str, list[dict[str, str]]]]] | None = None  # azure search
    interaction: Any = None  # the orchestrator (tools/interaction.Interaction), when orchestrated
    # Chat sessions: asks the user through the host's question channel (clickable options + a text box).
    ask_user: Callable[[str, str, list[Any], str | None], Awaitable[str]] | None = None
    user_github_repos: Callable[[], set[str]] | None = (
        None  # 'owner/repo' links in the user's own messages (D-237)
    )
    user_urls: Callable[[], set[str]] | None = (
        None  # web addresses the user typed in their own messages (D-349)
    )
    skills_changed: Callable[[], None] | None = None  # tells the host to re-read the installed skills
    end_turn: bool = False  # a phase tool finished its phase: the agent loop stops after this step
    step: int = 0  # increases with every tool call; used for 'no claim without evidence'
    last_edit_step: int = 0
    last_code_edit_step: int = 0  # the last change to something that has behaviour to test: not a page, a stylesheet, a note or a picture (D-379)
    last_verified_step: int = 0
    require_baseline: bool = False  # a real session asks for a test run before the first edit of existing code (set by the session host, D-408)
    tests_pinned: bool = False  # a test file was written in this session (D-410)
    rewrite_asked: bool = False  # the one reminder about replacing most of a file in one step was given
    baseline_checked: bool = False  # a test ran, a test file was written, or the first-edit reminder was given (tools/baseline_gate.py, D-408)
    todos: list[dict[str, str]] = field(default_factory=list)  # the model's own todo list (D-177)
    pin: Callable[[str, str | None], None] | None = None  # sets a pinned-context slot (set by the host)
    write_only_under: str | None = (
        None  # a subagent that may write only below this folder (the verifier, a builder)
    )
    design_first: bool = (
        True  # D4: the first page or style file of a project waits for a DESIGN.md (the design concept)
    )
    design_md_written: bool = (
        False  # the model wrote the project DESIGN.md itself (not imported from the user) (D-352)
    )
    design_candidates_refusals: int = (
        0  # how many times a page was refused until candidates were compared (D-352)
    )
    design_similar_refusals: int = 0
    design_gate_rounds: int = 0  # how many times that was asked for in this session
    write_only_is_builder: bool = (
        False  # selects the wording of the refusal (builders build, verifiers only verify)
    )
    last_ui_edit_step: int = 0  # a template/stylesheet/script that changes what the user sees (D-167)
    last_browser_step: int = 0  # the app was last used in a browser (browser_* tool or a Playwright run)
    last_screenshot_step: int = 0  # the page was last screenshotted with the style audit (D-245)
    last_critic_step: int = 0  # the design critic last reviewed the page (D-249)
    critic_ship: bool = False  # and its verdict was SHIP
    last_review_step: int = 0  # the two-axis code review last ran (C4, D-308)
    review_ship: bool = False  # and its verdict was SHIP
    critic_rounds: int = (
        0  # REVISE verdicts in a row; after three the model may finish with the open points listed
    )
    ui_audit_blocked: bool = False  # that audit found a blocker (e.g. the CSS framework produces no styles)
    reads: ReadTracker = field(default_factory=ReadTracker)
    publish: PublishCallback | None = None  # engine event publisher (file diffs, etc.)
    tool_cap_tokens: int = DEFAULT_TOOL_CAP_TOKENS
    edit_counts: dict[str, int] = field(
        default_factory=dict
    )  # how often each UI file was changed in this run (D1)
    shell_cap_tokens: int = DEFAULT_SHELL_CAP_TOKENS

    def note_edit(self, *relatives: str) -> None:
        """Remembers that files were changed, and whether any of them is code: a task that only changed a page, a stylesheet or a note has no test to run (D-379)."""
        self.last_edit_step = self.step
        if any(not relative.lower().endswith(STATIC_SUFFIXES) for relative in relatives):
            self.last_code_edit_step = self.step

    async def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.publish is not None:
            await self.publish(event_type, payload)

    async def ask_model(self, role: str, request: Any, what: str, beat_s: float = 4.0) -> Any:
        """A model call made by a tool (a picture question, a judge, a review): while it runs the activity line says what is being asked and for
        how long, so a slow answer never looks like a frozen tool (D-367). Returns the router's response."""
        started = time.monotonic()

        async def beat() -> None:
            while True:
                await asyncio.sleep(beat_s)
                seconds = round(time.monotonic() - started)
                await self.emit(
                    "tool_progress",
                    {
                        "source": "model",
                        "name": role,
                        "line": f"asking the {role} model: {what} ({seconds} s)",
                        "percent": None,
                        "stalled_s": None,
                        "lines": 0,
                        "elapsed_s": seconds,
                    },
                )

        task = asyncio.create_task(beat())
        try:
            return await self.router.chat(role, request)
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

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
        """True when the call only touches files DebCraft created in this workspace (none of the user's), so an
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

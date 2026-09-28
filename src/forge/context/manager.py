"""Keeps every model request inside the context window (spec §10).

Before each call `prepare()`:
  1. micro-compacts (old tool outputs -> stubs) once history passes micro_compact_at of its budget;
  2. summarises older turns once it passes auto_compact_at (summary goes into the pinned block);
  3. guarantees the request fits: emergency trim, then progressively harder trimming.
The working history is compacted in place (D-052); the full record stays in the event log and in
.forge/compactions/.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from forge.config import ForgeConfig
from forge.context.budget import Breakdown, ContextBudget
from forge.context.compaction import (
    chunk_transcript,
    emergency_trim,
    latest_user_index,
    micro_compact,
    split_for_summary,
    step_starts,
    summary_is_valid,
    summary_prompt,
)
from forge.context.pinned import PinnedBlocks
from forge.llm.base import ChatRequest, Message, ToolSpec, Usage
from forge.llm.router import LLMRouter
from forge.llm.tokens import count_request_tokens, count_text_tokens

Summariser = Callable[[str], Awaitable[str]]
EventCallback = Callable[[str, dict[str, Any]], Awaitable[None]]
SUMMARY_MAX_OUTPUT = 4000
CHUNK_SHARE_OF_SUMMARISER_WINDOW = 0.5


class ContextManager:
    def __init__(
        self,
        router: LLMRouter,
        config: ForgeConfig,
        compactions_dir: Path | None = None,
        summarise: Summariser | None = None,
        on_event: EventCallback | None = None,
        files_modified: Callable[[], list[str]] | None = None,
    ) -> None:
        self.router = router
        self.config = config
        self.compactions_dir = compactions_dir
        self.pinned = PinnedBlocks()
        self.compactions = 0
        self._summarise = summarise or self._summarise_with_llm
        self._on_event = on_event
        self._files_modified = files_modified
        self._budgets: dict[str, ContextBudget] = {}
        self._last_raw_estimate = 0
        self._steps_at_last_compaction = 0

    # --- budget ---

    def budget(self) -> ContextBudget:
        model_key = self.router.model_for_role("coder")
        if model_key not in self._budgets:
            self._budgets[model_key] = ContextBudget(self.config.llm.models[model_key], self.config.context)
        return self._budgets[model_key]

    def assemble(self, history: list[Message]) -> list[Message]:
        """What is actually sent: the history plus the pinned block at the end (keeps the cached
        prefix of the conversation stable, D-053)."""
        pinned = self.pinned.message(self.budget().pinned_cap)
        return [*history, pinned] if pinned else list(history)

    def breakdown(self, history: list[Message], tools: list[ToolSpec]) -> Breakdown:
        budget = self.budget()
        pinned = self.pinned.message(budget.pinned_cap)
        return Breakdown(
            usable=budget.usable,
            fixed=budget.estimate_messages(history[:1]) + budget.estimate_tools(tools),
            pinned=budget.estimate_messages([pinned]) if pinned else 0,
            history=budget.estimate_messages(history[1:]),
        )

    # --- before and after each call ---

    async def prepare(self, history: list[Message], tools: list[ToolSpec]) -> list[Message]:
        self._refresh_pinned()
        budget = self.budget()
        settings = self.config.context
        stubbed = 0
        keep = settings.keep_recent_tool_results
        # Only outputs from earlier user turns are stubbed (D-055): stubbing what the current task still
        # needs makes the model re-read it and thrash. Inside the current turn, the summary below
        # recovers space while keeping the findings.
        current_turn = latest_user_index(history)
        while keep >= 1 and self._history_share(history, tools) >= settings.micro_compact_at:
            stubbed += micro_compact(history, keep, before=current_turn)
            keep //= 2
        if stubbed:
            await self._emit(
                "notice", {"kind": "micro_compaction", "text": f"Trimmed {stubbed} old tool outputs."}
            )
        if self._history_share(history, tools) >= settings.auto_compact_at and self._steps_since_compaction(
            history
        ):
            await self.compact(history)
        messages = self.assemble(history)
        if budget.estimate(messages, tools) > budget.usable:
            self.force_fit(history, tools)
            messages = self.assemble(history)
        self._last_raw_estimate = count_request_tokens(messages, tools)
        return messages

    def record_usage(self, usage: Usage) -> None:
        self.budget().calibrate(self._last_raw_estimate, usage.input_tokens)

    def _steps_since_compaction(self, history: list[Message]) -> bool:
        """Cooldown (D-055): summarise again only after keep_recent_turns new steps. Otherwise a history
        that stays near the threshold would trigger a (paid, slow) summary on every single call; the hard
        fit guarantee still protects the budget in between."""
        new_steps = len(step_starts(history)) - self._steps_at_last_compaction
        return self.compactions == 0 or new_steps >= self.config.context.keep_recent_turns

    def _history_share(self, history: list[Message], tools: list[ToolSpec]) -> float:
        parts = self.breakdown(history, tools)
        available = max(1, parts.usable - parts.fixed - parts.pinned)
        return parts.history / available

    # --- compaction ---

    async def compact(self, history: list[Message], focus: str | None = None) -> bool:
        """Summarises all but the most recent turns. False if there was nothing to compact or the
        summary failed validation twice (then more history is kept verbatim instead)."""
        older, recent = split_for_summary(history, self.config.context.keep_recent_turns)
        if not older and focus:  # /compact asked explicitly: keep only the latest turn verbatim
            older, recent = split_for_summary(history, 1)
        if not older:
            return False
        await self._emit(
            "notice", {"kind": "compacting", "text": "Summarising earlier conversation to save context…"}
        )
        summary = await self._summary_for(older, focus)
        if summary is None:
            await self._emit(
                "notice",
                {
                    "kind": "compaction_failed",
                    "text": "The summary was incomplete twice; keeping the history as it is.",
                },
            )
            return False
        history[:] = [history[0], *recent]
        self.pinned.set("compaction_summary", summary)
        self.compactions += 1
        self._steps_at_last_compaction = len(step_starts(history))
        self._save_summary(summary)
        await self._emit(
            "notice",
            {"kind": "compacted", "text": f"Compacted earlier conversation ({len(older)} messages)."},
        )
        return True

    async def _summary_for(self, older: list[Message], focus: str | None) -> str | None:
        summariser_model = self.config.llm.models[self.router.model_for_role("summariser")]
        chunk_tokens = int(summariser_model.context_window * CHUNK_SHARE_OF_SUMMARISER_WINDOW)
        summary = self.pinned.get("compaction_summary")
        for chunk in chunk_transcript(older, chunk_tokens):
            prompt = summary_prompt(chunk, summary, focus)
            candidate = await self._summarise(prompt)
            if not summary_is_valid(candidate):
                candidate = await self._summarise(
                    prompt + "\n\nInclude EVERY heading listed above, exactly as written."
                )
            if not summary_is_valid(candidate):
                return None
            summary = candidate
        return summary

    async def _summarise_with_llm(self, prompt: str) -> str:
        response = await self.router.chat(
            "summariser", ChatRequest(messages=[Message.user(prompt)], max_output_tokens=SUMMARY_MAX_OUTPUT)
        )
        return response.text

    async def emergency(self, history: list[Message]) -> None:
        """After a context-length error from the provider (spec §10.4 tier 3)."""
        history[:] = emergency_trim(history)
        await self._emit(
            "notice",
            {
                "kind": "emergency_compaction",
                "text": "The request was too large; kept only the last two turns.",
            },
        )

    def force_fit(self, history: list[Message], tools: list[ToolSpec]) -> None:
        """Last resort so no request ever exceeds the usable budget (spec §10.7)."""
        budget = self.budget()

        def fits() -> bool:
            return budget.estimate(self.assemble(history), tools) <= budget.usable

        if fits():
            return
        history[:] = emergency_trim(history)
        micro_compact(history, keep_recent=0)
        while not fits():
            steps = [i for i in step_starts(history) if history[i].role == "assistant"]
            if len(steps) < 2:
                break
            del history[steps[0] : steps[1]]  # drop the oldest whole step: pairs stay intact
        while not fits():
            largest = max(
                range(1, len(history)), key=lambda i: count_text_tokens(history[i].content), default=None
            )
            if largest is None or len(history[largest].content) < 200:
                break
            content = history[largest].content
            history[largest] = history[largest].model_copy(
                update={"content": content[: len(content) // 2] + "\n[… cut to fit the context window]"}
            )

    def reset_for_task(self, history: list[Message], brief: str, handoff_note: str | None = None) -> None:
        """Task-scoped reset (spec §10.6): pinned + task brief + previous task's handoff note."""
        text = brief if not handoff_note else f"{brief}\n\nHandoff from the previous task:\n{handoff_note}"
        history[:] = [history[0], Message.user(text)]

    def clear(self, history: list[Message]) -> None:
        history[:] = history[:1]
        self.pinned.set("compaction_summary", None)

    # --- helpers ---

    def _refresh_pinned(self) -> None:
        if self._files_modified is not None:
            paths = self._files_modified()
            self.pinned.set("files_modified", "\n".join(paths) if paths else None)

    def _save_summary(self, summary: str) -> None:
        if self.compactions_dir is None:
            return
        self.compactions_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        (self.compactions_dir / f"{self.compactions:04d}-{stamp}.md").write_text(summary, encoding="utf-8")

    async def _emit(self, kind: str, payload: dict[str, Any]) -> None:
        if self._on_event is not None:
            await self._on_event(kind, payload)

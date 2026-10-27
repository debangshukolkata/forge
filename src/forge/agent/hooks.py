"""Hooks around tool calls and the session (TODO plugins step 4, D-501; docs/DESIGN_PLUGINS_MCP_LSP.md section 1).

Events: `pre_tool`, `post_tool`, `session_start`, `session_end`, `user_message` (config.yaml `hooks.*`, and hooks a plugin brings). A hook is a shell
command, or `{match: <tool name pattern>, command: ...}` to limit it to some tools. Rules that keep it safe:
- A hook command goes through the same permission gate and sandbox as a command the model runs. A hook the gate would ask about is NOT run and nobody is
  asked: a hook cannot approve anything. A hook the gate denies is not run either.
- A `pre_tool` hook may only DENY: a failing exit code blocks the tool call and its output is the reason. It can never allow a call the gate refused.
- Only `{tool}` and `{file}` are filled into a command, quoted; the user's message or a tool's output is never put into a command line.
- Hook output is untrusted text: capped, shown to the model with the injection check, redacted with every event."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from typing import Any

from forge.config import HookRule
from forge.protocol.events import EventBus, EventType
from forge.safety.injection import flag
from forge.safety.permissions import PermissionGate
from forge.toolkit.base import ToolContext
from forge.toolkit.powershell import ps_quote
from forge.toolkit.shell import execute

HOOK_TIMEOUT_S = 120
OUTPUT_CHARS = 1500
EVENTS = ("pre_tool", "post_tool", "session_start", "session_end", "user_message")


@dataclass
class HookOutcome:
    command: str
    ran: bool  # False: the gate would not run it without asking, or denied it
    ok: bool
    output: str

    def note(self, event: str) -> str:
        if not self.ran:
            return f"[{event} hook not run: {self.output}]"
        text, _ = flag(self.output)
        return f"[{event} hook: {self.command} -> {'ok' if self.ok else 'FAILED'}]\n{text}"


class HookRunner:
    def __init__(
        self,
        rules: dict[str, list[str | HookRule | dict[str, Any]]],
        context: ToolContext,
        gate: PermissionGate,
        bus: EventBus,
    ) -> None:
        self.rules = rules
        self.context = context
        self.gate = gate
        self.bus = bus

    def has(self, event: str) -> bool:
        return bool(self.rules.get(event)) and self.context.shell is not None

    def _commands(self, event: str, tool: str, file: str) -> list[str]:
        out: list[str] = []
        for rule in self.rules.get(event, []):
            if isinstance(rule, dict):  # a plugin's hooks.json entry
                pattern, template = str(rule.get("match", "*")), str(rule["command"])
            elif isinstance(rule, str):
                pattern, template = "*", rule
            else:
                pattern, template = rule.match, rule.command
            if event in ("pre_tool", "post_tool") and not fnmatch.fnmatch(tool, pattern):
                continue
            out.append(template.replace("{tool}", ps_quote(tool)).replace("{file}", ps_quote(file)))
        return out

    async def run(self, event: str, tool: str = "", file: str = "") -> list[HookOutcome]:
        shell = self.context.shell
        if shell is None:
            return []
        outcomes: list[HookOutcome] = []
        for command in self._commands(event, tool, file):
            decision = self.gate.decide("run_command", False, command, shell.scope())
            if decision.verdict != "allow":
                reason = f"the permission gate would {decision.verdict} it ({decision.reason}); a hook cannot approve anything"
                outcomes.append(HookOutcome(command, False, True, reason))
            else:
                result = await execute(self.context, command, HOOK_TIMEOUT_S, ".")
                outcomes.append(HookOutcome(command, True, result.ok, result.content[-OUTPUT_CHARS:]))
            last = outcomes[-1]
            await self.bus.publish(
                EventType.NOTICE,
                {
                    "kind": "hook",
                    "text": f"{event} hook {'ran' if last.ran else 'skipped'}: {command}"
                    + ("" if last.ok else " (failed)"),
                },
            )
        return outcomes

    @staticmethod
    def blocked_by(outcomes: list[HookOutcome]) -> HookOutcome | None:
        """The first pre_tool hook that ran and failed: it denies the call."""
        return next((o for o in outcomes if o.ran and not o.ok), None)

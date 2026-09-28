"""Permission gate (spec §14.2): decides allow / ask / deny for every tool call.

Modes:
  plan    - read-only tools only.
  default - file edits in the workspace are applied (shown as diffs); shell commands that are not
            clearly safe ask; the always-ask list always asks.
  auto    - everything inside the workspace runs without asking, except the always-ask list.
Always ask: deleting files, pip installs, network access, anything outside the workspace, nested
shells. Blocked commands never run in any mode.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from forge.safety.shell_classifier import Classification, ShellScope, classify

PermissionMode = Literal["plan", "default", "auto"]
Verdict = Literal["allow", "ask", "deny"]
SHELL_TOOLS = {"run_command", "python_run", "start_background"}
ALWAYS_ASK_TOOLS = {"delete_file"}
PREFIX_WORDS = 3  # "always allow" remembers this many leading words of a command


@dataclass
class Decision:
    verdict: Verdict
    reason: str
    always_ask: bool = False
    command_prefix: str | None = None  # offered to the user for "always allow this prefix"


class PermissionGate:
    def __init__(self, mode: PermissionMode, rules_file: Path) -> None:
        self.mode: PermissionMode = mode
        self._rules_file = rules_file

    def decide(
        self,
        tool_name: str,
        read_only: bool,
        command: str | None,
        scope: ShellScope | None,
        own_files_only: bool = False,
    ) -> Decision:
        if read_only:
            return Decision("allow", "read-only")
        if self.mode == "plan":
            return Decision("deny", "plan mode allows read-only tools only; ask the user to leave plan mode")
        if tool_name in ALWAYS_ASK_TOOLS and not own_files_only:
            return Decision("ask", "deleting your files always needs approval", always_ask=True)
        if tool_name in ALWAYS_ASK_TOOLS:
            if self.mode == "auto":
                return Decision("allow", "auto mode: a file Forge created in this workspace")
            return Decision("ask", "deletes a file Forge created in this workspace")
        if tool_name.startswith("mcp__"):  # an external tool server: it can do anything (spec §13B)
            if self.mode == "auto":
                return Decision("allow", "auto mode: MCP tool")
            return Decision("ask", "an MCP server tool (outside Forge)")
        if tool_name not in SHELL_TOOLS or command is None or scope is None:
            return Decision("allow", "workspace edit")
        return self._decide_command(command, scope)

    def _decide_command(self, command: str, scope: ShellScope) -> Decision:
        result: Classification = classify(command, scope)
        reason = "; ".join(result.reasons) or "allowlisted"
        prefix = command_prefix(command)
        if result.level == "blocked":
            return Decision("deny", f"blocked: {reason}")
        if result.level == "safe":
            return Decision("allow", reason)
        if result.always_ask:
            return Decision("ask", reason, always_ask=True, command_prefix=None)
        if self.mode == "auto":
            return Decision("allow", f"auto mode: {reason}")
        if prefix in self.allowed_prefixes():
            return Decision("allow", f"you always allow '{prefix}'")
        return Decision("ask", reason, command_prefix=prefix)

    def allowed_prefixes(self) -> list[str]:
        if not self._rules_file.exists():
            return []
        data = json.loads(self._rules_file.read_text(encoding="utf-8"))
        return [str(prefix) for prefix in data.get("allowed_prefixes", [])]

    def allow_prefix(self, prefix: str) -> None:
        prefixes = sorted(set(self.allowed_prefixes()) | {prefix})
        self._rules_file.parent.mkdir(parents=True, exist_ok=True)
        self._rules_file.write_text(json.dumps({"allowed_prefixes": prefixes}, indent=1), encoding="utf-8")


def command_prefix(command: str) -> str:
    return " ".join(command.strip().split()[:PREFIX_WORDS])

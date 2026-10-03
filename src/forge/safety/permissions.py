"""Permission gate (spec §14.2): decides allow / ask / deny for every tool call.

Modes:
  plan    - read-only tools only.
  default - file edits in the workspace are applied (shown as diffs); shell commands that are not
            clearly safe ask; the always-ask list always asks.
  auto    - everything inside the workspace runs without asking, except the always-ask list.
Always ask: deleting files, pip installs, network access, anything outside the workspace, nested
shells. Blocked commands never run in any mode.

Settings rules (D-183) from the user's settings.json add `deny` and `allow` patterns on top: a deny rule
always wins; an allow rule only turns an "ask" into "allow" and can never lift a block, the always-ask list
or plan mode.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Literal

from forge.errors import ConfigError
from forge.safety.shell_classifier import Classification, ShellScope, classify

PermissionMode = Literal["plan", "default", "auto"]
Verdict = Literal["allow", "ask", "deny"]
SHELL_TOOLS = {"run_command", "python_run", "start_background"}
ALWAYS_ASK_TOOLS = {"delete_file"}
PREFIX_WORDS = 3  # "always allow" remembers this many leading words of a command


RULE_SHAPE = re.compile(r"^([\w*.-]+)(?:\((.+)\))?$")
SHELL_OPERATORS = re.compile(r"[;&|\n`<>]|\$\(")


@dataclass(frozen=True)
class Rule:
    text: str
    tool: str
    pattern: str | None

    @classmethod
    def parse(cls, text: str) -> Rule:
        match = RULE_SHAPE.match(text.strip())
        if match is None:
            raise ConfigError(f"Permission rule {text!r} is not 'tool' or 'tool(pattern)'.")
        return cls(text.strip(), match.group(1), match.group(2))

    def matches(self, tool_name: str, command: str | None, *, for_deny: bool) -> bool:
        if not fnmatchcase(tool_name, self.tool):
            return False
        if self.pattern is None:
            return True
        if command is None:
            return False
        normalised = " ".join(command.split())
        if for_deny:
            # `cd x && git push` must still hit a deny rule on `git push`.
            segments = [" ".join(part.split()) for part in re.split(r"[;&|\n`]+|\$\(", command)]
            return any(fnmatchcase(segment, self.pattern) for segment in [normalised, *segments])
        # An allow rule never covers a chained or redirected command: `pytest && curl ...` is not `pytest`.
        return SHELL_OPERATORS.search(normalised) is None and fnmatchcase(normalised, self.pattern)


@dataclass(frozen=True)
class PermissionRules:
    allow: tuple[Rule, ...] = field(default_factory=tuple)
    deny: tuple[Rule, ...] = field(default_factory=tuple)

    @classmethod
    def load(cls, settings_file: Path) -> PermissionRules:
        """The `permissions` section of settings.json. A broken file raises: silently dropping a deny rule
        would be worse than refusing to start."""
        if not settings_file.exists():
            return cls()
        try:
            data = json.loads(settings_file.read_text(encoding="utf-8-sig"))
            section = data.get("permissions", {}) if isinstance(data, dict) else None
            if not isinstance(section, dict):
                raise ValueError("expected a JSON object with an optional 'permissions' object")
            lists = {name: section.get(name, []) for name in ("allow", "deny")}
            if not all(isinstance(v, list) and all(isinstance(r, str) for r in v) for v in lists.values()):
                raise ValueError("'allow' and 'deny' must be lists of strings")
        except (ValueError, OSError) as error:
            raise ConfigError(f"Cannot read {settings_file}: {error}") from error
        return cls(
            allow=tuple(Rule.parse(r) for r in lists["allow"]),
            deny=tuple(Rule.parse(r) for r in lists["deny"]),
        )

    def denied_by(self, tool_name: str, command: str | None) -> Rule | None:
        return next((r for r in self.deny if r.matches(tool_name, command, for_deny=True)), None)

    def allowed_by(self, tool_name: str, command: str | None) -> Rule | None:
        return next((r for r in self.allow if r.matches(tool_name, command, for_deny=False)), None)


@dataclass
class Decision:
    verdict: Verdict
    reason: str
    always_ask: bool = False
    command_prefix: str | None = None  # offered to the user for "always allow this prefix"


class PermissionGate:
    def __init__(self, mode: PermissionMode, rules_file: Path, rules: PermissionRules | None = None) -> None:
        self.mode: PermissionMode = mode
        self._rules_file = rules_file
        self.rules = rules or PermissionRules()

    def decide(
        self,
        tool_name: str,
        read_only: bool,
        command: str | None,
        scope: ShellScope | None,
        own_files_only: bool = False,
    ) -> Decision:
        denied = self.rules.denied_by(tool_name, command)
        if denied is not None:
            return Decision("deny", f"denied by your settings rule '{denied.text}'")
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
            allowed = self.rules.allowed_by(tool_name, command)
            if allowed is not None:
                return Decision("allow", f"your settings allow '{allowed.text}'")
            return Decision("ask", "an MCP server tool (outside Forge)")
        if tool_name not in SHELL_TOOLS or command is None or scope is None:
            return Decision("allow", "workspace edit")
        return self._decide_command(tool_name, command, scope)

    def _decide_command(self, tool_name: str, command: str, scope: ShellScope) -> Decision:
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
        allowed = self.rules.allowed_by(tool_name, command)
        if allowed is not None:
            return Decision("allow", f"your settings allow '{allowed.text}'")
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

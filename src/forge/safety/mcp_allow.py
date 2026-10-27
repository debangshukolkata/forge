"""Per-project MCP allow-list (D-499, design section 2 option B).

An MCP server is a process DebCraft does not control. A server named in `config.yaml` (`mcp.servers`) therefore starts
only when the user's own `<home>/settings.json` also lists it for this project, and only the tools listed there are
shown to the model:

    {"mcp_allow": {"<project scope>": {"<server>": {"tools": ["tool_a", "tool_b"]}}}}   ("tools": "*" = all)

The scope key is the memory scope of the project (`repo:<slug>-<hash>` in Mode A, `profile:<name>` in Mode B).
A project with no entry allows nothing. Like the permission rules, only the user's file counts: a folder the model can
write to must never be able to grant itself a server. A broken file raises, so the caller starts no server at all.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from forge.errors import ConfigError

SETTINGS_KEY = "mcp_allow"


@dataclass(frozen=True)
class ServerAllowance:
    """`tools` is None when every tool of the server is allowed."""

    tools: frozenset[str] | None = None

    def permits(self, tool_name: str) -> bool:
        return self.tools is None or tool_name in self.tools


@dataclass(frozen=True)
class McpAllowList:
    servers: dict[str, ServerAllowance] = field(default_factory=dict)

    def for_server(self, name: str) -> ServerAllowance | None:
        return self.servers.get(name)

    @classmethod
    def load(cls, settings_file: Path, scope: str) -> McpAllowList:
        section = _read_section(settings_file)
        entry = section.get(scope, {})
        if not isinstance(entry, dict):
            raise ConfigError(f"{settings_file}: '{SETTINGS_KEY}' entry for {scope!r} must be an object")
        return cls({name: _parse_allowance(settings_file, name, value) for name, value in entry.items()})


def scopes_with_entries(settings_file: Path) -> dict[str, list[str]]:
    """scope -> allowed server names, for `forge doctor`."""
    return {
        scope: sorted(entry)
        for scope, entry in _read_section(settings_file).items()
        if isinstance(entry, dict)
    }


def _read_section(settings_file: Path) -> dict[str, Any]:
    if not settings_file.exists():
        return {}
    try:
        data = json.loads(settings_file.read_text(encoding="utf-8-sig"))
    except (ValueError, OSError) as error:
        raise ConfigError(f"Cannot read {settings_file}: {error}") from error
    section = data.get(SETTINGS_KEY, {}) if isinstance(data, dict) else None
    if not isinstance(section, dict):
        raise ConfigError(f"{settings_file}: expected a JSON object with an optional '{SETTINGS_KEY}' object")
    return section


def _parse_allowance(settings_file: Path, server: str, value: Any) -> ServerAllowance:
    tools = value.get("tools") if isinstance(value, dict) else None
    if tools == "*":
        return ServerAllowance(None)
    if isinstance(tools, list) and all(isinstance(t, str) for t in tools):
        return ServerAllowance(frozenset(tools))
    raise ConfigError(
        f'{settings_file}: {SETTINGS_KEY} server {server!r} needs "tools": "*" or a list of names'
    )

"""Plugins as folders (TODO plugins step 3, D-501; docs/DESIGN_PLUGINS_MCP_LSP.md section 1).

A plugin is a folder `<home>/plugins/<name>/` with a `plugin.json` (name, version, description) and any of `commands/*.md`, `agents/*.md`, `skills/<name>/SKILL.md`
and `hooks.json` (the same events as config.yaml `hooks`). Rules:
- A plugin is OFF until the user enables it (`forge plugin enable <name>`, stored in `<home>/settings.json` under `plugins.enabled`); `forge plugin show <name>` lists
  exactly what it adds first. Nothing enables a plugin by itself, and the model has no tool for it.
- Plugins load only from DebCraft Home. A folder inside a workspace (Mode A or B) is never read as a plugin.
- A plugin cannot add MCP servers (servers are the user's own decision, D-499) and cannot change permission rules; its hooks run through the permission gate like any
  other hook (agent/hooks.py).
- User files win: a command or agent of the same name in the user's own folders replaces the plugin's one."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from forge.errors import ConfigError

NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,48}$")
HOOK_EVENTS = ("pre_tool", "post_tool", "session_start", "session_end", "user_message", "stop")


@dataclass
class Plugin:
    name: str
    folder: Path
    version: str = ""
    description: str = ""
    enabled: bool = False
    commands: list[str] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    hooks: dict[str, list[Any]] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)

    def adds(self) -> str:
        """What enabling it brings, in the words the user sees before they enable it."""
        lines = [
            f"{self.name} {self.version}".strip() + (f": {self.description}" if self.description else "")
        ]
        if self.commands:
            lines.append("  slash commands: " + ", ".join("/" + c for c in self.commands))
        if self.agents:
            lines.append("  agents: " + ", ".join(self.agents))
        if self.skills:
            lines.append("  skills: " + ", ".join(self.skills))
        for event, rules in self.hooks.items():
            for rule in rules:
                lines.append(
                    f"  hook {event}: {rule if isinstance(rule, str) else rule.get('command', rule)}"
                )
        if len(lines) == 1:
            lines.append("  (adds nothing)")
        lines.extend(f"  problem: {p}" for p in self.problems)
        return "\n".join(lines)


def plugins_root(home: Path) -> Path:
    return home / "plugins"


def _settings(home: Path) -> dict[str, Any]:
    path = home / "settings.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, OSError) as error:
        raise ConfigError(f"Cannot read {path}: {error}") from error
    if not isinstance(data, dict):
        raise ConfigError(f"Cannot read {path}: expected a JSON object")
    return data


def enabled_names(home: Path) -> list[str]:
    section = _settings(home).get("plugins", {})
    names = section.get("enabled", []) if isinstance(section, dict) else []
    return [n for n in names if isinstance(n, str) and NAME.match(n)] if isinstance(names, list) else []


def _read_hooks(folder: Path, problems: list[str]) -> dict[str, list[Any]]:
    path = folder / "hooks.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, OSError) as error:
        problems.append(f"hooks.json unreadable: {error}")
        return {}
    hooks: dict[str, list[Any]] = {}
    for event, rules in data.items() if isinstance(data, dict) else []:
        if event not in HOOK_EVENTS or not isinstance(rules, list):
            problems.append(f"hooks.json: ignored '{event}'")
            continue
        kept = [
            r
            for r in rules
            if isinstance(r, str) or (isinstance(r, dict) and isinstance(r.get("command"), str))
        ]
        if kept:
            hooks[event] = kept
    return hooks


def load_plugin(folder: Path, enabled: set[str]) -> Plugin | None:
    if not NAME.match(folder.name) or not folder.is_dir():
        return None
    problems: list[str] = []
    meta: dict[str, Any] = {}
    manifest = folder / "plugin.json"
    if manifest.is_file():
        try:
            loaded = json.loads(manifest.read_text(encoding="utf-8-sig"))
            meta = loaded if isinstance(loaded, dict) else {}
        except (ValueError, OSError) as error:
            problems.append(f"plugin.json unreadable: {error}")
    else:
        problems.append("no plugin.json")
    if isinstance(meta.get("mcp"), dict | list) or "mcp_servers" in meta:
        problems.append("a plugin cannot add MCP servers; the entry is ignored (add servers in config.yaml)")
    return Plugin(
        name=folder.name,
        folder=folder,
        version=str(meta.get("version", "")),
        description=str(meta.get("description", ""))[:200],
        enabled=folder.name in enabled,
        commands=sorted(p.stem for p in (folder / "commands").glob("*.md"))
        if (folder / "commands").is_dir()
        else [],
        agents=sorted(p.stem for p in (folder / "agents").glob("*.md"))
        if (folder / "agents").is_dir()
        else [],
        skills=sorted(p.parent.name for p in (folder / "skills").glob("*/SKILL.md"))
        if (folder / "skills").is_dir()
        else [],
        hooks=_read_hooks(folder, problems),
        problems=problems,
    )


def list_plugins(home: Path) -> list[Plugin]:
    root = plugins_root(home)
    if not root.is_dir():
        return []
    enabled = set(enabled_names(home))
    found = (load_plugin(folder, enabled) for folder in sorted(root.iterdir()))
    return [plugin for plugin in found if plugin is not None]


def enabled_plugins(home: Path) -> list[Plugin]:
    return [plugin for plugin in list_plugins(home) if plugin.enabled]


def set_enabled(home: Path, name: str, on: bool) -> bool:
    """Turns a plugin on or off in settings.json, keeping everything else in the file. False when there is no such plugin."""
    if not any(p.name == name for p in list_plugins(home)):
        return False
    data = _settings(home)
    section = data.get("plugins")
    section = section if isinstance(section, dict) else {}
    names = [n for n in enabled_names(home) if n != name]
    if on:
        names.append(name)
    section["enabled"] = sorted(names)
    data["plugins"] = section
    (home / "settings.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return True


def plugin_skill_roots(home: Path) -> list[Path]:
    return [p.folder / "skills" for p in enabled_plugins(home) if p.skills]


def plugin_command_folders(home: Path) -> list[Path]:
    return [p.folder / "commands" for p in enabled_plugins(home) if p.commands]


def plugin_agent_folders(home: Path) -> list[Path]:
    return [p.folder / "agents" for p in enabled_plugins(home) if p.agents]


def plugin_hooks(home: Path) -> dict[str, list[Any]]:
    merged: dict[str, list[Any]] = {}
    for plugin in enabled_plugins(home):
        for event, rules in plugin.hooks.items():
            merged.setdefault(event, []).extend(rules)
    return merged

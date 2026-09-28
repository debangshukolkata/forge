"""Custom subagents (spec §13B): <forge_home>/agents/<name>.md — frontmatter lists the allowed tools, the role
(whose model runs it) and the reasoning effort; the body is its system prompt. Spawned by name with
spawn_subagent, like the built-in types (explore, reviewer, debugger). Subagents never get tools that write
unless the file lists them, and never escalate or talk to the user: they return a report."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.S)
_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,40}$")


@dataclass
class AgentDefinition:
    name: str
    prompt: str
    tools: list[str] = field(default_factory=list)  # tool names; empty = the read-only tools
    role: str = "coder"
    effort: str | None = None
    description: str = ""


def load_agents(home: Path) -> dict[str, AgentDefinition]:
    folder = home / "agents"
    agents: dict[str, AgentDefinition] = {}
    if not folder.is_dir():
        return agents
    for path in sorted(folder.glob("*.md")):
        if not _NAME.match(path.stem):
            continue
        text = path.read_text(encoding="utf-8")
        match = FRONT.match(text)
        meta: dict[str, str] = dict(re.findall(r"^(\w+):\s*(.+)$", match.group(1), re.M)) if match else {}
        body = (match.group(2) if match else text).strip()
        tools = [t.strip() for t in re.split(r"[,\s\[\]]+", meta.get("tools", "")) if t.strip()]
        agents[path.stem] = AgentDefinition(
            name=path.stem,
            prompt=body,
            tools=tools,
            role=meta.get("model", meta.get("role", "coder")).strip(),
            effort=meta.get("effort", "").strip() or None,
            description=meta.get("description", "").strip(),
        )
    return agents

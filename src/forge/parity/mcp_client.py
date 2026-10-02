"""Optional MCP client (spec §13B): connect to MCP servers listed in config (stdio), e.g. an internal
Jira/Confluence/DB tool server. Their tools appear as `mcp__<server>__<tool>`, always go through the
permission gate (they ask first, except in auto mode), and their output is capped and redacted like any
tool result.
Disabled by default; needs the `mcp` package (pip install mcp)."""

from __future__ import annotations

import contextlib
import re
from typing import Any, ClassVar

from pydantic import ConfigDict

from forge.llm.base import ToolSpec
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult, inline_schema

PREFIX = "mcp__"
CALL_TIMEOUT_S = 120


class _AnyArgs(ToolArgs):
    model_config = ConfigDict(extra="allow")


class McpHub:
    """One session per configured server, kept open for the whole Forge session."""

    def __init__(self, servers: dict[str, Any], secrets: Any = None) -> None:
        self.servers = servers
        self.secrets = secrets
        self.sessions: dict[str, Any] = {}
        self.tools: list[Tool] = []
        self.errors: dict[str, str] = {}
        self._stack = contextlib.AsyncExitStack()

    async def start(self) -> list[Tool]:
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:
            self.errors["*"] = "the mcp package is not installed (pip install mcp)"
            return []
        for name, server in self.servers.items():
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", name):
                self.errors[name] = "server names use letters, digits, _ and -"
                continue
            env = {key: self.secrets.get(key) or "" for key in server.env_names} if self.secrets else None
            params = StdioServerParameters(
                command=server.command, args=list(server.args), env=env, cwd=server.cwd
            )
            try:
                read, write = await self._stack.enter_async_context(stdio_client(params))
                session = await self._stack.enter_async_context(
                    ClientSession(read, write, read_timeout_seconds=CALL_TIMEOUT_S)
                )
                await session.initialize()
                listed = await session.list_tools()
            except Exception as error:
                self.errors[name] = f"{type(error).__name__}: {error}"
                continue
            self.sessions[name] = session
            for tool in listed.tools:
                self.tools.append(_wrap(self, name, tool))
        return self.tools

    async def call(self, server: str, tool: str, arguments: dict[str, Any]) -> ToolResult:
        session = self.sessions.get(server)
        if session is None:
            return ToolResult(ok=False, content=f"MCP server {server} is not connected.")
        result = await session.call_tool(tool, arguments)
        parts = []
        for block in getattr(result, "content", []) or []:
            text = getattr(block, "text", None)
            parts.append(text if text is not None else f"[{getattr(block, 'type', 'content')}]")
        is_error = bool(getattr(result, "is_error", False) or getattr(result, "isError", False))
        return ToolResult(ok=not is_error, content="\n".join(parts) or "(no content)")

    def describe(self) -> str:
        lines = []
        for server in self.sessions:
            count = sum(t.name.startswith(f"{PREFIX}{server}__") for t in self.tools)
            lines.append(f"{server}: connected ({count} tools)")
        lines += [f"{server}: NOT connected — {error}" for server, error in self.errors.items()]
        lines += [f"  {t.name}: {t.description[:100]}" for t in self.tools]
        return "\n".join(lines) or "No MCP servers configured (config: mcp.servers)."

    async def close(self) -> None:
        with contextlib.suppress(Exception):
            await self._stack.aclose()


def _wrap(hub: McpHub, server: str, mcp_tool: Any) -> Tool:
    tool_name = f"{PREFIX}{server}__{mcp_tool.name}"[:64]
    schema = (
        getattr(mcp_tool, "input_schema", None)
        or getattr(mcp_tool, "inputSchema", None)
        or {"type": "object"}
    )
    # Not called `description`: the class body below defines that name, which would shadow this one.
    tool_description = (getattr(mcp_tool, "description", "") or f"{mcp_tool.name} (MCP server {server})")[
        :1000
    ]

    class McpTool(Tool):
        name: ClassVar[str] = tool_name
        description: ClassVar[str] = f"[MCP {server}] {tool_description}"
        read_only: ClassVar[bool] = False
        Args: ClassVar[type[ToolArgs]] = _AnyArgs

        def spec(self) -> ToolSpec:
            return ToolSpec(
                name=self.name, description=self.description, parameters=inline_schema(dict(schema))
            )

        async def run(self, args: Any, context: ToolContext) -> ToolResult:
            return await hub.call(server, mcp_tool.name, args.model_dump())

    return McpTool()

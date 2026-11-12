"""Runs an agent: it chooses one of its tools for the question, calls it and answers from what the tool returned.

An agent can only work with what fits into its context: a tool result larger than the agent's
`max_context_chars` cannot be read, and the run fails.
"""

from __future__ import annotations

import importlib
import re
from dataclasses import dataclass

from agenthub import deployment_api
from agenthub.store import Agent, Tool

STOP_WORDS = {"the", "a", "an", "of", "that", "which", "what", "is", "are", "with", "all", "their", "this", "show", "list"}


class ContextOverflow(Exception):
    def __init__(self, tool: str, size: int, limit: int) -> None:
        super().__init__(f"the result of {tool} has {size} characters; the agent's context holds {limit}")
        self.tool, self.size, self.limit = tool, size, limit


@dataclass
class RunResult:
    tool: str
    tool_result_chars: int
    answer: str


def _words(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z]+", text.lower()) if word not in STOP_WORDS}


def choose_tool(agent: Agent, question: str) -> Tool:
    """The tool whose description shares the most words with the question (the first one on a tie)."""
    asked = _words(question)
    return max(agent.tools, key=lambda tool: len(asked & _words(tool.description + " " + tool.name.replace("_", " "))))


def call_tool(tool: Tool) -> str:
    if tool.kind == "native":
        return deployment_api.call(tool.target)
    module_name, _, function_name = tool.target.partition(":")
    return str(getattr(importlib.import_module(module_name), function_name)())


def run(agent: Agent, question: str) -> RunResult:
    if not agent.tools:
        raise LookupError(f"agent {agent.name} has no tools")
    tool = choose_tool(agent, question)
    result = call_tool(tool)
    if len(result) > agent.max_context_chars:
        raise ContextOverflow(tool.name, len(result), agent.max_context_chars)
    return RunResult(tool.name, len(result), result)

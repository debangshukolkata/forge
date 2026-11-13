"""Runs an agent: a LangGraph tool-calling agent on a real Azure OpenAI model, with the tools and the system prompt
from the database.

An agent can only work with what fits into its context: a tool result larger than the agent's
`max_context_chars` cannot be used, and the run fails.
"""

from __future__ import annotations

import importlib
import re
from dataclasses import dataclass, field
from typing import Any

from agenthub_pg import deployment_api
from agenthub_pg.settings import settings
from agenthub_pg.store import Agent, Tool

STOP_WORDS = {
    "the",
    "a",
    "an",
    "of",
    "that",
    "which",
    "what",
    "is",
    "are",
    "with",
    "all",
    "their",
    "this",
    "show",
    "list",
}


class ContextOverflow(Exception):
    def __init__(self, tool: str, size: int, limit: int) -> None:
        super().__init__(f"the result of {tool} has {size} characters; the agent's context holds {limit}")
        self.tool, self.size, self.limit = tool, size, limit


@dataclass
class RunResult:
    tools: list[str] = field(default_factory=list)
    tool_result_chars: int = 0
    answer: str = ""


def call_tool(tool: Tool) -> str:
    if tool.kind == "native":
        return deployment_api.call(tool.target)
    module_name, _, function_name = tool.target.partition(":")
    return str(getattr(importlib.import_module(module_name), function_name)())


def _words(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z]+", text.lower()) if word not in STOP_WORDS}


def _model() -> Any:
    from langchain_openai import AzureChatOpenAI

    return AzureChatOpenAI(
        azure_endpoint=settings.azure_endpoint,
        api_key=settings.azure_api_key,  # type: ignore[arg-type]
        api_version=settings.azure_api_version,
        azure_deployment=settings.azure_deployment,
        temperature=0,
    )


def run(agent: Agent, question: str) -> RunResult:
    if not agent.tools:
        raise LookupError(f"agent {agent.name} has no tools")
    result = RunResult()

    def guarded(tool: Tool) -> str:
        text = call_tool(tool)
        result.tools.append(tool.name)
        result.tool_result_chars = len(text)
        if len(text) > agent.max_context_chars:
            raise ContextOverflow(tool.name, len(text), agent.max_context_chars)
        return text

    if settings.fake_model:  # the API tests: no model, the tool whose description fits the question best
        asked = _words(question)
        best = max(
            agent.tools, key=lambda t: len(asked & _words(t.description + " " + t.name.replace("_", " ")))
        )
        result.answer = guarded(best)
        return result

    from langchain_core.tools import StructuredTool
    from langgraph.prebuilt import create_react_agent

    def make_tool(tool: Tool) -> StructuredTool:
        def call() -> str:
            return guarded(tool)

        return StructuredTool.from_function(func=call, name=tool.name, description=tool.description)

    tools = [make_tool(tool) for tool in agent.tools]
    graph = create_react_agent(_model(), tools, prompt=agent.system_prompt)
    try:
        output = graph.invoke({"messages": [("user", question)]}, {"recursion_limit": 12})
    except ContextOverflow:
        raise
    if (
        result.tool_result_chars > agent.max_context_chars
    ):  # the graph may have turned the error into a message
        raise ContextOverflow(result.tools[-1], result.tool_result_chars, agent.max_context_chars)
    content = output["messages"][-1].content
    result.answer = content if isinstance(content, str) else str(content)
    return result

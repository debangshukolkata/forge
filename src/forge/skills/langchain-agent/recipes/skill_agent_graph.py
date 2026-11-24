"""A tool-calling (ReAct) agent that attaches tools to itself through skills: an explicit LangGraph graph.

Works on langgraph 0.2 to 1.x: it uses only StateGraph, bind_tools and messages, which all of them have.

A skill = instructions (its own system prompt) + the names of the tools it may use. The model first sees one line per
skill and the `load_skill` tool. Loading a skill adds its instructions and binds its tools for the next step.
The code, not the prompt, decides what may run: a tool runs only when a loaded skill names it AND the agent is
allowed to use it (`allowed_tools`).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Annotated, Any

from langchain_core.messages import AnyMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

LOAD_SKILL = "load_skill"
NO_GUESSING = (
    "Never state a fact about this system that no tool returned in this conversation: when no available tool "
    "can answer, say that you cannot."
)


@dataclass(frozen=True)
class Skill:
    name: str
    description: str  # one line: what it is for and when to pick it; the model chooses by this
    instructions: str
    tools: tuple[str, ...] = ()


def merge_names(old: list[str] | None, new: list[str] | None) -> list[str]:
    return list(dict.fromkeys([*(old or []), *(new or [])]))


class SkillAgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    active_skills: Annotated[
        list[str], merge_names
    ]  # with a checkpointer a skill stays loaded in the conversation


def build_skill_agent(
    model: Any,  # a chat model with bind_tools; take it from the application's own factory
    skills: Sequence[Skill],  # read from the repository's own store (a table, SKILL.md files)
    tool_registry: Mapping[str, BaseTool],  # the repository's existing tools by name; never copies of them
    allowed_tools: set[str],  # what this agent and this user may use at all
    system_prompt: str,
    checkpointer: Any = None,
    on_tool: Callable[[str], None] | None = None,
) -> Any:
    by_name = {skill.name: skill for skill in skills}
    if LOAD_SKILL in tool_registry:
        raise ValueError(f"a tool named {LOAD_SKILL} already exists in the registry")

    def usable(skill: Skill) -> list[str]:
        return [name for name in skill.tools if name in tool_registry and name in allowed_tools]

    def tools_for(active: Sequence[str]) -> dict[str, BaseTool]:
        names = [name for key in active if key in by_name for name in usable(by_name[key])]
        return {name: tool_registry[name] for name in names}

    def load_skill(name: str) -> str:
        """Loads a skill: its instructions, and its tools become available in the next step."""
        raise NotImplementedError("handled by the tools node, which also changes the state")

    load_tool = StructuredTool.from_function(func=load_skill, name=LOAD_SKILL)

    def system_text(active: Sequence[str]) -> str:
        index = "\n".join(f"- {s.name}: {s.description}" for s in skills)
        parts = [system_prompt]
        if index:
            parts.append(
                "Skills you can load with load_skill. When one fits the request, load it before you answer; "
                f"its tools are available only after that:\n{index}\n\n{NO_GUESSING}"
            )
        parts += [f"# Skill {by_name[k].name}\n{by_name[k].instructions}" for k in active if k in by_name]
        return "\n\n".join(parts)

    def prepare(state: SkillAgentState) -> tuple[Any, list[AnyMessage]]:
        active = state.get("active_skills") or []
        tools = [*([load_tool] if skills else []), *tools_for(active).values()]
        bound = model.bind_tools(tools) if tools else model
        return bound, [SystemMessage(system_text(active)), *state["messages"]]

    def call_model(state: SkillAgentState, config: RunnableConfig) -> dict[str, Any]:
        bound, messages = prepare(state)
        return {"messages": [bound.invoke(messages, config)]}

    async def acall_model(state: SkillAgentState, config: RunnableConfig) -> dict[str, Any]:
        bound, messages = prepare(state)
        return {"messages": [await bound.ainvoke(messages, config)]}

    def failed(call: Mapping[str, Any], text: str) -> ToolMessage:
        return ToolMessage(text, tool_call_id=call["id"], name=call["name"], status="error")

    def loaded(call: Mapping[str, Any]) -> tuple[ToolMessage, list[str]]:
        skill = by_name.get(str(call["args"].get("name", "")))
        if skill is None:
            return failed(call, f"No such skill. The skills are: {', '.join(by_name)}"), []
        ready = usable(skill)
        missing = [name for name in skill.tools if name not in ready]
        text = f"Skill {skill.name} is loaded. Its tools now available: {', '.join(ready) or 'none'}."
        if missing:
            text += f" Not available to this agent: {', '.join(missing)}; say so if the task needs them."
        return ToolMessage(text, tool_call_id=call["id"], name=LOAD_SKILL), [skill.name]

    def refused(call: Mapping[str, Any], active: Sequence[str]) -> ToolMessage | None:
        """The check that counts: the model can name any tool, also one it was not given."""
        if call["name"] in tools_for(active):
            return None
        return failed(
            call, f"{call['name']} is not available. Load a skill that has it, or answer without it."
        )

    def prepared(call: Mapping[str, Any]) -> dict[str, Any]:
        if on_tool is not None:
            on_tool(call["name"])
        return {"name": call["name"], "args": call["args"], "id": call["id"], "type": "tool_call"}

    def split(state: SkillAgentState) -> tuple[list[ToolMessage | None], list[str], list[str]]:
        active = state.get("active_skills") or []
        answers: list[ToolMessage | None] = []
        newly: list[str] = []
        for call in state["messages"][-1].tool_calls:  # type: ignore[union-attr]
            if call["name"] == LOAD_SKILL:
                message, names = loaded(call)
                answers.append(message)
                newly += names
            else:  # a tool of a skill loaded in this same step is not available before the next one
                answers.append(refused(call, active))
        return answers, newly, list(active)

    def run_tools(state: SkillAgentState, config: RunnableConfig) -> dict[str, Any]:
        answers, newly, active = split(state)
        tools = tools_for(active)
        for index, call in enumerate(state["messages"][-1].tool_calls):  # type: ignore[union-attr]
            if answers[index] is None:
                try:
                    answers[index] = tools[call["name"]].invoke(prepared(call), config)
                except (
                    Exception
                ) as error:  # the model sees what failed and can react; narrow this to your errors
                    answers[index] = failed(call, f"{type(error).__name__}: {error}"[:500])
        return {"messages": answers, "active_skills": newly}

    async def arun_tools(state: SkillAgentState, config: RunnableConfig) -> dict[str, Any]:
        answers, newly, active = split(state)
        tools = tools_for(active)

        async def one(call: Mapping[str, Any]) -> ToolMessage:
            try:
                return await tools[call["name"]].ainvoke(prepared(call), config)
            except Exception as error:
                return failed(call, f"{type(error).__name__}: {error}"[:500])

        calls = state["messages"][-1].tool_calls  # type: ignore[union-attr]
        pending = [i for i, answer in enumerate(answers) if answer is None]
        for i, message in zip(pending, await asyncio.gather(*(one(calls[i]) for i in pending)), strict=True):
            answers[i] = message
        return {"messages": answers, "active_skills": newly}

    def route(state: SkillAgentState) -> str:
        return "tools" if getattr(state["messages"][-1], "tool_calls", None) else END

    graph = StateGraph(SkillAgentState)
    graph.add_node("agent", RunnableLambda(call_model, acall_model))
    graph.add_node("tools", RunnableLambda(run_tools, arun_tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", route, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=checkpointer)


# Run: graph.invoke({"messages": [("user", question)]}, {"recursion_limit": 25})
# Stream tokens: async for chunk, meta in graph.astream(inputs, config, stream_mode="messages")
# Stream steps: graph.stream(inputs, config, stream_mode="updates")
# Keep GraphRecursionError (langgraph.errors): it is how a run that never ends is reported.

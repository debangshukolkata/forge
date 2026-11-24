"""The same skill agent as middleware for `langchain.agents.create_agent` (langchain 1.x only).

    agent = create_agent(model, tools=registry_tools, system_prompt=..., middleware=[SkillMiddleware(skills, allowed)])

Every tool has to be given to create_agent, or it cannot be executed; the middleware shows the model only the tools
of the loaded skills, and refuses a call to any other one.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Annotated, Any, NotRequired

from langchain.agents.middleware import AgentMiddleware, AgentState, ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.types import Command

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


class SkillState(AgentState):
    active_skills: NotRequired[Annotated[list[str], merge_names]]


class SkillMiddleware(AgentMiddleware):
    state_schema = SkillState

    def __init__(self, skills: Sequence[Skill], allowed_tools: set[str]) -> None:
        super().__init__()
        self.by_name = {skill.name: skill for skill in skills}
        self.allowed = allowed_tools

        @tool(LOAD_SKILL)
        def load_skill(name: str, tool_call_id: Annotated[str, InjectedToolCallId]) -> Any:
            """Loads a skill: its instructions, and its tools become available in the next step."""
            skill = self.by_name.get(name)
            if skill is None:
                return f"No such skill. The skills are: {', '.join(self.by_name)}"
            ready = [t for t in skill.tools if t in self.allowed]
            text = f"Skill {name} is loaded. Its tools now available: {', '.join(ready) or 'none'}."
            missing = [t for t in skill.tools if t not in self.allowed]
            if missing:
                text += f" Not available to this agent: {', '.join(missing)}; say so if the task needs them."
            return Command(
                update={
                    "active_skills": [name],
                    "messages": [ToolMessage(text, tool_call_id=tool_call_id, name=LOAD_SKILL)],
                }
            )

        self.tools = [load_skill]

    def _available(self, state: Any) -> set[str]:
        active = state.get("active_skills") or []
        return {
            t for key in active if key in self.by_name for t in self.by_name[key].tools if t in self.allowed
        }

    def _request(self, request: ModelRequest) -> ModelRequest:
        names = self._available(request.state) | {LOAD_SKILL}
        index = "\n".join(f"- {s.name}: {s.description}" for s in self.by_name.values())
        # langchain 1.0 has `system_prompt` (text) on the request, later releases have `system_message`
        newer = hasattr(request, "system_message")
        message = request.system_message if newer else None
        before = (str(message.content) if message else "") if newer else str(request.system_prompt or "")
        parts = [
            before,
            "Skills you can load with load_skill. When one fits the request, load it before you answer; "
            f"its tools are available only after that:\n{index}\n\n{NO_GUESSING}",
        ]
        for key in request.state.get("active_skills") or []:
            if key in self.by_name:
                parts.append(f"# Skill {key}\n{self.by_name[key].instructions}")
        text = "\n\n".join(part for part in parts if part)
        system: dict[str, Any] = {"system_message": SystemMessage(text)} if newer else {"system_prompt": text}
        shown = [t for t in request.tools if getattr(t, "name", None) in names]
        return request.override(tools=shown, **system)

    def wrap_model_call(
        self, request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]
    ) -> ModelResponse:
        return handler(self._request(request))

    async def awrap_model_call(
        self, request: ModelRequest, handler: Callable[[ModelRequest], Awaitable[ModelResponse]]
    ) -> ModelResponse:
        return await handler(self._request(request))

    def _refused(self, request: Any) -> ToolMessage | None:
        """The check that counts: the model can name any tool, also one it was not shown."""
        call = request.tool_call
        if call["name"] == LOAD_SKILL or call["name"] in self._available(request.state):
            return None
        return ToolMessage(
            f"{call['name']} is not available. Load a skill that has it, or answer without it.",
            tool_call_id=call["id"],
            name=call["name"],
            status="error",
        )

    def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        return self._refused(request) or handler(request)

    async def awrap_tool_call(self, request: Any, handler: Callable[[Any], Awaitable[Any]]) -> Any:
        return self._refused(request) or await handler(request)

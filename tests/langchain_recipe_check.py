"""Runs the recipes of the langchain-agent skill with a scripted model; started with a LangChain interpreter.

    <venv python> langchain_recipe_check.py <recipes folder> graph|middleware

Standard library and LangChain only. Prints OK and the versions, or fails."""

from __future__ import annotations

import asyncio
import contextlib
import importlib.metadata as metadata
import sys
from typing import Any

sys.path.insert(0, sys.argv[1])
KIND = sys.argv[2]

from langchain_core.language_models.chat_models import BaseChatModel  # noqa: E402
from langchain_core.messages import AIMessage  # noqa: E402
from langchain_core.outputs import ChatGeneration, ChatResult  # noqa: E402
from langchain_core.tools import tool  # noqa: E402

if KIND == "graph":
    from skill_agent_graph import Skill, build_skill_agent
else:
    from skill_agent_middleware import Skill, SkillMiddleware

SEEN: list[tuple[set[str], str]] = []  # per model call: tools offered, system text
RAN: list[str] = []


class Scripted(BaseChatModel):
    """Answers with the given messages in order and notes what it was offered."""

    script: list[Any]
    offered: list[str] = []  # noqa: RUF012  (a pydantic field)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        return self.model_copy(update={"offered": [t.name for t in tools], "script": self.script})

    def _generate(
        self, messages: Any, stop: Any = None, run_manager: Any = None, **kwargs: Any
    ) -> ChatResult:
        SEEN.append((set(self.offered), str(messages[0].content)))
        return ChatResult(generations=[ChatGeneration(message=self.script.pop(0))])


def call(name: str, number: int, /, **args: Any) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"c{number}"}])


@tool
def add(a: int, b: int) -> int:
    """Adds."""
    RAN.append("add")
    return a + b


@tool
def wipe() -> str:
    """Forbidden."""
    RAN.append("wipe")
    return "wiped"


@tool
def broken() -> str:
    """Fails."""
    RAN.append("broken")
    raise ValueError("no luck")


SKILLS = [
    Skill("math", "sums", "MATH-RULE", ("add", "wipe", "ghost")),
    Skill("other", "other things", "OTHER-RULE", ("broken",)),
]


def agent(script: list[Any]) -> Any:
    SEEN.clear()
    RAN.clear()
    model = Scripted(script=script)
    allowed = {"add", "broken"}
    tools = {t.name: t for t in (add, wipe, broken)}
    if KIND == "graph":
        return build_skill_agent(model, SKILLS, tools, allowed, "BASE")
    from langchain.agents import create_agent

    return create_agent(
        model, tools=list(tools.values()), system_prompt="BASE", middleware=[SkillMiddleware(SKILLS, allowed)]
    )


def script() -> list[Any]:
    return [
        call("add", 1, a=1, b=2),  # before any skill: refused
        call("load_skill", 2, name="nothing"),
        call("load_skill", 3, name="math"),
        call("wipe", 4),  # named by the skill, not allowed: refused
        call("add", 5, a=17, b=25),
        AIMessage(content="42"),
    ]


def check(out: dict[str, Any]) -> None:
    texts = [str(m.content) for m in out["messages"]]
    assert RAN == ["add"], RAN
    assert "42" in texts[-2] and texts[-1] == "42", texts
    assert out["active_skills"] == ["math"], out["active_skills"]
    assert SEEN[0][0] == {"load_skill"} and "MATH-RULE" not in SEEN[0][1] and "sums" in SEEN[0][1], SEEN[0]
    assert SEEN[3][0] == {"load_skill", "add"}, SEEN[3][0]
    assert "BASE" in SEEN[3][1] and "MATH-RULE" in SEEN[3][1] and "OTHER-RULE" not in SEEN[3][1]
    assert any("No such skill" in t for t in texts)
    assert sum("is not available" in t for t in texts) == 2, texts
    assert any("Not available to this agent: wipe" in t for t in texts), texts


inputs = {"messages": [("user", "17+25?")]}
check(agent(script()).invoke(inputs))
check(asyncio.run(agent(script()).ainvoke(inputs)))
steps = list(agent(script()).stream(inputs, stream_mode="updates"))
assert len(steps) >= 11 and RAN == ["add"], steps
if KIND == "graph":  # two calls in one answer, one of them failing: each gets its result
    both = AIMessage(
        content="",
        tool_calls=[
            {"name": "broken", "args": {}, "id": "x"},
            {"name": "add", "args": {"a": 1, "b": 1}, "id": "y"},
        ],
    )
    two = [
        call("load_skill", 1, name="math"),
        call("load_skill", 2, name="other"),
        both,
        AIMessage(content="done"),
    ]
    for out in (agent(list(two)).invoke(inputs), asyncio.run(agent(list(two)).ainvoke(inputs))):
        tail = [str(m.content) for m in out["messages"][-3:]]
        assert "no luck" in tail[0] and tail[1] == "2" and tail[2] == "done", tail
found = []
for name in ("langchain", "langchain-core", "langgraph"):
    with contextlib.suppress(metadata.PackageNotFoundError):
        found.append(f"{name} {metadata.version(name)}")
print("OK", KIND, ", ".join(found))

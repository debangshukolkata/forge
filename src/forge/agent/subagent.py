"""Subagents (spec §9.10, §10.5): a fresh context and a restricted toolset for noisy work such as exploring
the codebase. Only the condensed report (<= ~1.5k tokens) comes back to the main conversation."""

from __future__ import annotations

from forge.agent.loop import AgentLoop
from forge.context.manager import ContextManager
from forge.engine.approvals import ApprovalBroker
from forge.engine.events import EventBus
from forge.llm.base import Message
from forge.llm.router import LLMRouter
from forge.llm.tokens import head_and_tail
from forge.safety.permissions import PermissionGate
from forge.safety.redact import default_redactor
from forge.tools.base import ToolContext
from forge.tools.registry import ToolRegistry, default_tools

REPORT_TOKENS = 1500
EXPLORE_ITERATIONS = 25

EXPLORE_PROMPT = """You are Forge's explore subagent. You only read: search the knowledge base and code to
find what a developer needs to implement the requirement below in THIS codebase. Report, in under 700 words:
- the most relevant existing files, and the closest existing example for each kind of new file needed
  (route/MethodView, marshmallow schema, service, repository/raw SQL, model, LangGraph node, test);
- the exact conventions those examples follow (naming, imports, error handling, test fixtures);
- where registrations happen (blueprints, config, graph wiring) and the test command;
- related tables/columns and anything surprising or risky.
Cite repository-relative paths. Don't propose a full plan."""


async def run_explore(router: LLMRouter, context: ToolContext, requirement: str) -> str:
    """Runs a read-only exploration with its own history and event bus; returns the condensed report."""
    bus = EventBus(redactor=default_redactor)  # private: the main UI only sees the report
    tools = ToolRegistry([t for t in default_tools() if t.read_only])
    sub_context = ToolContext(
        workspace=context.workspace,
        shell=context.shell,
        kb=context.kb,
        tool_cap_tokens=context.tool_cap_tokens,
        shell_cap_tokens=context.shell_cap_tokens,
    )
    gate = PermissionGate("plan", context.workspace.forge_dir / "permissions.json")
    manager = ContextManager(router, router.config)
    loop = AgentLoop(router, bus, tools, sub_context, gate, ApprovalBroker(bus), EXPLORE_ITERATIONS, manager)
    loop.escalate = False
    history = [Message.system(EXPLORE_PROMPT), Message.user(f"Requirement:\n{requirement}")]

    async def ignore(delta: str) -> None:
        return None

    await loop.run(history, ignore)
    report = next((m.content for m in reversed(history) if m.role == "assistant" and m.content.strip()), "")
    head, tail, omitted = head_and_tail(report, REPORT_TOKENS)
    return head + (f"\n[… {omitted} tokens of the report omitted …]\n" + tail if omitted else "")


DEBUGGER_ITERATIONS = 20
DEBUGGER_PROMPT = """You are Forge's debugger subagent, called because the main agent is stuck. You have a
fresh view: don't trust its assumptions. You may read code, search, and run tests/verify — you can't edit.
Find the root cause of the problem below. Reply in under 500 words:
1. Root cause (with the evidence: file:line, test output).
2. Why the previous attempts didn't work.
3. The concrete fix (which file, what change), and how to verify it.
If the requirement or a test itself looks wrong, say so plainly."""


async def run_debugger(router: LLMRouter, context: ToolContext, problem: str) -> str:
    """A fresh-context diagnosis (spec §13.3 step 2), on the reviewer role's model: a second model catches
    different mistakes. Read-only tools plus test runs."""
    from forge.tools.verify import RunTests, Verify

    tools = ToolRegistry([*(t for t in default_tools() if t.read_only), RunTests(), Verify()])
    return await _run_subagent(
        router, context, tools, DEBUGGER_PROMPT, problem, DEBUGGER_ITERATIONS, "reviewer"
    )


async def _run_subagent(
    router: LLMRouter,
    context: ToolContext,
    tools: ToolRegistry,
    prompt: str,
    task: str,
    iterations: int,
    role: str,
) -> str:
    bus = EventBus(redactor=default_redactor)
    sub_context = ToolContext(
        workspace=context.workspace,
        shell=context.shell,
        kb=context.kb,
        db=context.db,
        tool_cap_tokens=context.tool_cap_tokens,
        shell_cap_tokens=context.shell_cap_tokens,
    )
    gate = PermissionGate("default", context.workspace.forge_dir / "permissions.json")
    manager = ContextManager(router, router.config)
    loop = AgentLoop(router, bus, tools, sub_context, gate, ApprovalBroker(bus), iterations, manager)
    loop.role, loop.escalate = role, False
    history = [Message.system(prompt), Message.user(task)]

    async def ignore(delta: str) -> None:
        return None

    await loop.run(history, ignore)
    report = next((m.content for m in reversed(history) if m.role == "assistant" and m.content.strip()), "")
    head, tail, omitted = head_and_tail(report, REPORT_TOKENS)
    return head + (f"\n[… {omitted} tokens of the report omitted …]\n" + tail if omitted else "")

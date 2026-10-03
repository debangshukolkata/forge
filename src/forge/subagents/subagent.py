"""Subagents (spec §9.10, §10.5): a fresh context and a restricted toolset for noisy work such as exploring
the codebase. Only the condensed report (<= ~1.5k tokens) comes back to the main conversation."""

from __future__ import annotations

import itertools
import time

from forge.agent.loop import AgentLoop
from forge.context.manager import ContextManager
from forge.llm.base import Message
from forge.llm.router import LLMRouter
from forge.llm.tokens import head_and_tail
from forge.protocol.approvals import ApprovalBroker
from forge.protocol.events import EventBus, EventType
from forge.safety.permissions import PermissionGate
from forge.safety.redact import default_redactor
from forge.toolkit.base import ToolContext
from forge.toolkit.shell import RunCommand
from forge.tools.registry import ToolRegistry, default_tools

REPORT_TOKENS = 1500
EXPLORE_ITERATIONS = 25

EXPLORE_PROMPT = """You are Forge's explore subagent. You only read: search and read the code to
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
        tool_cap_tokens=context.tool_cap_tokens,
        shell_cap_tokens=context.shell_cap_tokens,
    )
    gate = PermissionGate("plan", context.workspace.forge_dir / "permissions.json")
    manager = ContextManager(router, router.config)
    loop = AgentLoop(router, bus, tools, sub_context, gate, ApprovalBroker(bus), EXPLORE_ITERATIONS, manager)
    history = [Message.system(EXPLORE_PROMPT), Message.user(f"Requirement:\n{requirement}")]

    await _tracked_run(
        context,
        loop,
        bus,
        history,
        "explorer",
        "Explore the code: " + requirement.splitlines()[0][:120]
        if requirement.strip()
        else "Explore the code",
    )
    report = next((m.content for m in reversed(history) if m.role == "assistant" and m.content.strip()), "")
    head, tail, omitted = head_and_tail(report, REPORT_TOKENS)
    return head + (f"\n[… {omitted} tokens of the report omitted …]\n" + tail if omitted else "")


VERIFIER_ITERATIONS = 45
VERIFIER_PROMPT = """You are Forge's verifier subagent. You did not write this code and you do not trust
it. The main agent gives you the requirement (and what changed) and how to run the app. Your job is to find
out, by running and using the app the way its users would, whether it really does what was asked, and to
report evidence. Work through these layers, skipping only those that cannot apply:

1. Static: does it compile and import? Run the language's checks (python -m compileall / ruff / mypy when the
   repo uses them, npm run build or tsc for a frontend). Any error is a finding.
2. Tests: run the project's own test suite and read the output; note failures, errors, warnings and skips.
3. Runtime: start the app (start_background with a ready_pattern; the port the requirement names) and read its
   output with read_background after exercising it. Tracebacks, 500 responses, warnings and deprecation
   messages in the server log are findings even when the page looks fine. Check that it also starts cleanly
   from an empty data folder.
4. Behaviour: list the acceptance checks the requirement implies, concretely: every page and route, every
   exact label, button text, message, column and link it names, each validation and error case, edge cases
   (empty input, duplicate, boundary values, second click, back button), persistence across reloads and
   pages, and that earlier features still work (regression). Turn them into a script and run it: for a web
   UI a Playwright script (python, sync API) under tests/e2e/ launched with
   `p.chromium.launch(channel="msedge", headless=True)` (no browser download is needed; if playwright is
   missing install it with `python -m pip install playwright`, the user is asked to approve); for an API or
   CLI a pytest or python script with requests or subprocess. Print one PASS/FAIL line per check with the observed value and exit non-zero on
   any failure.
5. Browser diagnostics: in the browser read the console (browser_console) and failed requests
   (browser_network): JavaScript errors, 404s for scripts or styles and failed API calls are findings. Compare
   the DOM (browser_snapshot, or page.evaluate for computed styles, classes and attributes) with what the
   requirement says.
6. Visual: take screenshots (browser_screenshot) of each page at desktop width and at 375px wide, and look at
   them with view_image: overlapping or cut-off text, horizontal scrolling, unreadable contrast, an empty
   chart, broken layout. Say what you saw.
7. Data: when the app stores anything, check the stored result directly (query the SQLite file or read the
   output file with a python_run script), not just the page that claims it saved.

For each FAIL decide: is it an app bug, or a wrong assumption in your check (a selector, timing, test data)?
Fix your own check mistakes and re-run until the remaining failures are real. Never weaken a check just to
turn it green. Stop the server (stop_background) when done. You may only write files below tests/e2e/ and you
cannot change the app; report problems instead. Reply with a short table per layer (PASS or FAIL, one line
each, with what you saw and any screenshot path), the exact steps to reproduce each real failure, the path of
your script, and a final line `VERDICT: PASS` (everything that applies passed) or `VERDICT: FAIL`."""

DEBUGGER_ITERATIONS = 20
DEBUGGER_PROMPT = """You are Forge's debugger subagent, called to give the main agent a fresh view of a
failure: don't trust its assumptions. You may read code, search and run commands (e.g. the tests) — you
can't edit.
Find the root cause of the problem below. Reply in under 500 words:
1. Root cause (with the evidence: file:line, test output).
2. Why the previous attempts didn't work.
3. The concrete fix (which file, what change), and how to verify it.
If the requirement or a test itself looks wrong, say so plainly."""


async def run_debugger(router: LLMRouter, context: ToolContext, problem: str) -> str:
    """A fresh-context diagnosis (spec §13.3 step 2), on the reviewer role's model: a second model catches
    different mistakes. Read-only tools plus the shell (to run tests)."""
    tools = ToolRegistry([*(t for t in default_tools() if t.read_only), RunCommand()])
    return await _run_subagent(
        router, context, tools, DEBUGGER_PROMPT, problem, DEBUGGER_ITERATIONS, "reviewer"
    )


_AGENT_IDS = itertools.count(1)


async def _tracked_run(
    context: ToolContext, loop: AgentLoop, bus: EventBus, history: list[Message], role: str, purpose: str
) -> None:
    """Runs a subagent on its private bus; the session only hears that it started and finished (Run map,
    D-119): who, for what, how long, how many tool calls and failures, and whether it ended normally."""

    async def ignore(delta: str) -> None:
        return None

    agent_id = f"agent-{next(_AGENT_IDS)}"
    started = time.perf_counter()
    await context.emit("agent_started", {"id": agent_id, "role": role, "purpose": purpose})
    ok = True
    try:
        await loop.run(history, ignore)
    except Exception:
        ok = False
        raise
    finally:
        finished = [e for e in bus.events_since(0) if e.type == EventType.TOOL_CALL_FINISHED]
        await context.emit(
            "agent_finished",
            {
                "id": agent_id,
                "role": role,
                "ok": ok,
                "tool_calls": len(finished),
                "failed_calls": sum(1 for e in finished if not e.payload.get("ok")),
                "duration_s": round(time.perf_counter() - started, 1),
            },
        )


def _purpose(prompt: str, task: str) -> str:
    """A short label: which kind of subagent (from its prompt) and what it was asked (first line)."""
    kind = next(
        (
            label
            for key, label in (
                ("reviewer", "Review the change"),
                ("debugger", "Diagnose a failure"),
                ("Diagnose", "Analyse a pasted error"),
            )
            if key in prompt[:200]
        ),
        "Helper task",
    )
    first = next((line.strip() for line in task.splitlines() if line.strip()), "")
    return f"{kind}: {first[:120]}" if first else kind


async def _run_subagent(
    router: LLMRouter,
    context: ToolContext,
    tools: ToolRegistry,
    prompt: str,
    task: str,
    iterations: int,
    role: str,
    *,
    write_only_under: str | None = None,
    needs_user_approvals: bool = False,
) -> str:
    bus = EventBus(redactor=default_redactor)
    sub_context = ToolContext(
        workspace=context.workspace,
        shell=context.shell,
        db=context.db,
        tool_cap_tokens=context.tool_cap_tokens,
        shell_cap_tokens=context.shell_cap_tokens,
        write_only_under=write_only_under,
    )
    gate_mode = "default"
    approvals = ApprovalBroker(bus)
    host = getattr(context.interaction, "host", None)
    if needs_user_approvals and host is not None:
        # The verifier installs packages and starts the app, which can need the user's approval: ask through
        # the same channel as the main agent instead of an internal broker nobody answers (it would hang).
        approvals = host.approvals
        gate_mode = host.agent.gate.mode if host.agent is not None else gate_mode
        sub_context.background = context.background
    gate = PermissionGate(gate_mode, context.workspace.forge_dir / "permissions.json")  # type: ignore[arg-type]
    manager = ContextManager(router, router.config)
    loop = AgentLoop(router, bus, tools, sub_context, gate, approvals, iterations, manager)
    loop.role = role
    history = [Message.system(prompt), Message.user(task)]

    await _tracked_run(context, loop, bus, history, role, _purpose(prompt, task))
    report = next((m.content for m in reversed(history) if m.role == "assistant" and m.content.strip()), "")
    head, tail, omitted = head_and_tail(report, REPORT_TOKENS)
    return head + (f"\n[… {omitted} tokens of the report omitted …]\n" + tail if omitted else "")

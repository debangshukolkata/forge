"""Two planners, one plan (D-658): two strong models plan the same task at once, a third merges the plans.

What both plans say goes into the plan as it is. Where they differ the merging model (`llm.plan_merger`, else the judge role) decides and
gives its reason; a difference that changes what gets built is put to the user as one question card, with the
merger's choice recommended (a run nobody watches takes the recommendation). The coder gets the merged plan and a
short list of what was decided between the two."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from forge.errors import LLMError
from forge.llm.base import ChatRequest, Message
from forge.llm.router import LLMRouter, forced_model
from forge.toolkit.base import ToolContext
from forge.tools.interaction import OptionSpec

MAX_QUESTIONS = 3  # more cards than this turns a plan into a questionnaire; the rest the merger decides

MERGE_PROMPT = """You merge two plans for the same task, written independently by two planners (A and B).

1. Everything both plans agree on goes into the merged plan unchanged in substance.
2. Something only one plan has goes in when it serves the task; leave out what does not.
3. Where they differ on the same point, decide by what gives the user the better result: the choice that also handles
   the cases the request did not spell out (other wordings, other inputs, the next file of the same kind) beats the one
   that only passes the example. Fewer tokens, fewer model calls or less code is never a reason. Give the reason in one
   sentence. Mark the difference
   `changes_what_is_built: true` only when the two choices would give the user a different result (a different approach,
   behaviour, data or interface), not for wording, file names or order of work.
4. Keep the merged plan's structure: objective, acceptance criteria, approach, tasks with checks, risks.

Answer with one JSON object and nothing else:
{"plan": "<the merged plan in Markdown>",
 "differences": [{"point": "<what the plans differ on, short>", "a": "<plan A's choice>", "b": "<plan B's choice>",
                  "chosen": "a" or "b", "reason": "<one sentence>", "changes_what_is_built": true or false}]}"""


@dataclass
class Difference:
    point: str
    a: str
    b: str
    chosen: str
    reason: str
    matters: bool
    decided_by: str = "merger"


@dataclass
class Merged:
    plan: str
    differences: list[Difference] = field(default_factory=list)


def planners(router: LLMRouter) -> list[str]:
    """The two models that plan, when both are known and set up in the .env file; otherwise none (one planner as before)."""
    keys = [
        key
        for key in dict.fromkeys(router.config.llm.plan_twice)
        if key in router.config.llm.models and router._configured(key)
    ]
    return keys[:2] if len(keys) >= 2 else []


def parse_merge(text: str) -> Merged | None:
    """The merger's answer, or None when it is not the JSON asked for."""
    found = re.search(r"\{.*\}", text, re.DOTALL)
    if found is None:
        return None
    try:
        data = json.loads(found.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not str(data.get("plan", "")).strip():
        return None
    differences = []
    for item in data.get("differences") or []:
        if not isinstance(item, dict):
            continue
        chosen = str(item.get("chosen", "a")).strip().lower()
        differences.append(
            Difference(
                point=str(item.get("point", "")).strip(),
                a=str(item.get("a", "")).strip(),
                b=str(item.get("b", "")).strip(),
                chosen="b" if chosen.startswith("b") else "a",
                reason=str(item.get("reason", "")).strip(),
                matters=item.get("changes_what_is_built") is True,
            )
        )
    return Merged(plan=str(data["plan"]).strip(), differences=[d for d in differences if d.point])


def report(merged: Merged) -> str:
    """The merged plan and, after it, what was decided between the two plans."""
    if not merged.differences:
        return merged.plan + "\n\n(Two planners wrote this plan independently and agreed on every point.)"
    lines = [merged.plan, "", "## Decided between the two plans"]
    for d in merged.differences:
        choice = d.a if d.chosen == "a" else d.b
        other = d.b if d.chosen == "a" else d.a
        who = "the user" if d.decided_by == "user" else "the merging model"
        lines.append(f"- **{d.point}**: {choice} (chosen by {who}; not: {other}). {d.reason}".rstrip())
        if d.decided_by == "user":
            lines.append("  Where the plan above says otherwise, follow this choice of the user.")
    return "\n".join(lines)


def _label(text: str, limit: int = 70) -> str:
    """A short option label, cut at a word."""
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " ..."


Asker = Callable[[str, str, list[Any], str | None], Awaitable[str]]


def _asker(context: ToolContext) -> Asker | None:
    interaction = context.interaction
    asker = getattr(interaction, "ask_user", None) if interaction is not None else None
    return asker or context.ask_user


async def ask_about(merged: Merged, ask: Asker | None) -> None:
    """Differences that change the result go to the user, at most MAX_QUESTIONS; the merger decides the rest."""
    if ask is None:
        return
    for d in [d for d in merged.differences if d.matters][:MAX_QUESTIONS]:
        first, second = _label(d.a) or "Plan A", _label(d.b) or "Plan B"
        if first == second:
            second = f"{second} (plan B)"
        options = [OptionSpec(label=first, description=d.a), OptionSpec(label=second, description=d.b)]
        recommended = first if d.chosen == "a" else second
        answer = await ask(
            f"Two plans differ: {d.point}",
            f"Two models planned this task independently. The merging model recommends: {recommended}. {d.reason}",
            options,
            recommended,
        )
        if second in answer and first not in answer:
            d.chosen, d.decided_by = "b", "user"
        elif first in answer and second not in answer:
            d.chosen, d.decided_by = "a", "user"


async def plan_twice(
    router: LLMRouter,
    context: ToolContext,
    keys: list[str],
    plan_once: Callable[[], Awaitable[str]],
    task: str,
) -> str:
    """Both planners at once, then the merge. With one plan only, that plan; with none, the error of the first."""

    async def with_model(key: str) -> str:
        token = forced_model.set(("planner", key))
        try:
            return await plan_once()
        finally:
            forced_model.reset(token)

    results = await asyncio.gather(*(with_model(key) for key in keys), return_exceptions=True)
    plans = [
        r for r in results if isinstance(r, str) and r.strip() and not r.startswith("(the subagent ended")
    ]
    if not plans:
        # Neither planner answered (their names are in the .env file but the models cannot be reached): the
        # planner role alone, as without two planners, rather than no plan at all.
        return await plan_once()
    if len(plans) == 1:
        return plans[0]
    request = ChatRequest(
        messages=[
            Message.system(MERGE_PROMPT),
            Message.user(f"TASK:\n{task}\n\nPLAN A:\n{plans[0]}\n\nPLAN B:\n{plans[1]}"),
        ]
    )
    merger = router.config.llm.plan_merger
    token = (
        forced_model.set(("judge", merger))
        if merger in router.config.llm.models and router._configured(merger)
        else None
    )
    try:
        merged = parse_merge((await router.chat("judge", request)).text)
    except LLMError:
        merged = None
    finally:
        if token is not None:
            forced_model.reset(token)
    if merged is None:  # the merge failed: the coder gets both plans rather than none
        return f"Two plans were written; they could not be merged. Weigh them yourself.\n\n## Plan A\n{plans[0]}\n\n## Plan B\n{plans[1]}"
    await ask_about(merged, _asker(context))
    return report(merged)

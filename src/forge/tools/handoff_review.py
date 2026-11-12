"""A second model looks at every hand-off before the user sees it (D-571).

`request_user_action` is the cheapest way out for the working model: it always "succeeds". On the office laptop
it sent the user to restart DebCraft, to copy variables and to rewrite a token, each time for something DebCraft
could have done itself. The known cases are refused by pattern (tools/interaction.py); this review is for the
ones nobody listed. The reviewer role's model (a different model from the coder where one is configured) gets
the card, the facts about the installation, the list of DebCraft's tools and the user's last messages, and says
whether DebCraft can do this itself. If so the card is not shown and the working model is told what to do
instead. It can insist: the third hand-off in a row is shown whatever the review says, and any failure of the
review shows the card.
"""

from __future__ import annotations

import json
import re

from forge.llm.base import ChatRequest, Message
from forge.toolkit.app_keys import installation_facts
from forge.toolkit.base import ToolContext

MAX_REFUSALS_IN_A_ROW = 2
REVIEWER = (
    "You check a hand-off. DebCraft is a coding agent that works in a copy of the user's repository on the "
    "user's Windows computer. It is about to interrupt the user with the card below and ask them to do "
    "something by hand. The user's main complaint about DebCraft is that it hands over work it could do itself "
    "and asks for things the user has already done or said.\n\n"
    "Decide one thing: is this card necessary?\n"
    "- `do_it_yourself` when DebCraft can do the step with its own tools (listed below), when the card "
    "contradicts the facts about the installation or what the user has said, when it asks the user to check, "
    "copy, move, rename or re-enter something DebCraft can look at or use where it is, or when its reason is a "
    "guess DebCraft has not checked.\n"
    "- `hand_over` only for what truly needs the user: getting a credential that is in none of the files, "
    "granting a right on a system DebCraft cannot reach, installing software outside the workspace, an action "
    "in another application or on another machine, a decision that is the user's to make.\n"
    "When unsure, answer `hand_over`: a needed card that is not shown is worse than an extra one.\n\n"
    'Answer with JSON only: {"verdict": "do_it_yourself" | "hand_over", "reason": "one or two sentences", '
    '"instead": "for do_it_yourself: the exact tools DebCraft should call, in order, and with what"}'
)


def _verdict(text: str) -> dict[str, str] | None:
    found = re.search(r"\{.*\}", text, re.DOTALL)
    if not found:
        return None
    try:
        data = json.loads(found.group(0))
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get("verdict") not in ("do_it_yourself", "hand_over"):
        return None
    return {key: str(data.get(key, "")) for key in ("verdict", "reason", "instead")}


async def review_hand_off(
    title: str, steps: list[str], verify_command: str | None, context: ToolContext
) -> str | None:
    """None: show the card. Otherwise what to tell the working model instead of showing it."""
    if context.router is None or context.handoff_refusals >= MAX_REFUSALS_IN_A_ROW:
        context.handoff_refusals = 0
        return None
    tools = context.tool_catalog() if context.tool_catalog is not None else []
    said = context.recent_user_messages() if context.recent_user_messages is not None else []
    card = "\n".join([f"Title: {title}", *(f"{index}. {step}" for index, step in enumerate(steps, 1))])
    if verify_command:
        card += f"\nDebCraft would check afterwards with: {verify_command}"
    question = "\n\n".join(
        [
            installation_facts(context.workspace).strip(),
            "DebCraft's tools:\n" + "\n".join(f"- {line}" for line in tools),
            "The user's last messages (oldest first):\n"
            + ("\n".join(f"- {text}" for text in said) or "- (none)"),
            "The card DebCraft wants to show:\n" + card,
        ]
    )
    request = ChatRequest(
        messages=[Message(role="system", content=REVIEWER), Message(role="user", content=question)]
    )
    try:
        response = await context.ask_model(
            "reviewer", request, "checking whether DebCraft can do this itself"
        )
        verdict = _verdict(str(response.text))
    except Exception:
        verdict = None
    if verdict is None or verdict["verdict"] == "hand_over":
        context.handoff_refusals = 0
        return None
    context.handoff_refusals += 1
    await context.emit(
        "notice",
        {"kind": "handoff_review", "text": f"A step for you was held back: {verdict['reason']}"[:400]},
    )
    return (
        "Not shown to the user. A second model checked this hand-off against the facts and against what DebCraft "
        f"can do itself: {verdict['reason']}\nDo this instead: {verdict['instead'] or 'use your own tools'}\n"
        "If you have already tried exactly that and it failed, call request_user_action again and put what you "
        "tried and what came back into the first step: it is then shown to the user."
    )

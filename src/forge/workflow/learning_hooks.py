"""Where learning meets the workflow (spec §12): related past requirements for PLAN, approved lessons pinned
at each task start, and — after EXPORT — the requirement card, metrics and the RETRO (proposed lessons that
the user approves in one step)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from forge.config import forge_home
from forge.learning.lessons import LessonStore, parse_proposals, render_for_pin
from forge.learning.library import Library
from forge.learning.metrics import Metrics
from forge.learning.scope import scope_of, visible_scopes
from forge.llm.base import ChatRequest, Message
from forge.protocol.events import EventType
from forge.workspace.output import compute_changes

if TYPE_CHECKING:
    from forge.workflow.orchestrator import Orchestrator

RETRO_PROMPT = """You write the retrospective of a finished software requirement for the team that runs
Forge (an AI coding agent). From the evidence, write in under 350 words:
## Went well
## Went wrong (with root causes)
## Proposed lessons
One per line, exactly '- LESSON: <imperative, reusable advice for future work on this codebase/host>'.
At most 3; only lessons that would have prevented a real problem or saved real time here. No secrets, no
code, no data values. If there is nothing worth keeping, write '- none'."""


def related_cards_note(orchestrator: Orchestrator) -> str:
    """Earlier requirements in the same repo/profile (never other scopes) — appended to any fresh brief,
    not only a change request, since a new requirement is the common case where citing a past card helps."""
    home = forge_home()
    scope = scope_of(orchestrator.workspace, home)
    hits = Library(home).search(
        orchestrator._requirement_text(), visible_scopes(scope), exclude=str(orchestrator.workspace.root)
    )
    if not hits:
        return ""
    lines = [f"- {h.id}: {h.title}" for h in hits[:3]]
    return (
        "\n\nRelated past requirements in this codebase (read them with library_read before planning; if one "
        "applies, cite it in the plan by its id, e.g. 'reuse the pattern from REQ-0001'):\n"
        + "\n".join(lines)
    )


def pin_lessons(orchestrator: Orchestrator, task_text: str) -> None:
    home = forge_home()
    config = orchestrator.host.router.config.learning
    scope = scope_of(orchestrator.workspace, home)
    lessons = LessonStore(home).retrieve(
        visible_scopes(scope), task_text, config.lessons_top_k, config.lessons_token_cap
    )
    orchestrator.host.context_manager.pinned.set("lessons", render_for_pin(lessons))


async def after_export(orchestrator: Orchestrator) -> None:
    """Card + metrics always; the retro as configured (learning.retro: prompt | auto | off)."""
    home = forge_home()
    workspace = orchestrator.workspace
    scope = scope_of(workspace, home)
    state = orchestrator.state
    files = [c.path for c in compute_changes(workspace) if not c.secret]
    review = orchestrator.store.read_document("reports/review.md")
    problems = [f"{t.id} needed {t.attempts} attempts" for t in state.tasks if t.attempts > 1]
    problems += [f"{t.id} blocked: {t.blocked_reason}" for t in state.tasks if t.status == "blocked"]
    sql = (
        (workspace.output_dir / "DB_CHANGES.sql").read_text(encoding="utf-8")
        if (workspace.output_dir / "DB_CHANGES.sql").exists()
        else ""
    )
    card_id = Library(home).write_card(
        scope=scope,
        workspace_root=str(workspace.root),
        workspace_name=workspace.info.name,
        requirement=orchestrator._requirement_text(),
        plan=orchestrator.store.read_document("PLAN.md"),
        decisions=orchestrator.store.read_document("DECISIONS.md"),
        tasks=[{"id": t.id, "status": t.status, "title": t.title} for t in state.tasks],
        files=files,
        sql=sql,
        status="done" if all(t.status == "done" for t in state.tasks) else "partial",
        problems=problems,
    )
    stuck_events = sum(
        1
        for e in orchestrator.host.bus.events_since(0)
        if e.type == EventType.NOTICE and e.payload.get("kind") == "stuck"
    )
    metrics = Metrics(home)
    for task in state.tasks:
        metrics.record(
            "task",
            scope,
            str(workspace.root),
            task=task.id,
            status=task.status,
            fix_attempts=max(task.attempts - 1, 0),
        )
    metrics.record(
        "run",
        scope,
        str(workspace.root),
        card=card_id,
        cost_usd=orchestrator.host.router.cost.total_usd,
        tasks=len(state.tasks),
        blocked=sum(t.status == "blocked" for t in state.tasks),
        stuck_events=stuck_events,
        review_findings=review.count("[blocking]") + review.count("[minor]"),
    )
    await orchestrator._notice("library", f"Saved this requirement to the library as {card_id}.")
    mode = orchestrator.host.router.config.learning.retro
    if mode != "off":
        # Fire-and-forget: the retro (an LLM call) and, in "prompt" mode, its lesson approval must never
        # gate the turn. Forge has already told the user the requirement is done and is free to take their
        # next message immediately, the same way this assistant doesn't block on a wrap-up aside — a
        # pending approval card the user hasn't noticed used to sit in front of every later chat message
        # (D-128's "not a turn-blocking approval gate" applied to PLAN/REQUIREMENTS but not to this).
        retro_task = asyncio.create_task(
            _retro(orchestrator, card_id, scope, review, problems, stuck_events, ask=mode == "prompt")
        )
        orchestrator._background(retro_task)


async def _retro(
    orchestrator: Orchestrator,
    card_id: str,
    scope: str,
    review: str,
    problems: list[str],
    stuck: int,
    ask: bool,
) -> None:
    home = forge_home()
    state = orchestrator.state
    evidence = "\n".join(
        [
            f"Requirement: {orchestrator._requirement_text()[:2000]}",
            "Tasks: "
            + "; ".join(f"{t.id} {t.status} (attempts {t.attempts}) {t.title}" for t in state.tasks),
            f"Problems: {'; '.join(problems) or 'none'}; stuck escalations: {stuck}",
            f"Review report (excerpt):\n{review[:3000]}",
        ]
    )
    try:
        response = await orchestrator.host.router.chat(
            "reviewer", ChatRequest(messages=[Message.system(RETRO_PROMPT), Message.user(evidence)])
        )
    except Exception as error:
        await orchestrator._notice("retro", f"Retro skipped: {error}")
        return
    retro_path = home / "learning" / "retros" / f"{card_id}.md"
    retro_path.parent.mkdir(parents=True, exist_ok=True)
    retro_path.write_text(f"# Retro {card_id}\n\n{response.text}\n", encoding="utf-8")
    store = LessonStore(home)
    proposed = [
        store.propose(text, scope, source="retro", evidence=card_id)
        for text in parse_proposals(response.text)
    ]
    proposed = [lesson for lesson in proposed if lesson.status == "proposed"]
    if not proposed:
        return
    listing = "\n".join(f"- {lesson.id}: {lesson.text}" for lesson in proposed)
    if not ask:
        await orchestrator._notice("retro", f"{len(proposed)} lesson(s) proposed; review them with /lessons.")
        return
    approved, _ = await orchestrator._approve(
        "lessons",
        f"Keep {len(proposed)} lesson(s) from this requirement for future work?",
        f"Retro for {card_id} (full text in Forge Home learning/retros/).\n\nProposed lessons:\n{listing}\n\n"
        "Approve keeps them (you can edit or delete any later with /lessons); reject drops them.",
    )
    for lesson in proposed:
        store.set_status(lesson.id, "approved" if approved else "rejected")

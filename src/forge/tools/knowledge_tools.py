"""`knowledge_search` and `knowledge_write`: the topic notes about a repository (KL2 and KL3, D-566).

What the model works out about an existing repository during a task is written down once, under DebCraft Home by
repository, and read by every later project on it. Each topic names its source files; when one of them has
changed since, the reader is told which, re-checks and corrects the topic. A wrong note is expected now and
then (the model is not perfect): it is corrected when the code shows the mistake, and the correction is kept
in the topic's history."""

from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from forge.config import forge_home
from forge.knowledge.code_map import CodeMap, cap
from forge.knowledge.structure import load
from forge.knowledge.topic_check import REVIEWER, rule_problem, verdict_of
from forge.knowledge.topics import (
    MAX_BODY_CHARS,
    MAX_SOURCES,
    Topic,
    all_topics,
    clear_winner,
    delete_topic,
    overlapping,
    ranked,
    read_topic,
    save_topic,
    slug_of,
    uncovered,
)
from forge.knowledge.usage import load_usage, never_read, reads_of, unused, use_order
from forge.knowledge.usage import record as count_use
from forge.llm.base import ChatRequest, Message
from forge.memory.scope import scope_of
from forge.memory.store import MemoryStore
from forge.safety.redact import default_redactor
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools.code_map_tool import (
    current_marks,
    knowledge_metrics,
    knowledge_store,
    project_view,
    repository_map_pin,
    timed_view,
)
from forge.workspace.workspace import Workspace

READS_BEFORE_REMINDER = 6  # files read without looking at what is already known
READS_BEFORE_WRITE_REMINDER = 14  # files read without writing anything down
WINNER_IN_FULL_CHARS = (
    8000  # a search returns a clearly best topic whole when it is no longer than this (KP5)
)
MAX_READ_AT_ONCE = 4
PIN_SLOT = "kb_essentials"
NO_REPOSITORY = "This project has no existing repository to keep knowledge about."
# The first things worth knowing about any service repository; the agenda lists the ones no topic covers yet.
STARTER_TOPICS = (
    ("how to run and test it", "run test start server command"),
    ("the web API: groups of endpoints, how a request is authenticated", "endpoint api route auth token"),
    ("the data model: main tables and what they hold", "table model schema database"),
    ("configuration: settings and environment variable names", "config settings environment"),
    ("agents: which exist and what each is for", "agent"),
    ("tools: where they are written and how one is attached to an agent", "tool attach register"),
    ("orchestration: how a run is built, its nodes and edges", "orchestration graph node edge workflow"),
    ("streaming and non-streaming answers: where each path is", "stream streaming response"),
)


def _outdated_note(topic: Topic, changed: list[str]) -> str:
    if not changed:
        return ""
    return (
        f"\n\n[These source files changed since this topic was written ({topic.updated}): {', '.join(changed)}. "
        "Read them before relying on it. If it still holds, call knowledge_write with this slug and "
        "`confirm: true`; if not, write the corrected topic with a `reason`.]"
    )


class KnowledgeSearch(Tool):
    name = "knowledge_search"
    read_only = True
    description = (
        "What earlier work wrote down about this repository (how agents, tools, orchestration, APIs and data "
        "fit together). Look here BEFORE exploring an area. action `search` (query = words: the best topics "
        "with their matching lines; a topic that clearly answers the question comes back whole), `read` (query = a topic's slug, or several slugs separated by commas: the whole topics, and which of its source "
        "files changed since it was written), `list` (every topic in one line each), `agenda` (what is worth "
        "learning next: topics whose files changed, areas with nothing written, files changed in the "
        "repository since the last update)."
    )

    class Args(ToolArgs):
        action: Literal["search", "read", "list", "agenda"]
        query: str = ""

    def summary(self, args: KnowledgeSearch.Args) -> str:
        return f"knowledge_search {args.action} {args.query}".strip()

    async def run(self, args: KnowledgeSearch.Args, context: ToolContext) -> ToolResult:
        workspace = context.workspace
        if workspace.mode_b:
            return ToolResult(ok=False, content=NO_REPOSITORY)
        context.knowledge_looked = True
        store = knowledge_store(workspace)
        notes = all_topics(store)
        structure, _, view_seconds = await timed_view(workspace)
        marks = current_marks(workspace, structure, {path for topic in notes for path in topic.sources})
        query = args.query.strip()

        def facts(outcome: str, **counts: int) -> dict[str, Any]:
            return knowledge_metrics(args.action, outcome, view_seconds, topics=len(notes), **counts)

        if args.action == "list":
            lines = [f"{topic.slug}: {topic.title}. {topic.summary}" for topic in notes]
            return ToolResult(
                ok=True,
                content=cap(lines) if lines else "Nothing is written down yet.",
                meta=facts("listed" if lines else "nothing"),
            )
        if args.action == "agenda":
            return ToolResult(ok=True, content=_agenda(notes, marks, structure, store), meta=facts("listed"))
        if not query:
            return ToolResult(ok=False, content=f"`{args.action}` needs a `query`.", meta=facts("refused"))
        if args.action == "read":
            slugs = [part for part in re.split(r"[\s,;]+", query) if part][:MAX_READ_AT_ONCE]
            rendered = []
            read_slugs = []
            outdated = 0
            for slug in slugs:
                topic = read_topic(store, slug)
                if topic is None:
                    names = ", ".join(note.slug for note in notes) or "none yet"
                    rendered.append(f"No topic {slug!r}. Topics: {names}.")
                else:
                    rendered.append(_render_topic(topic, marks))
                    read_slugs.append(topic.slug)
                    outdated += bool(topic.outdated(marks))
            record_use(store, workspace, read=read_slugs)
            if not read_slugs:
                return ToolResult(ok=False, content="\n\n".join(rendered), meta=facts("missing"))
            return ToolResult(
                ok=True,
                content="\n\n---\n\n".join(rendered),
                meta=facts("read", read=len(read_slugs), outdated=outdated),
            )
        found = ranked(notes, query, usage=load_usage(store), current=marks)
        if not found:
            return ToolResult(
                ok=True,
                content=f"Nothing written down matches {query!r}. Work it out from the code (code_map first), "
                "then record it with knowledge_write.",
                meta=facts("nothing"),
            )
        winner = clear_winner(found)
        lines = []
        for _, topic, hits in found:
            changed = topic.outdated(marks)
            mark = f" [may be outdated: {len(changed)} of its files changed]" if changed else ""
            lines.append(f"{topic.slug}: {topic.title}. {topic.summary}{mark}")
            if topic is not winner:
                lines += [f"    {hit[:200]}" for hit in hits]
        whole = winner is not None and len(winner.body) <= WINNER_IN_FULL_CHARS
        record_use(
            store,
            workspace,
            read=[winner.slug] if whole and winner is not None else [],
            found=[topic.slug for _, topic, _ in found],
        )
        if winner is not None and whole:
            # One topic clearly answers the question: give it whole, so no second call follows (KP5, D-574).
            return ToolResult(
                ok=True,
                content="\n".join(lines)
                + f"\n\nThe best match, {winner.slug}, in full:\n\n{_render_topic(winner, marks)}",
                meta=facts("whole", found=len(found), read=1),
            )
        return ToolResult(
            ok=True,
            content="\n".join(lines) + "\n\nRead one in full with action `read`.",
            meta=facts("matches", found=len(found)),
        )


def record_use(store: Path, workspace: Workspace, *, read: list[str], found: list[str] | None = None) -> None:
    """KU1: counts per topic, keyed by this project's folder so 'in how many projects' can be told."""
    count_use(store, str(workspace.root), read=read, found=found or [])


def _render_topic(topic: Topic, marks: dict[str, str]) -> str:
    sources = "\n".join(f"- {path}" for path in topic.sources)
    history = ("\n\nCorrections so far:\n" + "\n".join(topic.history)) if topic.history else ""
    return (
        f"# {topic.title}\n{topic.summary}\n\n{topic.body}\n\nSource files:\n{sources}{history}"
        + _outdated_note(topic, topic.outdated(marks))
    )


def _agenda(notes: list[Topic], marks: dict[str, str], structure: dict[str, Any], store: Path) -> str:
    code_map = CodeMap(structure)
    parts: list[str] = []
    stale = [(topic, topic.outdated(marks)) for topic in notes]
    stale = [(topic, changed) for topic, changed in stale if changed]
    if stale:
        parts.append(
            "Topics to re-check (their source files changed):\n"
            + "\n".join(f"- {topic.slug}: {', '.join(changed[:6])}" for topic, changed in stale)
        )
    task_like = [topic for topic in notes if rule_problem(topic.title, topic.summary)]
    if task_like:
        parts.append(
            "Topics that look like findings of a task, not knowledge of the repository (move to memory with "
            "memory_write and delete, or rewrite for any task; never removed automatically):\n"
            + "\n".join(f"- {topic.slug}: {topic.title[:90]}" for topic in task_like)
        )
    idle = unused([topic.slug for topic in notes], load_usage(store))
    if idle:
        parts.append(
            "Topics listed in several projects and never read (merge, shorten, delete or keep; never removed "
            "automatically):\n"
            + "\n".join(f"- {slug}: listed in {count} projects, read in none" for slug, count in idle)
        )
    same = overlapping(notes)
    if same:
        parts.append(
            "Topics that rest on mostly the same files (consider merging them into one):\n"
            + "\n".join(f"- {first} and {second}" for first, second in same)
        )
    folders: dict[str, int] = {}
    for path, record in code_map.files.items():
        folder = path.rsplit("/", 1)[0] if "/" in path else "."
        folders[folder] = folders.get(folder, 0) + len(record.get("symbols", []))
    open_folders = uncovered(folders, notes)
    if open_folders:
        parts.append(
            "Areas with nothing written down yet (most code first):\n"
            + "\n".join(f"- {folder}/ ({symbols} classes and functions)" for folder, symbols in open_folders)
        )
    text = " ".join(f"{topic.slug} {topic.title} {topic.summary}".lower() for topic in notes)
    missing = [title for title, words in STARTER_TOPICS if not any(word in text for word in words.split())]
    if missing:
        parts.append("Questions no topic answers yet:\n" + "\n".join(f"- {title}" for title in missing))
    changes = load(store).get("last_changes")
    if changes:
        parts.append(
            f"Changed in the repository when the map was last updated ({changes['at']}, {changes['count']} files):\n"
            + "\n".join(f"- {path}" for path in changes["paths"][:30])
        )
    return "\n\n".join(parts) or "Nothing is open: every area has a topic and no topic's files have changed."


class KnowledgeWrite(Tool):
    name = "knowledge_write"
    read_only = True  # it writes only DebCraft's own notes under DebCraft Home, like memory_write
    description = (
        "Write down what you worked out about THIS REPOSITORY so no later project has to work it out again: "
        "one topic per call, about one thing (for example 'How tools are attached to an agent'). `title`; "
        "`summary` (one line: what the topic answers); `body` (Markdown, at most about 150 lines: the facts, "
        "each with its file and line like `agents/react.py:42`, the names of classes, functions and tables, "
        "the order in which things happen; short excerpts only, no copies of whole functions); `sources` (the "
        "repository files the topic describes, so DebCraft can tell when it may be outdated). Describe the "
        "repository as it is, not the change you are making. To CORRECT a topic that turned out wrong or "
        "outdated: the same `slug`, the new text and a `reason` (what was wrong). To confirm a topic still holds "
        "after its files changed: `slug` and `confirm: true`. To remove one: `slug` and `delete: true`. Never "
        "put secrets or values from an .env file here, only the names of settings."
    )

    class Args(ToolArgs):
        title: str = ""
        summary: str = ""
        body: str = ""
        sources: list[str] = Field(default_factory=list)
        slug: str = ""
        reason: str = ""
        confirm: bool = False
        delete: bool = False

    def summary(self, args: KnowledgeWrite.Args) -> str:
        return f"knowledge_write {args.slug or args.title}"

    async def run(self, args: KnowledgeWrite.Args, context: ToolContext) -> ToolResult:
        workspace = context.workspace
        if workspace.mode_b:
            return ToolResult(ok=False, content=NO_REPOSITORY)
        store = knowledge_store(workspace)
        slug = slug_of(args.slug or args.title)
        existing = read_topic(store, slug) if (args.slug or args.title) else None
        started = time.perf_counter()
        structure, _, view_seconds = await timed_view(workspace)

        def facts(outcome: str, **counts: float) -> dict[str, Any]:
            # `total_s` leaves nothing out: the view, the second model's check, the save and the re-pin.
            total = round(time.perf_counter() - started, 2)
            return knowledge_metrics("write", outcome, view_seconds, total_s=total, **counts)

        if args.delete:
            done = delete_topic(store, slug)
            await self._repin(context, structure)
            return ToolResult(
                ok=done,
                content=f"Topic {slug} removed." if done else f"No topic {slug!r}.",
                meta=facts("removed" if done else "refused"),
            )
        if args.confirm:
            if existing is None:
                return ToolResult(ok=False, content=f"No topic {slug!r} to confirm.", meta=facts("refused"))
            existing.sources = current_marks(workspace, structure, existing.sources)
            existing.updated = time.strftime("%Y-%m-%d")
            save_topic(store, existing)
            await self._repin(context, structure)
            return ToolResult(
                ok=True, content=f"Topic {slug} confirmed against the current files.", meta=facts("confirmed")
            )
        problem = self._problem(args)
        if problem:
            return ToolResult(ok=False, content=problem, meta=facts("refused"))
        review_started = time.perf_counter()
        moved = await self._task_finding(args, slug, context)
        review_seconds = round(time.perf_counter() - review_started, 2)
        if moved is not None:
            outcome = "moved_to_memory" if moved.ok else "refused"
            return moved.model_copy(update={"meta": facts(outcome, review_s=review_seconds)})
        paths = [path.replace("\\", "/").strip().lstrip("./") for path in args.sources][:MAX_SOURCES]
        marks = current_marks(workspace, structure, paths)
        unknown = [path for path in paths if path not in marks]
        if unknown and len(unknown) == len(paths):
            return ToolResult(
                ok=False,
                content=f"None of the source files exist in the repository: {', '.join(unknown)}. Give paths "
                "relative to the repository root, as code_map and read_file show them.",
                meta=facts("refused", review_s=review_seconds),
            )
        history = list(existing.history) if existing else []
        if existing is not None:
            history.append(f"{time.strftime('%Y-%m-%d')}: {args.reason.strip() or 'rewritten'}"[:300])
        context.knowledge_written = True
        save_topic(
            store,
            Topic(
                slug=slug,
                title=default_redactor.redact(args.title.strip() or (existing.title if existing else slug)),
                summary=default_redactor.redact(" ".join(args.summary.split()))[:300],
                body=default_redactor.redact(args.body.strip()),
                sources=marks,
                updated=time.strftime("%Y-%m-%d"),
                history=history,
            ),
        )
        await self._repin(context, structure)
        note = f" Not found, so not tracked: {', '.join(unknown)}." if unknown else ""
        verb = "corrected" if existing is not None else "written"
        return ToolResult(
            ok=True,
            content=f"Topic {slug} {verb} ({len(marks)} source files tracked).{note} Every later project on this "
            "repository starts with it.",
            meta=facts(
                "corrected" if existing is not None else "written",
                review_s=review_seconds,
                sources=len(marks),
                characters=len(args.body.strip()),
            ),
        )

    @staticmethod
    def _problem(args: KnowledgeWrite.Args) -> str:
        if not args.title.strip() and not args.slug.strip():
            return "Give a `title` (or the `slug` of the topic you are correcting)."
        if not args.summary.strip() or len(args.body.strip()) < 80:
            return "A topic needs a one-line `summary` and a `body` with the facts and their file and line."
        if len(args.body) > MAX_BODY_CHARS:
            return (
                f"The body is {len(args.body)} characters; a topic holds at most {MAX_BODY_CHARS}. Split it into "
                "two topics about one thing each, and point to files and lines instead of copying code."
            )
        if not args.sources:
            return "Name the `sources`: the repository files this topic describes (so it can be re-checked when they change)."
        return ""

    @staticmethod
    async def _task_finding(args: KnowledgeWrite.Args, slug: str, context: ToolContext) -> ToolResult | None:
        """KU6: a note about this task is not repository knowledge. None: it is, go on and save the topic."""
        title = args.title.strip() or args.slug
        rule = rule_problem(title, args.summary)
        if rule:
            return ToolResult(ok=False, content=rule)
        if context.router is None or (args.slug and not args.title):
            return None
        question = f"Title: {title}\nSummary: {args.summary}\n\n{args.body[:3000]}"
        try:
            response = await context.ask_model(
                "reviewer",
                ChatRequest(
                    messages=[
                        Message(role="system", content=REVIEWER),
                        Message(role="user", content=question),
                    ]
                ),
                "checking that the note is about the repository, not the task",
            )
            verdict = verdict_of(str(response.text))
        except Exception:
            verdict = None  # a failed review never blocks a note
        if verdict is None or verdict[0] == "repository":
            return None
        memory = MemoryStore(forge_home(), scope_of(context.workspace)).save(
            slug, " ".join(args.summary.split())[:200], "project", f"{title}\n\n{args.body.strip()}"
        )
        await context.emit(
            "notice", {"kind": "memory", "text": f"Remembered ({memory.name}): {memory.description}"}
        )
        return ToolResult(
            ok=True,
            content=f"Not saved as a topic: a second model judged it to describe this task, not the repository "
            f"({verdict[1]}). It is kept in this project's memory as {memory.name}. Write a topic only for what "
            "is true of the repository for any task.",
        )

    @staticmethod
    async def _repin(context: ToolContext, structure: dict[str, Any]) -> None:
        """Re-pins the topic index from the view this call already made (KP3), off the event loop."""
        if context.pin is not None:
            pin = await asyncio.to_thread(repository_map_pin, context.workspace, False, structure)
            context.pin(PIN_SLOT, pin)


def reading_note(context: ToolContext) -> str:
    """One reminder each, appended to a read_file result: after several files read without looking at what is
    already known, and after many files read without writing anything down. The model was told both in its
    instructions; a weaker model forgets, and a rule that is not checked is not followed (D-312)."""
    workspace = context.workspace
    if workspace is None or workspace.mode_b or context.write_only_under is not None:
        return ""
    read = len(context.reads.paths())
    due = not context.knowledge_looked and not context.knowledge_look_asked and read >= READS_BEFORE_REMINDER
    if due and all_topics(
        knowledge_store(workspace)
    ):  # with nothing written down there is nothing to look at
        context.knowledge_look_asked = True
        return (
            f"\n\n[You have read {read} files. Earlier work wrote down how parts of this repository fit "
            "together: check knowledge_search (action `search`) before reading further, it may already answer this.]"
        )
    if (
        not context.knowledge_written
        and not context.knowledge_write_asked
        and read >= READS_BEFORE_WRITE_REMINDER
    ):
        context.knowledge_write_asked = True
        return (
            f"\n\n[You have read {read} files of this repository. Before you finish this task, record what you "
            "worked out about how this part fits together with knowledge_write (one topic per thing, with its "
            "files), or correct the existing topic: the next project should not have to read these files again.]"
        )
    return ""


LEARN_SKILL = "learn-repository"


def learn_request(focus: str = "") -> str:
    """The message `/learn` sends, also usable as the prompt of an unattended `debcraft run`."""
    about = f" Focus on: {focus.strip()}." if focus.strip() else ""
    return (
        f"Learn this repository for later projects: load the `{LEARN_SKILL}` skill and follow it.{about} "
        "Do not change any file of the repository."
    )


def stored_counts(workspace: Workspace) -> dict[str, Any] | None:
    """What is on disk for this repository, as numbers for `debcraft log-summary` (D-575): topics, how often
    they were read and found over all projects, and the most read ones. None for a project without a repository."""
    if workspace.mode_b:
        return None
    store = knowledge_store(workspace)
    slugs = [topic.slug for topic in all_topics(store)]
    usage = load_usage(store)
    most_read = [slug for slug in use_order(slugs, usage) if reads_of(usage, slug)][:5]
    return {
        "topics": len(slugs),
        "reads": sum(reads_of(usage, slug) for slug in slugs),
        "search_hits": sum(int(usage.get(slug, {}).get("found", 0)) for slug in slugs),
        "never_read": len(never_read(slugs, usage)),
        "most_read": [f"{slug} x{reads_of(usage, slug)}" for slug in most_read],
    }


def learning_status(workspace: Workspace) -> str:
    """What `/learn status` shows the user: what is written down, what may be outdated, what is open."""
    store = knowledge_store(workspace)
    notes = all_topics(store)
    structure, _ = project_view(workspace)
    marks = current_marks(workspace, structure, {path for topic in notes for path in topic.sources})
    lines = [f"Knowledge about this repository is kept in {store}", f"{len(notes)} topic(s) written down:"]
    for topic in notes:
        changed = topic.outdated(marks)
        mark = f"  (may be outdated: {len(changed)} of its files changed)" if changed else ""
        lines.append(f"  {topic.slug}: {topic.title}, updated {topic.updated}{mark}")
    return "\n".join(lines) + "\n\n" + _agenda(notes, marks, structure, store)

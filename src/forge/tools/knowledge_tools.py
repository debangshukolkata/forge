"""`knowledge_search` and `knowledge_write`: the topic notes about a repository (KL2 and KL3, D-566).

What the model works out about an existing repository during a task is written down once, under DebCraft Home by
repository, and read by every later project on it. Each topic names its source files; when one of them has
changed since, the reader is told which, re-checks and corrects the topic. A wrong note is expected now and
then (the model is not perfect): it is corrected when the code shows the mistake, and the correction is kept
in the topic's history."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from forge.knowledge.code_map import CodeMap, cap
from forge.knowledge.structure import load
from forge.knowledge.topics import (
    MAX_BODY_CHARS,
    MAX_SOURCES,
    Topic,
    all_topics,
    delete_topic,
    read_topic,
    save_topic,
    search,
    slug_of,
    uncovered,
)
from forge.safety.redact import default_redactor
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools.code_map_tool import current_marks, knowledge_store, project_view, repository_map_pin
from forge.workspace.workspace import Workspace

READS_BEFORE_REMINDER = 6  # files read without looking at what is already known
READS_BEFORE_WRITE_REMINDER = 14  # files read without writing anything down
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
        "with their matching lines), `read` (query = a topic's slug: the whole topic, and which of its source "
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
        structure, _ = project_view(workspace)
        marks = current_marks(workspace, structure, {path for topic in notes for path in topic.sources})
        query = args.query.strip()
        if args.action == "list":
            lines = [f"{topic.slug}: {topic.title}. {topic.summary}" for topic in notes]
            return ToolResult(ok=True, content=cap(lines) if lines else "Nothing is written down yet.")
        if args.action == "agenda":
            return ToolResult(ok=True, content=_agenda(notes, marks, structure, store))
        if not query:
            return ToolResult(ok=False, content=f"`{args.action}` needs a `query`.")
        if args.action == "read":
            topic = read_topic(store, query)
            if topic is None:
                names = ", ".join(note.slug for note in notes) or "none yet"
                return ToolResult(ok=False, content=f"No topic {query!r}. Topics: {names}.")
            sources = "\n".join(f"- {path}" for path in topic.sources)
            history = ("\n\nCorrections so far:\n" + "\n".join(topic.history)) if topic.history else ""
            return ToolResult(
                ok=True,
                content=f"# {topic.title}\n{topic.summary}\n\n{topic.body}\n\nSource files:\n{sources}{history}"
                + _outdated_note(topic, topic.outdated(marks)),
            )
        found = search(notes, query)
        if not found:
            return ToolResult(
                ok=True,
                content=f"Nothing written down matches {query!r}. Work it out from the code (code_map first), "
                "then record it with knowledge_write.",
            )
        lines = []
        for topic, hits in found:
            changed = topic.outdated(marks)
            mark = f" [may be outdated: {len(changed)} of its files changed]" if changed else ""
            lines.append(f"{topic.slug}: {topic.title}. {topic.summary}{mark}")
            lines += [f"    {hit[:200]}" for hit in hits]
        return ToolResult(ok=True, content="\n".join(lines) + "\n\nRead one in full with action `read`.")


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
        structure, _ = project_view(workspace)
        if args.delete:
            done = delete_topic(store, slug)
            self._repin(context)
            return ToolResult(ok=done, content=f"Topic {slug} removed." if done else f"No topic {slug!r}.")
        if args.confirm:
            if existing is None:
                return ToolResult(ok=False, content=f"No topic {slug!r} to confirm.")
            existing.sources = current_marks(workspace, structure, existing.sources)
            existing.updated = time.strftime("%Y-%m-%d")
            save_topic(store, existing)
            self._repin(context)
            return ToolResult(ok=True, content=f"Topic {slug} confirmed against the current files.")
        problem = self._problem(args)
        if problem:
            return ToolResult(ok=False, content=problem)
        paths = [path.replace("\\", "/").strip().lstrip("./") for path in args.sources][:MAX_SOURCES]
        marks = current_marks(workspace, structure, paths)
        unknown = [path for path in paths if path not in marks]
        if unknown and len(unknown) == len(paths):
            return ToolResult(
                ok=False,
                content=f"None of the source files exist in the repository: {', '.join(unknown)}. Give paths "
                "relative to the repository root, as code_map and read_file show them.",
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
        self._repin(context)
        note = f" Not found, so not tracked: {', '.join(unknown)}." if unknown else ""
        verb = "corrected" if existing is not None else "written"
        return ToolResult(
            ok=True,
            content=f"Topic {slug} {verb} ({len(marks)} source files tracked).{note} Every later project on this "
            "repository starts with it.",
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
    def _repin(context: ToolContext) -> None:
        if context.pin is not None:
            context.pin(PIN_SLOT, repository_map_pin(context.workspace, live=False))


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

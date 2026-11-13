"""Topic notes about a repository (KL2, D-566): what the model worked out and wrote down, one topic per file.

The structure index holds what can be read from the code exactly. A topic holds understanding: which agents
exist, how tools are attached, how the orchestration is built. Each topic names the source files it describes
and stores their fingerprints, so DebCraft can tell the reader which of them changed since the topic was
written. A topic is small on purpose: the index line is pinned, the body is loaded only when a task needs it.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

import yaml

from forge.knowledge.usage import MAX_USE_BONUS, OUTDATED_PENALTY, PINNED_BY_USE, Usage, reads_of, use_order

TOPICS_FOLDER = "topics"
MAX_BODY_CHARS = 12_000
MAX_SOURCES = 40
MAX_HISTORY = 12
FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


@dataclass
class Topic:
    slug: str
    title: str
    summary: str
    body: str = ""
    sources: dict[str, str] = field(default_factory=dict)  # path -> fingerprint when the topic was written
    updated: str = ""
    history: list[str] = field(default_factory=list)  # one line per correction: date and what was wrong

    def outdated(self, current: dict[str, str]) -> list[str]:
        """The source files that changed or disappeared since the topic was written."""
        return [path for path, mark in self.sources.items() if current.get(path) != mark]


def slug_of(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "topic"


def _folder(store: Path) -> Path:
    return store / TOPICS_FOLDER


_YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)  # the C parser when libyaml is installed
_parsed: dict[str, tuple[tuple[int, int], Topic | None]] = {}


def _parse(path: Path) -> Topic | None:
    """A topic file, parsed once per version of the file (size and modified time) so listing, searching and
    pinning do not open every file again (KP2). A copy is returned: callers edit topics."""
    try:
        status = path.stat()
    except OSError:
        return None
    stamp = (status.st_size, status.st_mtime_ns)
    cached = _parsed.get(str(path))
    if cached is None or cached[0] != stamp:
        cached = (stamp, _read(path))
        _parsed[str(path)] = cached
    topic = cached[1]
    return None if topic is None else replace(topic, sources=dict(topic.sources), history=list(topic.history))


def _read(path: Path) -> Topic | None:
    try:
        text = path.read_text(encoding="utf-8")
        match = FRONT.match(text)
        meta = yaml.load(match.group(1), Loader=_YAML_LOADER) if match else None
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(meta, dict) or not meta.get("title"):
        return None
    sources = meta.get("sources") or {}
    return Topic(
        slug=path.stem,
        title=str(meta["title"]),
        summary=str(meta.get("summary", "")),
        body=text[match.end() :].strip() if match else "",
        sources={str(key): str(value) for key, value in sources.items()} if isinstance(sources, dict) else {},
        updated=str(meta.get("updated", "")),
        history=[str(line) for line in meta.get("history") or []],
    )


def all_topics(store: Path) -> list[Topic]:
    folder = _folder(store)
    if not folder.is_dir():
        return []
    return [topic for path in sorted(folder.glob("*.md")) if (topic := _parse(path)) is not None]


def read_topic(store: Path, slug: str) -> Topic | None:
    path = _folder(store) / f"{slug_of(slug)}.md"
    return _parse(path) if path.is_file() else None


def save_topic(store: Path, topic: Topic) -> Path:
    folder = _folder(store)
    folder.mkdir(parents=True, exist_ok=True)
    meta = {
        "title": topic.title,
        "summary": topic.summary,
        "updated": topic.updated or time.strftime("%Y-%m-%d"),
        "sources": dict(sorted(topic.sources.items())),
        "history": topic.history[-MAX_HISTORY:],
    }
    text = "---\n" + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=1000) + "---\n\n"
    target = folder / f"{topic.slug}.md"
    scratch = target.with_suffix(".tmp")
    scratch.write_text(text + topic.body.strip() + "\n", encoding="utf-8")
    os.replace(scratch, target)
    return target


def delete_topic(store: Path, slug: str) -> bool:
    path = _folder(store) / f"{slug_of(slug)}.md"
    if not path.is_file():
        return False
    path.unlink()
    return True


FACT_LINE_CHARS = 160
KEY_FACTS_HEADING = re.compile(r"^#{1,6}\s*key facts\s*$", re.IGNORECASE)


def overlapping(topics: list[Topic], share: float = 0.6) -> list[tuple[str, str]]:
    """Pairs of topics resting on mostly the same source files (KU5): candidates for merging. Needs at least two
    shared files so one popular file does not link everything."""
    pairs = []
    for index, first in enumerate(topics):
        for second in topics[index + 1 :]:
            a, b = set(first.sources), set(second.sources)
            both = a & b
            if len(both) >= 2 and len(both) / len(a | b) >= share:
                pairs.append((first.slug, second.slug))
    return pairs


def key_facts(topic: Topic, lines: int) -> list[str]:
    """The few lines of a topic worth having in every model call (KU4): what is under a `Key facts` heading
    when the note has one, otherwise the first lines of its body that are not headings. Each is clipped."""
    body = [line.strip() for line in topic.body.splitlines()]
    start = next((i + 1 for i, line in enumerate(body) if KEY_FACTS_HEADING.match(line)), 0)
    facts: list[str] = []
    for line in body[start:]:
        if line.startswith("#"):
            if start:
                break  # the next heading ends the key facts section
            continue
        if line:
            facts.append(line if len(line) <= FACT_LINE_CHARS else line[: FACT_LINE_CHARS - 1] + "…")
        if len(facts) == lines:
            break
    return facts


def index_lines(
    topics: list[Topic],
    current: dict[str, str],
    limit: int = 80,
    usage: Usage | None = None,
    facts_top: int = 0,
    fact_lines: int = 4,
) -> list[str]:
    """One line per topic for the pinned index, with a mark on those whose sources changed.

    Once any topic has been read (KU2) only the most used ones get a line, the rest are counted: the pin stays
    short however many topics the repository collects. With no use yet it lists them in order, as before.
    `facts_top` (KU4): the first that many topics, the most used, also carry their key facts, so a common
    question needs no tool call. Only when use is known and the topic's files are unchanged."""
    if usage and any(reads_of(usage, topic.slug) for topic in topics):
        by_slug = {topic.slug: topic for topic in topics}
        topics = [by_slug[slug] for slug in use_order(list(by_slug), usage)]
        limit = min(limit, PINNED_BY_USE)
    lines = []
    with_facts = facts_top if usage and any(reads_of(usage, topic.slug) for topic in topics) else 0
    for number, topic in enumerate(topics[:limit]):
        changed = topic.outdated(current)
        mark = f" [may be outdated: {len(changed)} of its files changed]" if changed else ""
        lines.append(f"- {topic.slug}: {topic.title}. {topic.summary}{mark}")
        if number < with_facts and not changed:  # a note whose files changed may be wrong: no facts from it
            lines.extend(f"    {fact}" for fact in key_facts(topic, fact_lines))
    if len(topics) > limit:
        lines.append(f"- ... and {len(topics) - limit} more: knowledge_search finds them")
    return lines


def ranked(
    topics: list[Topic],
    query: str,
    limit: int = 6,
    usage: Usage | None = None,
    current: dict[str, str] | None = None,
) -> list[tuple[int, Topic, list[str]]]:
    """The topics that match the words of a query best: score, topic and the lines of its body that matched.

    The words decide; use adds a little (KU3) and a topic whose source files changed loses a little, so of two
    topics that fit equally the one that is read often and is still current comes first."""
    words = [word for word in re.findall(r"[a-z0-9_]+", query.lower()) if len(word) > 2]
    scored: list[tuple[int, Topic, list[str]]] = []
    for topic in topics:
        head = f"{topic.slug} {topic.title} {topic.summary}".lower()
        paths = " ".join(topic.sources).lower()
        body_lines = topic.body.splitlines()
        hits = [line.strip() for line in body_lines if any(word in line.lower() for word in words)]
        score = sum(
            6 * (word in head) + 2 * (word in paths) + min(3, topic.body.lower().count(word))
            for word in words
        )
        if score:
            score += min(MAX_USE_BONUS, reads_of(usage or {}, topic.slug))
            if current is not None and topic.outdated(current):
                score = max(1, score - OUTDATED_PENALTY)
            scored.append((score, topic, hits[:4]))
    scored.sort(key=lambda item: (-item[0], item[1].slug))
    return scored[:limit]


def search(topics: list[Topic], query: str, limit: int = 6) -> list[tuple[Topic, list[str]]]:
    return [(topic, hits) for _, topic, hits in ranked(topics, query, limit)]


def clear_winner(found: list[tuple[int, Topic, list[str]]]) -> Topic | None:
    """The best topic when it is the only match or scores half as much again as the next (KP5, D-574): the reader
    then needs no second call to read it."""
    if not found:
        return None
    if len(found) == 1 or found[0][0] * 2 >= found[1][0] * 3:
        return found[0][1]
    return None


def uncovered(folders: dict[str, int], topics: list[Topic], limit: int = 15) -> list[tuple[str, int]]:
    """Folders with the most symbols that no topic names a source file in: where nothing is written down yet."""
    covered = {path.rsplit("/", 1)[0] if "/" in path else "." for topic in topics for path in topic.sources}
    open_folders = [
        (folder, symbols) for folder, symbols in folders.items() if folder not in covered and symbols
    ]
    return sorted(open_folders, key=lambda item: (-item[1], item[0]))[:limit]

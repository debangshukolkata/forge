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
from dataclasses import dataclass, field
from pathlib import Path

import yaml

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


def _parse(path: Path) -> Topic | None:
    try:
        text = path.read_text(encoding="utf-8")
        match = FRONT.match(text)
        meta = yaml.safe_load(match.group(1)) if match else None
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


def index_lines(topics: list[Topic], current: dict[str, str], limit: int = 80) -> list[str]:
    """One line per topic for the pinned index, with a mark on those whose sources changed."""
    lines = []
    for topic in topics[:limit]:
        changed = topic.outdated(current)
        mark = f" [may be outdated: {len(changed)} of its files changed]" if changed else ""
        lines.append(f"- {topic.slug}: {topic.title}. {topic.summary}{mark}")
    if len(topics) > limit:
        lines.append(f"- ... and {len(topics) - limit} more: knowledge_search finds them")
    return lines


def search(topics: list[Topic], query: str, limit: int = 6) -> list[tuple[Topic, list[str]]]:
    """The topics that match the words of a query best, each with the lines of its body that matched."""
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
            scored.append((score, topic, hits[:4]))
    scored.sort(key=lambda item: (-item[0], item[1].slug))
    return [(topic, hits) for _, topic, hits in scored[:limit]]


def uncovered(folders: dict[str, int], topics: list[Topic], limit: int = 15) -> list[tuple[str, int]]:
    """Folders with the most symbols that no topic names a source file in: where nothing is written down yet."""
    covered = {path.rsplit("/", 1)[0] if "/" in path else "." for topic in topics for path in topic.sources}
    open_folders = [
        (folder, symbols) for folder, symbols in folders.items() if folder not in covered and symbols
    ]
    return sorted(open_folders, key=lambda item: (-item[1], item[0]))[:limit]

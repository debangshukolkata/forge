"""Which topics are read, so the pin and the search put the useful ones first (KU1 to KU3, D-574).

One file, `usage.json`, beside the topics folder (not inside the topic files: a read must not rewrite a topic and
disturb its fingerprints). Per topic: how often it was read, when last, in how many projects, and how often a
search found it. Counts only; never any text from a task."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

USAGE_FILE = "usage.json"
MAX_PROJECTS_KEPT = 50
PINNED_BY_USE = 20  # topics listed one by one in the pin once there is any use data
PIN_FACTS_TOP = 5  # topics that also carry their key facts in the pin (KU4, D-586: measured, top 5 costs about 300 tokens per call)
PIN_FACT_LINES = 4
UNUSED_AFTER_PROJECTS = 3  # a topic listed in this many projects and never read is offered for review (KU5)
MAX_USE_BONUS = 4  # what use can add to a search score: words come first
OUTDATED_PENALTY = 2

Usage = dict[str, dict[str, Any]]


def load_usage(store: Path) -> Usage:
    try:
        data = json.loads((store / USAGE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save(store: Path, usage: Usage) -> None:
    store.mkdir(parents=True, exist_ok=True)
    target = store / USAGE_FILE
    scratch = target.with_suffix(".tmp")
    scratch.write_text(json.dumps(usage, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(scratch, target)


def record(
    store: Path,
    project: str,
    *,
    read: Iterable[str] = (),
    found: Iterable[str] = (),
    seen: Iterable[str] = (),
) -> None:
    """Counts reads and search hits for this project. Best effort: a failed write never fails a tool."""
    read, found, seen = list(read), list(found), list(seen)
    if not read and not found and not seen:
        return
    try:
        usage = load_usage(store)
        today = time.strftime("%Y-%m-%d")
        for slug in seen:  # listed in the pin of this project (KU5)
            entry = usage.setdefault(slug, {})
            earlier = [p for p in entry.get("seen", []) if p != project]
            entry["seen"] = [*earlier[-(MAX_PROJECTS_KEPT - 1) :], project]
        for slug in found:
            usage.setdefault(slug, {})["found"] = usage.get(slug, {}).get("found", 0) + 1
        for slug in read:
            entry = usage.setdefault(slug, {})
            entry["reads"] = entry.get("reads", 0) + 1
            entry["last"] = today
            projects = [p for p in entry.get("projects", []) if p != project]
            entry["projects"] = [*projects, project][-MAX_PROJECTS_KEPT:]
        _save(store, usage)
    except OSError:
        return


def reads_of(usage: Usage, slug: str) -> int:
    return int(usage.get(slug, {}).get("reads", 0))


def use_order(slugs: list[str], usage: Usage) -> list[str]:
    """The slugs most read first, then most recently read; topics never read keep their given order after them."""
    position = {slug: index for index, slug in enumerate(slugs)}
    return sorted(
        slugs,
        key=lambda slug: (
            -reads_of(usage, slug),
            # newest first: negate by sorting the date string in reverse through its complement
            "".join(chr(255 - ord(c)) for c in str(usage.get(slug, {}).get("last", ""))),
            position[slug],
        ),
    )


def unused(slugs: list[str], usage: Usage, projects: int = UNUSED_AFTER_PROJECTS) -> list[tuple[str, int]]:
    """Topics never read although they were listed in at least `projects` projects: (slug, projects)."""
    found = [(slug, len(usage.get(slug, {}).get("seen", []))) for slug in slugs if reads_of(usage, slug) == 0]
    return [(slug, count) for slug, count in found if count >= projects]


def never_read(slugs: list[str], usage: Usage) -> list[str]:
    return [slug for slug in slugs if reads_of(usage, slug) == 0]

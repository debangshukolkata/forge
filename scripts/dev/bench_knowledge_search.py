"""How fast is the topic search as the notes pile up? (Knowledge efficiency, D-616.)

Writes N synthetic topics into a scratch folder and times what every `knowledge_search` call does: listing the
topic files (first call parses them, later calls hit the parse cache), ranking a query, and the pinned index.
Run: .venv\\Scripts\\python scripts\\dev\\bench_knowledge_search.py [counts...]   (default 50 200 500 1000)
"""

# ruff: noqa: B023, SIM905  (each lambda runs at once, inside its own loop turn)

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

from forge.knowledge import topics as topics_module
from forge.knowledge.topics import Topic, all_topics, index_lines, ranked, save_topic

WORDS = "agent tool endpoint table orchestration stream token secret route schema queue worker cache retry".split()


def make_topics(store: Path, count: int) -> None:
    for number in range(count):
        words = [WORDS[(number + step) % len(WORDS)] for step in range(6)]
        body = "\n".join(
            f"- fact {line} about {words[line % 6]} in pkg{number}/mod{line}.py:{line + 1} and {words[(line + 2) % 6]}"
            for line in range(60)
        )
        save_topic(
            store,
            Topic(
                slug=f"topic-{number}",
                title=f"How {words[0]} and {words[1]} work in pkg{number}",
                summary=f"{words[2]} {words[3]} of pkg{number}",
                body=body,
                sources={f"pkg{number}/mod{line}.py": "x" for line in range(8)},
            ),
        )


def timed(action) -> float:  # type: ignore[no-untyped-def]
    started = time.perf_counter()
    action()
    return round((time.perf_counter() - started) * 1000, 1)


def main() -> None:
    counts = [int(arg) for arg in sys.argv[1:]] or [50, 200, 500, 1000]
    print(
        "topics | no cache file (ms) | new process, cache file (ms) | same process (ms) | rank query (ms) | pin (ms)"
    )
    for count in counts:
        with tempfile.TemporaryDirectory() as folder:
            store = Path(folder)
            make_topics(store, count)
            marks = {f"pkg{n}/mod{line}.py": "x" for n in range(count) for line in range(8)}
            first = timed(lambda: all_topics(store))  # parses every note and writes the cache file
            topics_module._parsed.clear()  # a new process starts with nothing in memory
            topics_module._warmed.clear()
            warm = timed(lambda: all_topics(store))
            cached = timed(lambda: all_topics(store))
            notes = all_topics(store)
            rank = timed(lambda: ranked(notes, "orchestration token secret retry", current=marks))
            pin = timed(lambda: index_lines(notes, marks))
            print(f"{count:6} | {first:18} | {warm:28} | {cached:17} | {rank:15} | {pin:8}")


if __name__ == "__main__":
    main()

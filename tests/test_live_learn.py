"""Live (real Azure model): /learn writes topics about the repository, and a later project uses them (D-566).

`learn`: the model follows the learn-repository skill on the fixture repository; topics appear under DebCraft
Home with source files that exist, and nothing in the repository copy changes. `reuse`: a second project on the
same repository answers a question from a topic instead of reading the code again.
Set LEARN_LOG to a file to get one JSON line per step."""

from __future__ import annotations

import json
import os

import pytest

from forge.knowledge.topics import all_topics
from forge.protocol.events import EventType
from forge.tools.code_map_tool import knowledge_store
from forge.tools.knowledge_tools import learn_request
from tests.test_live_agent import make_host, run_turn  # noqa: F401  (make_host is a fixture)

pytestmark = pytest.mark.live


def _watcher(calls: list[str], said: list[str]):  # type: ignore[no-untyped-def]
    def watch(event):  # type: ignore[no-untyped-def]
        if event.type == EventType.TOOL_CALL_STARTED:
            calls.append(f"{event.payload['name']} {event.payload['arguments']}"[:100])
        if event.type == EventType.MESSAGE_DONE:
            said.append(str(event.payload.get("text", "")))
        return None

    return watch


def _log(row: dict[str, object]) -> None:
    path = os.environ.get("LEARN_LOG")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")


async def test_learn_writes_topics_and_the_next_project_uses_them(
    make_host,  # noqa: F811
) -> None:  # type: ignore[no-untyped-def]
    first = make_host("auto")
    calls: list[str] = []
    said: list[str] = []
    try:
        await run_turn(
            first,
            learn_request(
                "how a claim is created, from the endpoint to the tables, and how a request is authenticated"
            ),
            _watcher(calls, said),
        )
        store = knowledge_store(first.workspace)
        topics = all_topics(store)
        changed = [change.path for change in first.workspace.changes()]
    finally:
        await first.close()
    names = [topic.slug for topic in topics]
    _log(
        {"step": "learn", "calls": calls, "topics": names, "changed": changed, "said": "\n".join(said)[-500:]}
    )
    print(f"\nLEARN: {len(calls)} tool calls, topics={names}, repository files changed={changed}")
    assert topics, f"no topic was written; tools used: {calls}"
    assert not changed, f"learning must not change the repository: {changed}"
    for topic in topics:
        assert topic.sources and all(path.startswith("backend/") for path in topic.sources), topic.sources
        assert ".py:" in topic.body, f"{topic.slug} cites no file and line"
    text = " ".join(topic.body.lower() for topic in topics)
    assert "jwt" in text and "claims" in text and "create_claim" in text

    second = make_host("auto")  # another project on the same repository
    calls2: list[str] = []
    said2: list[str] = []
    try:
        await run_turn(
            second,
            "Do not change anything. In two or three sentences: how is a request authenticated in this service?",
            _watcher(calls2, said2),
        )
    finally:
        await second.close()
    answer = "\n".join(said2).lower()
    _log({"step": "reuse", "calls": calls2, "answer": answer[:600]})
    print(f"\nREUSE: {len(calls2)} tool calls: {calls2}")
    assert any(call.startswith("knowledge_search") for call in calls2), (
        f"the topics were not consulted: {calls2}"
    )
    assert "jwt" in answer

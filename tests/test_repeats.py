"""HW1: a repeated call is answered with a fact. The ledger alone, then a real SessionHost with a mocked model."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path

import httpx2

from forge.agent.repeats import MAX_ENTRIES_PER_KEY, MAX_KEYS, Entry, RepeatLedger, call_key, digest_of
from forge.context.compaction import STUB_PREFIX, pairs_are_valid
from forge.engine.session_host import SessionHost
from forge.llm.base import Message
from forge.protocol.events import EventBus, EventType
from forge.protocol.inputs import SendMessage
from forge.safety.redact import Redactor
from forge.workspace.create import create_workspace
from tests.helpers import function_call_output, mocked_router, reply, responses_body, text_output

BIG = "backend/big_module.py"
BIG_TEXT = "".join(f"def function_number_{n}():\n    return {n}\n" for n in range(60))
SMALL = "backend/small_module.py"
FINAL = "All done here."


def test_the_ledger_finds_an_earlier_entry_with_the_same_digest_only() -> None:
    ledger = RepeatLedger()
    key = call_key("read_file", {"path": "a.py", "offset": 1})
    assert key == call_key("read_file", {"offset": 1, "path": "a.py"})  # argument order does not matter
    ledger.add(key, Entry(1, "c1", digest_of("one"), True))
    ledger.add(key, Entry(2, "c2", digest_of("two"), True))
    ledger.add(key, Entry(3, "c3", digest_of("one"), True))

    assert ledger.seen(key, digest_of("one")) == Entry(3, "c3", digest_of("one"), True)
    assert ledger.first(key, digest_of("one")) == Entry(1, "c1", digest_of("one"), True)
    assert ledger.count(key, digest_of("one")) == 2
    assert ledger.seen(key, digest_of("other")) is None
    assert ledger.count(call_key("grep", {}), digest_of("one")) == 0


def test_the_ledger_is_bounded() -> None:
    ledger = RepeatLedger()
    for step in range(MAX_ENTRIES_PER_KEY + 5):
        ledger.add("k", Entry(step, f"c{step}", digest_of("x"), True))
    assert ledger.count("k", digest_of("x")) == MAX_ENTRIES_PER_KEY
    assert ledger.first("k", digest_of("x")) == Entry(
        5, "c5", digest_of("x"), True
    )  # the oldest were dropped

    for number in range(MAX_KEYS + 3):
        ledger.add(f"key{number}", Entry(number, "c", digest_of("y"), True))
    assert ledger.count("k", digest_of("x")) == 0  # the oldest key went first
    assert ledger.count(f"key{MAX_KEYS + 2}", digest_of("y")) == 1


async def _run(
    original_repo: Path,
    tmp_path: Path,
    steps: list[tuple[str, str]],
    between: Callable[[int, SessionHost], None] | None = None,
    setup: Callable[[SessionHost], None] | None = None,
) -> SessionHost:
    """The mocked model makes the tool calls in `steps` one per model call, then answers FINAL."""
    host: SessionHost | None = None
    calls: list[int] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        json.loads(request.content)
        index = len(calls)
        calls.append(index)
        if between is not None and host is not None:
            between(index, host)
        if index < len(steps):
            name, arguments = steps[index]
            return reply(request, responses_body([function_call_output(name, arguments, f"call_{index}")]))
        return reply(request, responses_body([text_output(FINAL)]))

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    (workspace.path_of(BIG)).write_text(BIG_TEXT, encoding="utf-8")
    (workspace.path_of(SMALL)).write_text("VALUE = 1\n", encoding="utf-8")
    host = SessionHost(mocked_router(handler), EventBus(redactor=Redactor()), workspace=workspace)
    if setup is not None:
        setup(host)
    runner = asyncio.create_task(host.run())
    await host.submit(SendMessage(text="Look at the module."))
    for _ in range(200):
        await asyncio.sleep(0.05)
        if host.history[-1].role == "assistant" and host.history[-1].content == FINAL:
            break
    await asyncio.sleep(0.4)  # a reminder after the first answer would make the model answer again
    runner.cancel()
    return host


def _tool_texts(host: SessionHost) -> list[str]:
    return [m.content for m in host.history if m.role == "tool"]


def _finished(host: SessionHost) -> list[dict[str, object]]:
    return [e.payload for e in host.bus.events_since(0) if e.type == EventType.TOOL_CALL_FINISHED]


READ_BIG = ("read_file", json.dumps({"path": BIG}))


async def test_a_second_identical_read_is_answered_with_a_pointer(
    original_repo: Path, tmp_path: Path
) -> None:
    host = await _run(original_repo, tmp_path, [READ_BIG, READ_BIG])

    first, second = _tool_texts(host)
    assert "function_number_59" in first
    assert second.startswith("[Same result as your identical call at step 1:")
    assert "function_number_59" not in second
    finished = _finished(host)
    assert "repeat_of" not in finished[0] and finished[1]["repeat_of"] == 1
    assert "function_number_26" in str(finished[1]["preview"])  # the event keeps the real preview
    assert pairs_are_valid(host.history)


async def test_a_third_read_points_to_the_first_whole_result(original_repo: Path, tmp_path: Path) -> None:
    host = await _run(original_repo, tmp_path, [READ_BIG, READ_BIG, READ_BIG])

    texts = _tool_texts(host)
    assert texts[2].startswith("[Same result as your identical call at step 1:")
    assert [p.get("repeat_of") for p in _finished(host)] == [None, 1, 1]


async def test_a_read_after_the_file_changed_is_whole_again(original_repo: Path, tmp_path: Path) -> None:
    def between(index: int, host: SessionHost) -> None:
        if index == 1:  # the file changes on disk before the second read
            host.workspace.path_of(BIG).write_text(BIG_TEXT + "CHANGED = True\n", encoding="utf-8")

    host = await _run(original_repo, tmp_path, [READ_BIG, READ_BIG], between)

    texts = _tool_texts(host)
    assert "CHANGED = True" in texts[1] and not texts[1].startswith("[Same result")
    assert "repeat_of" not in _finished(host)[1]


async def test_a_read_whose_first_result_was_trimmed_is_whole_again(
    original_repo: Path, tmp_path: Path
) -> None:
    def between(index: int, host: SessionHost) -> None:
        if index == 1:  # compaction replaced the first result with a stub
            for position, message in enumerate(host.history):
                if message.role == "tool":
                    host.history[position] = message.model_copy(
                        update={"content": STUB_PREFIX + "read_file] gone"}
                    )

    host = await _run(original_repo, tmp_path, [READ_BIG, READ_BIG], between)

    assert "function_number_59" in _tool_texts(host)[1]
    assert "repeat_of" not in _finished(host)[1]


async def test_the_third_identical_short_answer_carries_a_note(original_repo: Path, tmp_path: Path) -> None:
    read_small = ("read_file", json.dumps({"path": SMALL}))
    host = await _run(original_repo, tmp_path, [read_small, read_small, read_small])

    texts = _tool_texts(host)
    assert "[note:" not in texts[0] and "[note:" not in texts[1]  # short results are never pointers
    assert "the same call with the same answer for the 3th time (first at step 1)" in texts[2]
    assert "try another way" in texts[2] and "read_background" not in texts[2]
    assert _finished(host)[2]["repeat_of"] == 1


async def test_todo_write_with_the_same_list_says_so_and_sends_one_event(
    original_repo: Path, tmp_path: Path
) -> None:
    todos = ("todo_write", json.dumps({"todos": [{"content": "step one", "status": "in_progress"}]}))
    host = await _run(original_repo, tmp_path, [todos, todos])

    first, second = _tool_texts(host)
    assert first.startswith("Todo list updated")
    assert second.startswith("The todo list is unchanged")
    assert sum(1 for e in host.bus.events_since(0) if e.type == EventType.TODO_UPDATED) == 1


def test_messages_stay_valid_pairs_helper_sees_plain_messages() -> None:
    assert pairs_are_valid([Message.system("s"), Message.user("u")])

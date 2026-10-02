"""M4: context management guarantees (spec §10.7). The summariser here is a deterministic function:
these tests check budgeting and message integrity, not the model (DECISIONS D-008, D-052)."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from forge.config import ForgeConfig
from forge.context.budget import ContextBudget
from forge.context.compaction import (
    REQUIRED_SECTIONS,
    emergency_trim,
    micro_compact,
    pairs_are_valid,
    split_for_summary,
    summary_is_valid,
)
from forge.context.manager import ContextManager
from forge.context.pinned import PinnedBlocks
from forge.llm.base import Message, ToolCall, ToolSpec
from forge.llm.tokens import count_text_tokens, head_and_tail
from forge.toolkit.base import ToolContext
from forge.tools.files import ReadFile
from forge.workspace.create import create_workspace
from tests.helpers import default_config, mocked_router

TOOLS = [
    ToolSpec(name="read_file", description="Read a file", parameters={"type": "object", "properties": {}})
]
VALID_SUMMARY = "\n\n".join(f"{section}\nNone." for section in REQUIRED_SECTIONS)


def small_window_config(context_window: int = 16_000, max_output: int = 2_000) -> ForgeConfig:
    config = default_config()
    for key in ("gpt51", "gpt41"):
        model = config.llm.models[key]
        config.llm.models[key] = model.model_copy(
            update={"context_window": context_window, "max_output": max_output}
        )
    return config


def unreachable(request: object) -> object:
    raise AssertionError("no LLM call expected")


def manager_with(config: ForgeConfig, summariser: object = None) -> ContextManager:
    router = mocked_router(unreachable)  # type: ignore[arg-type]
    router.config = config

    async def summarise(prompt: str) -> str:
        return VALID_SUMMARY

    return ContextManager(router, config, summarise=summariser or summarise)  # type: ignore[arg-type]


def words(tokens: int, seed: int = 0) -> str:
    rng = random.Random(seed)
    vocabulary = ["claim", "policy", "export", "service", "repository", "route", "schema", "test", "error"]
    return " ".join(rng.choice(vocabulary) for _ in range(tokens))


def tool_turn(index: int, output_tokens: int) -> list[Message]:
    call = ToolCall(
        id=f"call_{index}",
        name="read_file",
        raw_arguments=f'{{"path": "f{index}.py"}}',
        arguments={"path": f"f{index}.py"},
    )
    output, tail, _ = head_and_tail(words(output_tokens, index), 6000)  # the loop caps results
    return [
        Message(role="assistant", content="", tool_calls=[call]),
        Message.tool_result(call.id, output + tail),
    ]


# --- budget and pinned ---


def test_usable_budget_follows_spec_formula() -> None:
    budget = ContextBudget(default_config().llm.models["gpt51"], default_config().context)

    assert budget.usable == 272_000 - 32_000 - int(0.05 * 272_000)
    assert budget.pinned_cap == int(budget.usable * 0.08)


def test_calibration_scales_estimates_within_limits() -> None:
    budget = ContextBudget(default_config().llm.models["gpt51"], default_config().context)
    messages = [Message.user(words(1000))]
    raw = budget.estimate(messages, [])

    budget.calibrate(raw, int(raw * 1.3))
    assert budget.estimate(messages, []) == pytest.approx(raw * 1.3, rel=0.01)
    budget.calibrate(raw, raw * 10)
    assert budget.calibration == 2.0


def test_pinned_blocks_keep_priority_order_and_respect_the_cap() -> None:
    pinned = PinnedBlocks()
    pinned.set("memory_index", words(2000, 1))
    pinned.set("requirement", "Add a CSV export endpoint for claims.")
    pinned.set("files_modified", "backend/claims_app/api/claims/routes.py")

    text = pinned.render(cap_tokens=300)

    assert count_text_tokens(text) <= 300
    assert text.index("Requirement") < text.index("Files modified")
    assert "Add a CSV export endpoint for claims." in text  # highest priority survives intact
    assert "shortened to fit" in text


# --- pure compaction helpers ---


def test_pair_validation() -> None:
    good = [
        Message.system("s"),
        Message.user("u"),
        *tool_turn(1, 10),
        Message(role="assistant", content="done"),
    ]
    orphan = [Message.system("s"), Message.tool_result("nope", "x")]
    unanswered = [Message.system("s"), Message.user("u"), tool_turn(2, 10)[0], Message.user("again")]

    assert pairs_are_valid(good)
    assert not pairs_are_valid(orphan)
    assert not pairs_are_valid(unanswered)


def test_micro_compaction_stubs_old_results_only() -> None:
    history = [Message.system("s"), Message.user("u")]
    for index in range(12):
        history += tool_turn(index, 300)
    history[2] = history[2].model_copy(
        update={"provider_items": [{"type": "reasoning"}], "provider_items_model": "gpt51"}
    )

    stubbed = micro_compact(history, keep_recent=8)

    results = [m for m in history if m.role == "tool"]
    assert stubbed == 4
    assert all(m.content.startswith("[Output of read_file") for m in results[:4])
    assert all(not m.content.startswith("[Output of") for m in results[4:])
    assert history[2].provider_items is None
    assert pairs_are_valid(history)


def test_split_cuts_at_a_user_message() -> None:
    history = [Message.system("s")]
    for turn in range(8):
        history += [Message.user(f"u{turn}"), *tool_turn(turn, 10)]

    _older, recent = split_for_summary(history, keep_recent_steps=6)

    # 6 steps = the last 3 turns (each: user message + assistant step with its result)
    assert recent[0].role == "user" and recent[0].content == "u5"
    assert pairs_are_valid([history[0], *recent])


def test_split_inside_one_long_turn_keeps_the_request() -> None:
    history = [Message.system("s"), Message.user("Add the export endpoint.")]
    for step in range(20):
        history += tool_turn(step, 10)

    _older, recent = split_for_summary(history, keep_recent_steps=6)

    assert recent[0].content == "Add the export endpoint."  # the task statement is always kept
    assert [m.role for m in recent[1:3]] == ["assistant", "tool"]
    assert len([m for m in recent if m.role == "assistant"]) == 6
    assert pairs_are_valid([history[0], *recent])


def test_summary_validation() -> None:
    assert summary_is_valid(VALID_SUMMARY)
    assert not summary_is_valid("## Goal, phase, task and definition of done\nstuff")


def test_emergency_trim_keeps_last_two_turns() -> None:
    history = [Message.system("s")]
    for turn in range(5):
        history += [Message.user(f"u{turn}"), *tool_turn(turn, 50)]

    trimmed = emergency_trim(history)

    assert [m.content for m in trimmed if m.role == "user"] == ["u4"]
    assert pairs_are_valid(trimmed)


# --- the manager ---


async def test_stress_500_tool_calls_never_exceed_the_window() -> None:
    config = small_window_config()
    manager = manager_with(config)
    budget = manager.budget()
    history: list[Message] = [Message.system("You are Forge.")]
    rng = random.Random(7)
    worst = 0

    for index in range(500):
        if index % 10 == 0:
            history.append(Message.user(f"Step {index}: keep going."))
        history += tool_turn(index, rng.choice([200, 800, 2500, 7000]))
        messages = await manager.prepare(history, TOOLS)
        used = budget.estimate(messages, TOOLS)
        worst = max(worst, used)
        assert used <= budget.usable, f"request {index} is {used} > {budget.usable}"
        assert pairs_are_valid(history), f"pairs broken at {index}"
        assert all(count_text_tokens(m.content) <= 6000 + 50 for m in history if m.role == "tool")

    assert manager.compactions > 0
    assert manager.pinned.get("compaction_summary") == VALID_SUMMARY
    assert worst > budget.usable * 0.5  # the test really pushed the window


async def test_invalid_summary_twice_keeps_history(tmp_path: Path) -> None:
    calls: list[str] = []

    async def bad(prompt: str) -> str:
        calls.append(prompt)
        return "## Goal, phase, task and definition of done\nPartial."

    manager = manager_with(small_window_config(), bad)
    history = [Message.system("s")] + [
        m for t in range(10) for m in (Message.user(f"u{t}"), *tool_turn(t, 20))
    ]
    before = list(history)

    assert await manager.compact(history) is False
    assert history == before and len(calls) == 2
    assert "Include EVERY heading" in calls[1]


async def test_large_older_history_is_summarised_in_chunks() -> None:
    prompts: list[str] = []

    async def counting(prompt: str) -> str:
        prompts.append(prompt)
        return VALID_SUMMARY

    config = small_window_config()
    config.llm.models["gpt51"] = config.llm.models["gpt51"].model_copy(update={"context_window": 4000})
    manager = manager_with(config, counting)
    history = [Message.system("s")] + [
        m for t in range(20) for m in (Message.user(f"u{t}"), *tool_turn(t, 600))
    ]

    assert await manager.compact(history)
    assert len(prompts) > 1
    assert "merge it into your summary" in prompts[1]  # each chunk builds on the previous summary
    assert [m.content for m in history if m.role == "user"] == [f"u{t}" for t in range(17, 20)]


async def test_force_fit_handles_a_single_enormous_message() -> None:
    manager = manager_with(small_window_config())
    history = [Message.system("s"), Message.user(words(40_000))]

    messages = await manager.prepare(history, TOOLS)

    assert manager.budget().estimate(messages, TOOLS) <= manager.budget().usable
    assert "cut to fit the context window" in history[-1].content


async def test_emergency_after_provider_rejection() -> None:
    manager = manager_with(small_window_config())
    history = [Message.system("s")] + [
        m for t in range(6) for m in (Message.user(f"u{t}"), *tool_turn(t, 30))
    ]

    await manager.emergency(history)

    assert [m.content for m in history if m.role == "user"] == ["u5"]


def test_task_reset_keeps_system_prompt_and_brief() -> None:
    manager = manager_with(small_window_config())
    history = [Message.system("sys"), Message.user("old"), *tool_turn(1, 10)]

    manager.reset_for_task(history, "Task 3: add the service.", "Task 2 added the repository function.")

    assert [m.role for m in history] == ["system", "user"]
    assert "Handoff from the previous task" in history[1].content


async def test_files_larger_than_the_budget_stay_readable_in_ranges(
    original_repo: Path, tmp_path: Path
) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    big = workspace.path_of("backend/huge_log.txt")
    big.write_text("\n".join(f"line {n}: {words(12, n)}" for n in range(1, 20_001)), encoding="utf-8")
    context = ToolContext(workspace=workspace, tool_cap_tokens=6000)

    first = await ReadFile().run(ReadFile.Args(path="backend/huge_log.txt"), context)
    capped, saved = context.cap_output(first.content)
    last = await ReadFile().run(ReadFile.Args(path="backend/huge_log.txt", offset=19_990, limit=20), context)

    assert count_text_tokens(capped) <= 6000 + 100 and saved is not None
    assert "read it in ranges with read_file offset/limit" in capped
    assert "line 20000:" in last.content and count_text_tokens(last.content) < 1000


async def test_no_compaction_storm() -> None:
    """Near the threshold, a summary must not run on every call (D-055 cooldown)."""
    calls: list[int] = []

    async def counting(prompt: str) -> str:
        calls.append(1)
        return VALID_SUMMARY

    manager = manager_with(small_window_config(), counting)
    history: list[Message] = [Message.system("s"), Message.user("One long task.")]
    for index in range(300):
        history += tool_turn(index, 900)
        await manager.prepare(history, TOOLS)

    steps = 300
    assert 0 < manager.compactions <= steps // manager.config.context.keep_recent_turns + 1
    assert len(calls) == manager.compactions  # one summary call per compaction (all valid)

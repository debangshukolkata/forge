from __future__ import annotations

import pytest

from forge.errors import BudgetExceededError
from forge.llm.base import Message, ToolCall, ToolSpec, Usage
from forge.llm.cost import CostTracker, format_money
from forge.llm.tokens import count_message_tokens, count_request_tokens, count_text_tokens
from tests.helpers import default_config


def test_text_token_counts() -> None:
    assert count_text_tokens("") == 0
    assert count_text_tokens("hello world") == 2


def test_message_count_includes_tool_calls_and_overhead() -> None:
    plain = Message(role="assistant", content="ok")
    with_call = Message(
        role="assistant",
        content="ok",
        tool_calls=[ToolCall(id="1", name="read_file", raw_arguments='{"path":"x"}')],
    )

    assert count_message_tokens(with_call) > count_message_tokens(plain) > count_text_tokens("ok")


def test_request_count_includes_tool_schemas() -> None:
    messages = [Message.user("hi")]
    tool = ToolSpec(
        name="read_file", description="Read a file from the workspace", parameters={"type": "object"}
    )

    assert count_request_tokens(messages, [tool]) > count_request_tokens(messages)


def test_cost_uses_cached_input_price() -> None:
    config = default_config()
    tracker = CostTracker(config.llm.models, budget_usd=10)
    usage = Usage(input_tokens=1_000_000, cached_input_tokens=400_000, output_tokens=100_000)

    cost = tracker.record("gpt51", "coder", usage)

    # 600k uncached * $1.25 + 400k cached * $0.125 + 100k out * $10, per million
    assert cost == pytest.approx(0.75 + 0.05 + 1.0)
    assert tracker.cost_by_role["coder"] == pytest.approx(1.8)


def test_budget_cap_blocks_until_raised() -> None:
    tracker = CostTracker(default_config().llm.models, budget_usd=1.0)
    tracker.record("gpt51", "coder", Usage(output_tokens=200_000))  # $2

    with pytest.raises(BudgetExceededError):
        tracker.check_budget()
    tracker.raise_budget(5.0)
    tracker.check_budget()


def test_a_zero_budget_means_no_cap_and_is_the_default() -> None:
    config = default_config()
    assert config.limits.session_budget_usd == 0 and config.llm.role_reasoning_effort == {}
    tracker = CostTracker(config.llm.models, budget_usd=0)
    tracker.record("gpt51", "coder", Usage(output_tokens=50_000_000))  # $500
    tracker.check_budget()  # accuracy and speed come before token cost (D-161)


def test_money_display() -> None:
    config = default_config().cost
    assert format_money(1.5, config) == "$1.5000"
    assert format_money(1.0, config.model_copy(update={"display_currency": "INR"})) == "₹88.00"


def test_calls_are_filed_under_phase_and_task_and_persist(tmp_path) -> None:  # type: ignore[no-untyped-def]
    # D-118: tokens and cost per phase and task, kept in the project so they add up across sessions.
    from forge.llm.usage_ledger import UsageLedger

    config = default_config()
    tracker = CostTracker(config.llm.models, 20.0)
    model = next(iter(config.llm.models))
    tracker.ledger = UsageLedger(tmp_path / "usage.json")
    where = {"value": ("clarify", None)}
    tracker.where = lambda: where["value"]  # type: ignore[assignment,return-value]
    tracker.record(model, "coder", Usage(input_tokens=1000, output_tokens=100))
    where["value"] = ("execute", "T1")
    tracker.record(model, "coder", Usage(input_tokens=5000, output_tokens=500))
    tracker.record(model, "reviewer", Usage(input_tokens=2000, output_tokens=200))

    project = tracker.summary()["project"]
    assert project["by_phase"]["clarify"]["input_tokens"] == 1000
    assert project["by_phase"]["execute"]["calls"] == 2 and project["by_task"]["T1"]["output_tokens"] == 700
    assert project["total"]["calls"] == 3
    assert abs(project["total"]["cost_usd"] - round(tracker.total_usd, 6)) < 1e-6

    reopened = UsageLedger(tmp_path / "usage.json")  # a later session of the same project
    assert reopened.summary()["by_task"]["T1"]["calls"] == 2

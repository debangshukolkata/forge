"""D-360: the speed changes modelled on Claude Code: batching in the system prompt, one critic round unless something blocks, an idle limit on streams."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from forge.subagents import spawn_tool
from forge.subagents.critic import has_blocking_fix
from forge.subagents.spawn_tool import SpawnSubagent
from forge.toolkit.base import ToolContext
from forge.workflow.orchestrator import critic_cleared
from forge.workspace.create import create_workspace

REVISE_NO_BLOCK = """SCORES: Hierarchy 4, Consistency 4, Polish 3, Typography 4, States n/a, Responsive 4, Distinctiveness 3
BIGGEST GAP: the hero art is generic.
FIXES (most valuable first, at most 7):
1. hero: the illustration is generic -> draw a lab bench scene
2. footer: low contrast -> use #444
WHAT WORKS: spacing is calm.
VERDICT: REVISE (there is no BLOCKING fix, only suggestions)"""

REVISE_BLOCKING = """SCORES: Hierarchy 2, Consistency 3
BIGGEST GAP: the price table is cut off at 375 px.
FIXES:
1. BLOCKING table: sideways scroll at 375 px -> wrap the table in overflow-x:auto
2. footer: low contrast -> use #444
VERDICT: REVISE"""


def test_a_blocking_fix_is_a_fix_line_that_starts_with_the_word_not_the_word_in_a_sentence() -> None:
    assert has_blocking_fix(REVISE_BLOCKING)
    assert has_blocking_fix("FIXES:\n- **BLOCKING** header: text unreadable -> #111")
    assert not has_blocking_fix(REVISE_NO_BLOCK)
    assert not has_blocking_fix("There is nothing blocking here.\nVERDICT: REVISE")


@pytest.mark.parametrize("report, cleared", [(REVISE_NO_BLOCK, True), (REVISE_BLOCKING, False)])
async def test_one_critic_round_is_enough_unless_a_fix_blocks(
    report: str, cleared: bool, original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_subagent(*args: Any, **kwargs: Any) -> str:
        return report

    monkeypatch.setattr(spawn_tool, "_run_subagent", fake_subagent)
    context = ToolContext(
        workspace=create_workspace(original_repo, tmp_path / "ws", "backend"), router=object()
    )  # type: ignore[arg-type]
    context.last_ui_edit_step = 1
    result = await SpawnSubagent().run(
        SpawnSubagent.Args(agent="design-critic", task="Review http://localhost:5173"), context
    )
    assert result.ok and critic_cleared(context) is cleared
    assert ("no second review is needed" in result.content) is cleared


def test_the_system_prompt_asks_for_batched_steps_and_one_shot_writes() -> None:
    prompt = (
        Path(__file__).resolve().parent.parent / "src" / "forge" / "agent" / "prompts" / "system.md"
    ).read_text(encoding="utf-8")
    assert (
        "in the SAME step" in prompt
        and "todo_write" in prompt
        and "one multi_edit" in prompt
        and "Start a dev server once" in prompt
    )


async def test_streamed_answers_use_an_idle_limit_not_the_long_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from forge.config import AzureProviderConfig, ModelConfig, Secrets
    from forge.llm.azure_openai import AzureOpenAIProvider

    secrets = Secrets(
        {
            "AZURE_OPENAI_ENDPOINT": "https://x.openai.azure.com/",
            "AZURE_OPENAI_API_KEY": "k",
            "AZURE_OPENAI_API_VERSION": "2025-04-01-preview",
            "DEP": "d",
        },
        None,
    )  # check_secrets: fake
    model = ModelConfig(label="t", deployment_env="DEP", context_window=1000, max_output=100)
    provider = AzureOpenAIProvider("t", model, AzureProviderConfig(), secrets)
    assert AzureProviderConfig().stream_idle_s == 100.0 and AzureProviderConfig().timeout_s == 180.0
    seen: dict[str, Any] = {}

    class Stop(Exception):
        pass

    async def fake_create(**kwargs: Any) -> Any:
        seen.update(kwargs)
        raise Stop

    monkeypatch.setattr(provider._client.responses, "create", fake_create)
    with pytest.raises(Stop):
        await provider._stream_responses({"model": "d", "input": []}, lambda text: None)  # type: ignore[arg-type, return-value]
    assert seen["timeout"] == 100.0 and seen["stream"] is True


async def test_a_streamed_call_reports_what_it_is_doing_and_how_much(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-361: thinking, then a big tool call (a whole file as arguments): the screen can say so instead of showing a bare timer."""
    from types import SimpleNamespace

    from forge.config import AzureProviderConfig, ModelConfig, Secrets
    from forge.llm import base
    from forge.llm.azure_openai import AzureOpenAIProvider

    secrets = Secrets(
        {
            "AZURE_OPENAI_ENDPOINT": "https://x.openai.azure.com/",
            "AZURE_OPENAI_API_KEY": "k",
            "AZURE_OPENAI_API_VERSION": "2025-04-01-preview",
            "DEP": "d",
        },
        None,
    )  # check_secrets: fake
    provider = AzureOpenAIProvider(
        "t",
        ModelConfig(label="t", deployment_env="DEP", context_window=1000, max_output=100),
        AzureProviderConfig(),
        secrets,
    )
    monkeypatch.setattr(base.StreamProgress, "INTERVAL_S", 0.0)
    final = SimpleNamespace(
        model_dump=lambda exclude_none=True: {
            "output": [],
            "usage": {"input_tokens": 1, "output_tokens": 1},
            "model": "d",
        }
    )
    events = [
        SimpleNamespace(type="response.output_item.added", item=SimpleNamespace(type="reasoning")),
        SimpleNamespace(type="response.reasoning_summary_text.delta", delta="Comparing the three layouts"),
        SimpleNamespace(
            type="response.output_item.added", item=SimpleNamespace(type="function_call", name="write_file")
        ),
        SimpleNamespace(type="response.function_call_arguments.delta", delta="a" * 500),
        SimpleNamespace(type="response.function_call_arguments.delta", delta="b" * 700),
        SimpleNamespace(type="response.completed", response=final),
    ]

    async def fake_stream() -> Any:
        for event in events:
            yield event

    async def fake_create(**kwargs: Any) -> Any:
        return fake_stream()

    monkeypatch.setattr(provider._client.responses, "create", fake_create)
    seen: list[dict[str, Any]] = []

    async def progress(info: dict[str, Any]) -> None:
        seen.append(info)

    async def delta(text: str) -> None:
        return None

    await provider._stream_responses({"model": "d", "input": []}, delta, None, progress)
    assert seen[0]["stage"] == "waiting"
    assert any(s["stage"] == "thinking" and "Comparing the three layouts" in s["snippet"] for s in seen)
    calling = [s for s in seen if s["stage"] == "calling"]
    assert calling and calling[-1]["tool"] == "write_file" and calling[-1]["chars"] == 1200


def test_prompts_and_design_skill_tell_the_model_to_build_variants_side_by_side() -> None:
    """D-362: three designs were built one after another although parallel builders existed; the instruction must be a rule, not a 'can'."""
    root = Path(__file__).resolve().parents[1] / "src" / "forge"
    for relative in ("agent/prompts/system.md", "agent/prompts/system_modeb.md"):
        text = (root / relative).read_text(encoding="utf-8")
        assert "built at the same time, not one after" in text
    skill = (root / "skills/ui-design-quality/SKILL.md").read_text(encoding="utf-8")
    assert "Build the variants at the same time" in skill

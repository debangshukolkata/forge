"""D-380: build_variants starts one builder per variant at the same time, within the limit, and refuses overlapping folders."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from forge.subagents import variants_tool
from forge.subagents.variants_tool import BuildVariants, Variant
from forge.toolkit.base import ToolContext
from forge.workspace.create import create_workspace


def make_context(original_repo: Path, tmp_path: Path, limit: int) -> ToolContext:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    router = SimpleNamespace(config=SimpleNamespace(limits=SimpleNamespace(max_parallel_builders=limit)))
    return ToolContext(workspace=workspace, router=router)


def args(count: int = 3, folders: list[str] | None = None) -> BuildVariants.Args:
    names = "abcdef"
    return BuildVariants.Args(
        brief="Three designs of the Pulse home screen.",
        variants=[
            Variant(
                name=names[i],
                folder=(folders or [f"designs/design-{names[i]}" for i in range(count)])[i],
                direction=f"direction {names[i]}",
            )
            for i in range(count)
        ],
    )


async def test_the_builders_run_together_up_to_the_limit_and_see_the_others_directions(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    running = peak = 0
    briefs: dict[str, str] = {}

    async def fake_builder(
        context: ToolContext, *, folder: str, name: str, task: str
    ) -> tuple[str, str, str]:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        briefs[name] = task
        await asyncio.sleep(0.15)
        context.workspace.path_of(folder).mkdir(parents=True, exist_ok=True)
        (context.workspace.path_of(folder) / "index.html").write_text("<h1>x</h1>", encoding="utf-8")
        running -= 1
        return "DONE", f"built {name}\nSTATUS: DONE", f".forge/builders/{name}-report.md"

    monkeypatch.setattr(variants_tool, "run_builder", fake_builder)
    context = make_context(original_repo, tmp_path, limit=3)
    context.step = 4
    result = await BuildVariants().run(args(3), context)
    assert result.ok and peak == 3 and "[builder a in designs/design-a: DONE]" in result.content
    assert (
        "direction b" in briefs["a"]
        and "direction c" in briefs["a"]
        and "direction a" not in briefs["a"].split("The other variants")[1]
    )
    assert "your own DESIGN.md" in briefs["b"]
    assert (
        context.last_ui_edit_step == 4
    )  # the pages count as unverified edits, so the browser and critic gates apply

    peak = 0
    narrow = make_context(original_repo, tmp_path / "second", limit=2)
    done = await BuildVariants().run(args(3), narrow)
    assert done.ok and peak == 2  # at most the configured number at once, the rest wait their turn
    one_at_a_time = make_context(original_repo, tmp_path / "third", limit=1)
    peak = 0
    await BuildVariants().run(args(2), one_at_a_time)
    assert peak == 1


async def test_overlapping_or_unusable_folders_and_duplicate_names_are_refused(
    original_repo: Path, tmp_path: Path
) -> None:
    context = make_context(original_repo, tmp_path, limit=3)
    overlap = await BuildVariants().run(args(2, ["designs/a", "designs/a/inner"]), context)
    assert not overlap.ok and "overlap" in overlap.content
    outside = await BuildVariants().run(args(2, ["designs/a", "../elsewhere"]), context)
    assert not outside.ok and "below the repository root" in outside.content
    twin = BuildVariants.Args(
        brief="x",
        variants=[
            Variant(name="A", folder="d/a", direction="one"),
            Variant(name="a", folder="d/b", direction="two"),
        ],
    )
    assert not (await BuildVariants().run(twin, context)).ok


def test_the_tool_is_offered_and_the_prompts_name_it() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "forge"
    for relative in ("agent/prompts/system.md", "agent/prompts/system_modeb.md"):
        assert "call build_variants" in (root / relative).read_text(encoding="utf-8")
    assert "call `build_variants`" in (root / "skills/ui-design-quality/SKILL.md").read_text(encoding="utf-8")
    assert BuildVariants.name == "build_variants" and BuildVariants.read_only is True
    _: Any = None

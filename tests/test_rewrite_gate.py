"""D-410: replacing most of an existing source file in one step is refused once until a test has been written."""

from __future__ import annotations

from pathlib import Path

from forge.toolkit.base import ToolContext
from forge.tools.files import WriteFile
from forge.workspace.create import create_workspace


def context_for(original_repo: Path, tmp_path: Path) -> ToolContext:
    context = ToolContext(
        workspace=create_workspace(original_repo, tmp_path / "ws", "backend"),
        design_first=False,
        require_baseline=True,
    )
    context.baseline_checked = True  # the tests have run; the rewrite reminder is separate
    return context


def module(prefix: str, factor: str) -> str:
    lines: list[str] = []
    for number in range(20):
        lines += [f"def {prefix}_{number}(value):", f"    return value {factor} {number}", ""]
    return chr(10).join(lines) + chr(10)


def seed(context: ToolContext, text: str) -> None:
    context.workspace.write_text("pricing_rules.py", text, "seed")
    context.reads.record("pricing_rules.py", (context.workspace.repo_dir / "pricing_rules.py").read_bytes())


async def test_replacing_most_of_a_file_is_refused_once(original_repo: Path, tmp_path: Path) -> None:
    context = context_for(original_repo, tmp_path)
    seed(context, module("rule", "+"))
    rewritten = module("step", "*")
    first = await WriteFile().run(WriteFile.Args(path="pricing_rules.py", content=rewritten), context)
    assert not first.ok and "replaces most of an existing file" in first.content
    second = await WriteFile().run(WriteFile.Args(path="pricing_rules.py", content=rewritten), context)
    assert second.ok  # one reminder only


async def test_a_small_change_is_not_a_rewrite(original_repo: Path, tmp_path: Path) -> None:
    context = context_for(original_repo, tmp_path)
    seed(context, module("rule", "+"))
    nudged = module("rule", "+").replace("value + 3", "value + 33")
    assert (await WriteFile().run(WriteFile.Args(path="pricing_rules.py", content=nudged), context)).ok


async def test_a_written_test_clears_it(original_repo: Path, tmp_path: Path) -> None:
    context = context_for(original_repo, tmp_path)
    seed(context, module("rule", "+"))
    test_text = "def test_x():" + chr(10) + "    assert True" + chr(10)
    await WriteFile().run(WriteFile.Args(path="tests/test_rules.py", content=test_text), context)
    assert context.tests_pinned
    result = await WriteFile().run(
        WriteFile.Args(path="pricing_rules.py", content=module("step", "*")), context
    )
    assert result.ok


async def test_a_short_file_is_not_held_up(original_repo: Path, tmp_path: Path) -> None:
    context = context_for(original_repo, tmp_path)
    context.workspace.write_text("tiny.py", "VALUE = 1" + chr(10), "seed")
    context.reads.record("tiny.py", (context.workspace.repo_dir / "tiny.py").read_bytes())
    assert (await WriteFile().run(WriteFile.Args(path="tiny.py", content="OTHER = 2" + chr(10)), context)).ok

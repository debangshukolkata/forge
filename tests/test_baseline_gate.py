"""D-408: the first change to existing source code is refused once until the existing tests have run or a test has been written."""

from __future__ import annotations

from pathlib import Path

from forge.toolkit.base import ToolContext
from forge.tools.baseline_gate import is_test_file
from forge.tools.files import WriteFile
from forge.workspace.create import create_workspace


def context_for(original_repo: Path, tmp_path: Path) -> ToolContext:
    return ToolContext(
        workspace=create_workspace(original_repo, tmp_path / "ws", "backend"),
        design_first=False,
        require_baseline=True,  # a real session sets this; tests that build their own context are not held up by it
    )


def an_existing_source_file(context: ToolContext) -> tuple[str, str]:
    found = next(
        p for p in context.workspace.repo_dir.rglob("*.py") if "test" not in p.name and ".venv" not in p.parts
    )
    relative = found.relative_to(context.workspace.repo_dir).as_posix()
    context.reads.record(relative, found.read_bytes())  # the file tools want a file read before it is changed
    return relative, context.workspace.read_text(relative)[0]


async def test_the_first_edit_of_existing_code_is_refused_once_then_allowed(
    original_repo: Path, tmp_path: Path
) -> None:
    context = context_for(original_repo, tmp_path)
    relative, text = an_existing_source_file(context)
    first = await WriteFile().run(WriteFile.Args(path=relative, content=text + "\n# changed\n"), context)
    assert not first.ok and "run the existing tests" in first.content.lower()
    second = await WriteFile().run(WriteFile.Args(path=relative, content=text + "\n# changed\n"), context)
    assert second.ok  # one reminder, never a trap


async def test_a_test_run_clears_it(original_repo: Path, tmp_path: Path) -> None:
    context = context_for(original_repo, tmp_path)
    context.baseline_checked = True  # what a pytest command sets in the shell layer
    relative, text = an_existing_source_file(context)
    assert (await WriteFile().run(WriteFile.Args(path=relative, content=text + "\n#x\n"), context)).ok


async def test_writing_a_test_file_clears_it(original_repo: Path, tmp_path: Path) -> None:
    context = context_for(original_repo, tmp_path)
    relative, text = an_existing_source_file(context)
    made = await WriteFile().run(
        WriteFile.Args(path="tests/test_new_behaviour.py", content="def test_x():\n    assert True\n"),
        context,
    )
    assert made.ok and context.baseline_checked
    assert (await WriteFile().run(WriteFile.Args(path=relative, content=text + "\n#y\n"), context)).ok


async def test_a_new_file_is_never_refused(original_repo: Path, tmp_path: Path) -> None:
    context = context_for(original_repo, tmp_path)
    created = await WriteFile().run(
        WriteFile.Args(path="brand_new_module.py", content="VALUE = 1\n"), context
    )
    assert created.ok


def test_test_files_are_recognised_by_name_and_folder() -> None:
    assert is_test_file("tests/test_cart.py") and is_test_file("shop/tests/conftest.py")
    assert is_test_file("web/src/app.test.tsx")
    assert not is_test_file("shop/orders.py") and not is_test_file(
        "src/contest_rules.py".replace("contest", "orders")
    )


async def test_a_context_that_does_not_ask_for_a_baseline_is_never_held_up(
    original_repo: Path, tmp_path: Path
) -> None:
    context = context_for(original_repo, tmp_path)
    context.require_baseline = False
    relative, text = an_existing_source_file(context)
    changed = text + "\n#z\n"
    assert (await WriteFile().run(WriteFile.Args(path=relative, content=changed), context)).ok

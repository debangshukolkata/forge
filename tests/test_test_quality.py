"""C10 (D-309): weak tests are flagged, and a light mutation check finds what the tests do not notice."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

from forge.tools.test_quality import make_mutants, run_mutation_check, weak_test_findings

SOURCE = textwrap.dedent(
    """
    def clamp(value, low, high):
        if value < low:
            return low
        if value > high:
            return high
        return value


    def is_adult(age):
        return age >= 18 and age < 150
    """
)


def test_tests_that_cannot_fail_are_flagged(tmp_path: Path) -> None:
    code = textwrap.dedent(
        """
        from unittest.mock import patch

        def test_nothing_checked():
            result = 1 + 1

        def test_always_true():
            assert True

        def test_same_thing():
            value = compute()
            assert value == value

        def test_real():
            assert 1 + 1 == 2

        def test_raises():
            import pytest
            with pytest.raises(ValueError):
                int("x")

        @patch("a.b")
        @patch("a.c")
        def test_only_mocks(m1, m2):
            m1.return_value = 1
            mock = MagicMock()
            mock.run()
            assert m1
        """
    )
    path = tmp_path / "test_x.py"
    path.write_text(code, encoding="utf-8")
    found = "\n".join(weak_test_findings([path], tmp_path))
    assert "test_nothing_checked has no assertion" in found
    assert "assert True" in found and "compares an expression with itself" in found
    assert "test_real" not in found and "test_raises" not in found
    assert "test_only_mocks mocks 3 things" in found


def test_source_files_and_broken_files_are_left_alone(tmp_path: Path) -> None:
    source = tmp_path / "app.py"
    source.write_text("def test_looking_name(): pass\n", encoding="utf-8")
    broken = tmp_path / "test_bad.py"
    broken.write_text("def (:\n", encoding="utf-8")
    assert weak_test_findings([source, broken], tmp_path) == []


def test_mutants_are_small_single_changes() -> None:
    mutants = make_mutants(SOURCE, limit=20)
    descriptions = " | ".join(m.description for m in mutants)
    assert (
        "`Lt` to `GtE`" in descriptions
        and "`GtE` to `Lt`" in descriptions
        and "`And` to `Or`" in descriptions
    )
    assert "return None" in descriptions
    for mutant in mutants:
        compile(mutant.source, "<mutant>", "exec")  # every mutant is valid Python
        assert mutant.source != SOURCE.strip()


def test_the_tests_that_miss_an_edge_let_mutants_survive_and_the_file_is_restored(tmp_path: Path) -> None:
    module = tmp_path / "mathx.py"
    module.write_text(SOURCE, encoding="utf-8")
    (tmp_path / "test_mathx.py").write_text(
        textwrap.dedent(
            """
            from mathx import clamp, is_adult

            def test_middle_value():
                assert clamp(5, 0, 10) == 5

            def test_low():
                assert clamp(-3, 0, 10) == 0
            """
        ),
        encoding="utf-8",
    )
    tried, survivors = run_mutation_check(module, tmp_path, sys.executable, [])
    assert tried >= 4 and survivors  # nothing tests `high` or is_adult at all
    assert module.read_text(encoding="utf-8") == SOURCE  # restored


def test_thorough_tests_kill_the_mutants_they_cover(tmp_path: Path) -> None:
    module = tmp_path / "mathx.py"
    module.write_text(
        "def clamp(value, low, high):\n    if value < low:\n        return low\n    return value\n",
        encoding="utf-8",
    )
    (tmp_path / "test_mathx.py").write_text(
        "from mathx import clamp\n\ndef test_all():\n    assert clamp(-3, 0, 10) == 0\n    assert clamp(0, 0, 10) == 0\n    assert clamp(5, 0, 10) == 5\n",
        encoding="utf-8",
    )
    tried, survivors = run_mutation_check(module, tmp_path, sys.executable, [])
    assert tried >= 2
    assert [m.description for m in survivors] == [] or all("Lt" not in m.description for m in survivors)


async def test_the_tool_reports_survivors_and_refuses_test_files(original_repo: Path, tmp_path: Path) -> None:
    from forge.toolkit.base import ToolContext
    from forge.tools.test_quality import MutationCheck
    from forge.workspace.create import create_workspace
    from forge.workspace.pyenv import PythonEnvironment

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    workspace.info.python_env = PythonEnvironment(
        python=sys.executable, venv="", app_dir=str(workspace.app_dir), top_packages=[]
    )
    relative = workspace.app_dir.relative_to(workspace.repo_dir).as_posix()
    workspace.write_text(f"{relative}/mathx.py", SOURCE)
    workspace.write_text(
        f"{relative}/test_mathx.py",
        "from mathx import clamp\n\ndef test_one():\n    assert clamp(5, 0, 10) == 5\n",
    )
    context = ToolContext(workspace=workspace)
    tool = MutationCheck()
    result = await tool.run(tool.Args(path=f"{relative}/mathx.py", tests="test_mathx.py"), context)
    assert (
        result.ok
        and "went unnoticed by the tests" in result.content
        and "nothing checks this" in result.content
    )
    refused = await tool.run(tool.Args(path=f"{relative}/test_mathx.py"), context)
    assert not refused.ok and "not a test file" in refused.content
    _ = pytest

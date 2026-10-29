"""D-560: a changed expectation in the user's existing tests is named in the edit result and listed in the delivery report."""

from __future__ import annotations

from pathlib import Path

from forge.toolkit.base import ToolContext
from forge.tools.files import EditFile, ReadFile, WriteFile
from forge.workspace.create import create_workspace
from forge.workspace.test_expectations import changed_assertions, is_existing_test, report_lines, take_all
from tests.conftest import FIXTURE_REPO

EXISTING = "backend/tests/test_claims_api.py"


def test_rewritten_and_removed_assertions_are_found_and_added_ones_are_not() -> None:
    before = 'def test_a():\n    assert total == 3\n    assert body["n"].endswith("-00004")\n    x = 1\n'
    after = "def test_a():\n    assert total == 2\n    x = 2\n    assert new_check()\n"
    assert changed_assertions(before, after) == [
        ("assert total == 3", "assert total == 2"),
        ('assert body["n"].endswith("-00004")', ""),
    ]
    assert changed_assertions(before, before + "    assert extra\n") == []  # only added: it checks more
    assert changed_assertions("    assert x == 1\n", "    assert  x == 1\n") == [
        ("assert x == 1", "assert  x == 1")
    ]


def test_only_tests_that_were_in_the_original_repository_count(tmp_path: Path) -> None:
    workspace = create_workspace(FIXTURE_REPO, tmp_path / "ws", "backend")
    assert is_existing_test(workspace, EXISTING)
    assert not is_existing_test(workspace, "backend/tests/test_new_feature.py")  # the model's own new test
    assert not is_existing_test(workspace, "backend/claims_app/services/claims_service.py")  # not a test


async def test_the_edit_result_names_the_change_and_the_report_lists_it(tmp_path: Path) -> None:
    """The TI3 case (D-559): the next claim number edited to repeat an existing one."""
    workspace = create_workspace(FIXTURE_REPO, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace)
    await ReadFile().run(ReadFile.Args(path=EXISTING), context)
    edited = await EditFile().run(
        EditFile.Args(
            path=EXISTING,
            old_string='assert body["claim_number"].endswith("-00004")',
            new_string='assert body["claim_number"].endswith("-00003")',
        ),
        context,
    )
    assert edited.ok and "You changed 1 expectation(s) in an existing test" in edited.content
    assert (
        '`assert body["claim_number"].endswith("-00004")` -> `assert body["claim_number"].endswith("-00003")`'
        in edited.content
    )

    new_test = await WriteFile().run(
        WriteFile.Args(path="backend/tests/test_counts.py", content="def test_x():\n    assert 1 == 1\n"),
        context,
    )
    assert "expectation" not in new_test.content  # a new test file is the model's own

    entries = take_all(workspace)
    assert [entry["path"] for entry in entries] == [EXISTING]
    assert "## Changed test expectations" in "\n".join(report_lines(entries))
    assert take_all(workspace) == []  # the next change request starts with an empty list

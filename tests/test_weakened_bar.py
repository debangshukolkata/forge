"""A task must not turn a check off to get to green: new suppressions, skipped tests and deleted tests are reported."""

from __future__ import annotations

from pathlib import Path

from forge.tools.weakened_bar import weakened_bar_findings

TESTS_BEFORE = "def test_a():\n    assert 1\n\n\ndef test_b():\n    assert 2\n"


def _case(tmp_path: Path, name: str, before: str | None, after: str | None) -> tuple[str, Path, Path]:
    current, baseline = tmp_path / "repo" / name, tmp_path / "baseline" / name
    for path, text in ((current, after), (baseline, before)):
        if text is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    return name, current, baseline


def test_new_suppression_is_reported(tmp_path: Path) -> None:
    found = weakened_bar_findings([_case(tmp_path, "a.py", "x = 1\n", "x = 1  # type: ignore\n")])
    assert len(found) == 1 and "suppression" in found[0]


def test_existing_suppression_is_not_reported(tmp_path: Path) -> None:
    text = "import os  # noqa\n"
    assert weakened_bar_findings([_case(tmp_path, "a.py", text, text + "y = 2\n")]) == []


def test_new_file_with_a_skip_is_reported(tmp_path: Path) -> None:
    after = "import pytest\n\n\n@pytest.mark.skip\ndef test_a():\n    assert 1\n"
    found = weakened_bar_findings([_case(tmp_path, "test_a.py", None, after)])
    assert len(found) == 1 and "skipped" in found[0]


def test_deleted_test_and_deleted_file_are_reported(tmp_path: Path) -> None:
    fewer = weakened_bar_findings(
        [_case(tmp_path, "test_a.py", TESTS_BEFORE, "def test_a():\n    assert 1\n")]
    )
    assert len(fewer) == 1 and "1 fewer" in fewer[0]
    gone = weakened_bar_findings([_case(tmp_path, "test_b.py", TESTS_BEFORE, None)])
    assert len(gone) == 1 and "2 fewer" in gone[0]


def test_typescript_and_other_files(tmp_path: Path) -> None:
    ts = weakened_bar_findings([_case(tmp_path, "a.ts", "const x = 1;\n", "// @ts-ignore\nconst x = 1;\n")])
    assert len(ts) == 1
    assert weakened_bar_findings([_case(tmp_path, "notes.md", "a\n", "# noqa\n")]) == []

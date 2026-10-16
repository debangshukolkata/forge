"""The acceptance criteria check (D-456): the verifier's criteria lines are read, and the refusal says what is missing."""

from __future__ import annotations

from pathlib import Path

from forge.subagents.criteria import (
    CRITERIA_ROUND_LIMIT,
    criteria_refusal,
    has_criteria_lines,
    parse_criteria,
    project_criteria,
)

REPORT = """Layer table ...

ACCEPTANCE CRITERIA
1. MET: a manager sees who else is away (screenshot shot-3)
2. NOT MET: self-approval is possible from the HR screen
3. UNCHECKED - needs a second browser session
- **4. MET** - payroll CSV downloads
VERDICT: FAIL"""


def test_lines_are_sorted_into_met_not_met_and_unchecked() -> None:
    parsed = parse_criteria(REPORT)
    assert [n for n, _ in parsed["met"]] == [1, 4]
    assert parsed["not_met"] == [(2, "self-approval is possible from the HR screen")]
    assert parsed["unchecked"][0][0] == 3
    assert has_criteria_lines(parsed)
    assert not has_criteria_lines(parse_criteria("VERDICT: PASS, nothing else"))


def test_project_criteria_reads_the_section_of_requirements(tmp_path: Path) -> None:
    forge = tmp_path / ".forge"
    forge.mkdir()
    (forge / "REQUIREMENTS.md").write_text(
        "# App\n\n## Scope\nx\n\n## Acceptance criteria\n1. A user can sign in\n2. A manager approves\n\n## Edge cases\n- none\n",
        encoding="utf-8",
    )
    text = project_criteria(forge)
    assert "A manager approves" in text and "Edge cases" not in text and "Scope" not in text
    assert project_criteria(tmp_path / "other") == ""


def test_the_gate_refuses_unchecked_then_not_met_and_lets_go_after_three_rounds() -> None:
    criteria = "1. A user can sign in"
    assert "have not been checked" in criteria_refusal(criteria, None, 0)
    parsed = parse_criteria(REPORT)
    assert "2. self-approval" in criteria_refusal(criteria, parsed, 1)
    assert criteria_refusal(criteria, parsed, CRITERIA_ROUND_LIMIT) == ""
    assert criteria_refusal(criteria, parse_criteria("1. MET: ok"), 0) == ""

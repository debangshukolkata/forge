"""D-660: `Laptop-Report.cmd` / `forge laptop all`: the questions, the conversations it holds, the new pages."""

from __future__ import annotations

import json
from pathlib import Path

from forge.engine import laptop_all
from forge.engine.laptop_pages import ITEMS, report_folder, summary_page
from tests.test_laptop import Log, _write_conversation


def test_no_question_and_nothing_on_wisdomnext() -> None:
    """D-661: the run asks nothing and holds only the two planners and the crawl, in a test project."""
    held = laptop_all.conversations_to_hold()
    assert [items for items, _, _ in held] == ["DP1", "TV1"]
    assert "planner" in held[0][1][0] and "tavily_crawl" in held[1][1][0]
    assert not hasattr(laptop_all, "ask_inputs")
    assert set(laptop_all.COVERED) <= set(ITEMS)


def test_the_test_project_is_made_from_the_sample_repository(isolated_forge_home: Path) -> None:
    root = laptop_all.make_test_project(isolated_forge_home, Path(__file__).resolve().parents[1])
    assert (root / ".forge").is_dir() and root.parent == report_folder(isolated_forge_home)


def test_the_summary_shows_only_the_items_of_this_run(isolated_forge_home: Path) -> None:
    lines = summary_page(isolated_forge_home, only=laptop_all.COVERED).lines
    assert [line.split()[0] for line in lines if line.strip()][: len(laptop_all.COVERED)] == [
        item for item in ITEMS if item in laptop_all.COVERED
    ]
    assert not any(line.startswith("RS7") for line in lines)


def test_the_two_planner_page_counts_merged_plans_and_cards(tmp_path: Path) -> None:
    log = Log()
    log.call(
        "spawn_subagent",
        {"agent": "planner"},
        preview="[planner report]\n## Objective\n## Decided between the two plans\n- x",
    )
    log.add(
        "question_asked",
        {"id": "q1", "question": "Two plans differ: how questions are answered", "options": []},
    )
    _write_conversation(tmp_path, "c2", log, 10)
    page = laptop_all.dual_plan_page(tmp_path)
    assert page.verdicts[0].status == "PASS" and "1 merged, 1 card" in page.verdicts[0].line
    one = Log()
    one.call("spawn_subagent", {"agent": "planner"}, preview="[planner report]\n## Objective")
    _write_conversation(tmp_path / "other", "c1", one, 10)
    assert laptop_all.dual_plan_page(tmp_path / "other").verdicts[0].status == "CHECK"
    assert laptop_all.dual_plan_page(None).verdicts[0].status == "NOT RUN"


def test_the_role_challenge_page_shows_why_a_coder_turn_ended(isolated_forge_home: Path) -> None:
    folder = isolated_forge_home / "reports" / "role-challenge" / "20261125-0901"
    folder.mkdir(parents=True)
    rows = [
        {
            "role": "coder",
            "model": "gemini-4-neon",
            "repeat": 0,
            "note": "12 of 12",
            "failed_calls": ["run_command", "ERROR 504 DEADLINE_EXCEEDED"],
        },
        {"role": "judge", "model": "gemini-4-neon", "repeat": 0},
    ]
    (folder / "results.json").write_text(json.dumps({"facts": {}, "rows": rows}), encoding="utf-8")
    lines = laptop_all.role_challenge_page(isolated_forge_home).lines
    assert lines[0].startswith("gemini-4-neon 1: 12 of 12") and "ERROR 504" in lines[1] and len(lines) == 2

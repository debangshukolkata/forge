"""D-660: `Laptop-Report.cmd` / `forge laptop all`: the questions, the conversations it holds, the new pages."""

from __future__ import annotations

import json
from pathlib import Path

from forge.engine import laptop_all
from forge.engine.laptop_pages import ITEMS, report_folder
from tests.test_laptop import Log, _write_conversation


def _answers(*typed: str):  # type: ignore[no-untyped-def]
    queue = list(typed)
    return lambda _question: queue.pop(0) if queue else ""


def test_the_questions_are_asked_once_and_offered_again(isolated_forge_home: Path, tmp_path: Path) -> None:
    project = tmp_path / "wisdom"
    (project / ".forge").mkdir(parents=True)
    first = laptop_all.ask_inputs(
        isolated_forge_home, _answers(str(project), "", "argocd", "how many pods?", "", "")
    )
    assert (
        first["agent"] == "argocd"
        and first["site"] == "https://docs.python.org/3/"
        and first["requirement"] == ""
    )
    again = laptop_all.ask_inputs(isolated_forge_home, _answers("", "", "", "", "", "Add a health endpoint"))
    assert again["workspace"] == str(project) and again["question"] == "how many pods?"
    assert again["requirement"] == "Add a health endpoint"
    saved = json.loads(
        (report_folder(isolated_forge_home) / laptop_all.INPUTS_FILE).read_text(encoding="utf-8")
    )
    assert saved == again


def test_a_folder_that_is_not_a_project_stops_at_once(isolated_forge_home: Path, tmp_path: Path) -> None:
    try:
        laptop_all.ask_inputs(isolated_forge_home, _answers(str(tmp_path), "", "a", "q", "", ""))
    except SystemExit as stop:
        assert "no .forge folder" in str(stop)
    else:
        raise AssertionError("a folder without .forge was taken")


def test_the_conversations_cover_the_items_the_plan_asked_the_user_to_type() -> None:
    held = laptop_all.conversations_to_hold(
        {"agent": "argocd", "question": "how many pods?", "site": "https://a.example/", "requirement": ""}
    )
    items = {item for entry in held for item in entry[0].split()}
    assert {"TK5", "TK6", "RN2", "KL6", "TV1", "RS9", "HT1"} <= items
    assert any("argocd" in text and "how many pods?" in text for _, texts, _ in held for text in texts)
    assert [texts[0] for _, texts, _ in held if texts[0].startswith("/")] == ["/learn"]
    assert {"GM1", "DP1", "GQ1", "CP2"} <= set(ITEMS)


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

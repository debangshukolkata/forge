"""D-655: the challenge's truths are true, its scores tell right from wrong, and a run can go on."""

from __future__ import annotations

import copy
import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

FOLDER = Path(__file__).resolve().parent.parent / "scripts" / "dev"


@pytest.fixture(scope="module")
def kit() -> Any:
    sys.path.insert(0, str(FOLDER))
    try:
        return importlib.import_module("role_challenge")
    finally:
        sys.path.remove(str(FOLDER))


CASES: list[tuple[list[tuple[int, int]], int]] = [
    ([], 5),
    ([(0, 10)], 5),
    ([(5, 10)], 5),
    ([(20, 30), (0, 10)], 5),
    ([(0, 50), (10, 20), (60, 70)], 10),
    ([(0, 50), (10, 20), (55, 70)], 10),
    ([(0, 100), (5, 8), (20, 30)], 10),
    ([(10, 20), (0, 4), (3, 12)], 1),
    ([(0, 10), (5, 30), (12, 14)], 3),
    ([(0, 5), (5, 6), (16, 20)], 10),
    ([(8, 30), (0, 10), (9, 12)], 8),
    ([(0, 100), (40, 50)], 5),
]


def _truth(taken: list[tuple[int, int]], size: int) -> int:
    at = 0
    while any(start < at + size and at < end for start, end in taken):
        at += 1
    return at


def test_the_known_verdicts_of_the_judge_task_are_true(kit: Any) -> None:
    for name, (answer, (correct, unchanged, sentence)) in kit.tasks.JUDGE_ANSWERS.items():
        explained, _, code = answer.partition("def first_free")
        scope: dict[str, Any] = {}
        exec("def first_free" + code.split("\n\nIt walks")[0], scope)
        right = kept = True
        for taken, size in CASES:
            given = copy.deepcopy(taken)
            right &= scope["first_free"](given, size) == _truth(taken, size)
            kept &= given == taken
        assert (right, kept) == (correct, unchanged), name
        assert sentence == (explained.strip().count(".") == 1), name


def test_the_scores_tell_right_from_wrong(kit: Any) -> None:
    tasks = kit.tasks
    truth = {
        n: dict(zip(tasks.JUDGE_KEYS, verdict, strict=True))
        for n, (_, verdict) in tasks.JUDGE_ANSWERS.items()
    }
    assert tasks.judge_score("So:\n```json\n" + json.dumps(truth) + "\n```")[0] == 100
    lenient = {n: dict.fromkeys(tasks.JUDGE_KEYS, True) for n in truth}
    assert tasks.judge_score(json.dumps(lenient))[0] < 80
    faults = [
        {
            "function": f + "()",
            "problem": "the first page, sql parameter, mutable default, atomic, path, naive, lost, silent, return code, empty, string compare, iterate, swallow, year 31",
        }
        for f in tasks.REVIEW_FAULTS
    ]
    assert tasks.reviewer_score(json.dumps({"defects": faults}))[0] == 100
    alarms = [*faults, {"function": "cached", "problem": "race"}, {"function": "file_id", "problem": "md5"}]
    assert 85 < tasks.reviewer_score(json.dumps({"defects": alarms}))[0] < 100
    assert tasks.reviewer_score("I see nothing")[0] == 0
    for name, (_, values) in tasks.VISION.items():
        assert tasks.vision_score(name, json.dumps(values))[0] == 100
        assert tasks.vision_score(name, json.dumps(dict.fromkeys(values, "?")))[0] == 0
        assert (kit.PICTURES / f"{name}.png").is_file()
    for name in tasks.CRITIC_FAULTS:
        assert (kit.PICTURES / f"{name}.png").is_file()
    assert tasks.critic_score("good", '{"defects": []}')[0] == 100
    assert tasks.critic_score("phone", '{"defects": []}')[0] == 0
    everything = " ".join(tasks._STEPS)
    assert tasks.summary_score(everything)[0] < 100 and "20 of 20" in tasks.summary_score(everything)[1]
    assert tasks.planner_score('{"met": [1, 2, 3, 99]}') == 20
    assert tasks.planner_score("good plan") is None


async def test_taking_over_is_scored_by_what_works(kit: Any) -> None:
    from forge.llm.base import LLMResponse

    fallback = kit.fallback
    basket = (
        "from prices import price_of\n\n\nclass Basket:\n    def __init__(self):\n        self.lines = {}\n\n"
        "    def add(self, name, count=1):\n        self.lines[name] = self.lines.get(name, 0) + count\n\n"
        "    def remove(self, name):\n        return self.lines.pop(name)\n\n    def total(self):\n"
        "        total = sum(price_of(n) * c for n, c in self.lines.items())\n"
        "        return total * 0.9 if total >= 100 else total\n"
    )
    shop = "from basket import Basket\nfrom prices import load_prices, price_of\n"

    def playing(*writes: tuple[str, str]) -> Any:
        replies = [
            LLMResponse(tool_calls=[fallback._call(9 + n, "write_file", {"path": path, "content": text})])
            for n, (path, text) in enumerate(writes)
        ] + [LLMResponse(text="done")]

        async def ask(request: Any) -> Any:
            return replies.pop(0)

        return ask

    fixed = fallback.PRICES.replace("PRICES.get(name, 0.0)", "PRICES[name]")
    full = [("basket.py", basket), ("shop.py", shop)]
    assert (await fallback.play(playing(("prices.py", fixed), *full), "k"))[0] == 100
    trusting = await fallback.play(playing(*full), "k")  # believes the other model's work
    assert 80 < trusting[0] < 95
    assert (await fallback.play(playing(), "k"))[0] < 40


def test_the_report_names_the_choice_and_a_run_goes_on(kit: Any, tmp_path: Path) -> None:
    run = kit.Run(tmp_path / "r")
    for model, score, seconds in (("gpt54", 90, 40), ("gemini-4-neon", 88, 10), ("gemini-4-carbon", 50, 5)):
        run.add(
            {"role": "judge", "model": model, "repeat": 0, "score": score, "seconds": seconds, "note": "<b>"}
        )
    run.add(
        {
            "role": "planner",
            "model": "gpt54",
            "repeat": 0,
            "score": 0.0,
            "error": "TimeoutError: x",
            "seconds": 1,
        }
    )
    again = kit.Run(tmp_path / "r")
    assert again.done("judge", "gpt54", 0) and not again.done(
        "planner", "gpt54", 0
    )  # an error is tried again
    choice, second, sure = kit.report.verdict(again.rows, "judge", again.models())
    assert (choice, second) == ("gemini-4-neon", "gpt54") and "close" in sure
    text = (tmp_path / "r" / "report.html").read_text(encoding="utf-8")
    assert "Design critic" in text and "&lt;b&gt;" in text and "TimeoutError" in text


def test_a_candidate_works_alone_and_without_the_users_services(kit: Any, tmp_path: Path) -> None:
    from forge.config import Secrets, load_config

    mine = kit.coder.alone(load_config(tmp_path), "gpt54")
    assert {getattr(mine.llm.roles, r) for r in ("coder", "planner", "fallback", "critic")} == {"gpt54"}
    assert mine.llm.rotation == [] and mine.llm.fallback_also == []
    values = {"AZURE_OPENAI_ENDPOINT": "x", "DEV_PG_URL": "y", "TAVILY_X": "z", "GOOGLE_CLOUD_PROJECT": "p"}
    assert kit.coder.own_secrets(Secrets(values, None)).names() == [
        "AZURE_OPENAI_ENDPOINT",
        "GOOGLE_CLOUD_PROJECT",
    ]


def test_the_project_is_complete_and_the_checks_see_a_missing_answer(kit: Any, tmp_path: Path) -> None:
    repo = kit.coder.make_project(tmp_path, 9)
    assert "127.0.0.1:9/complete" in (repo / "recqa" / "model.py").read_text(encoding="utf-8")
    compile((repo / "recqa" / "model.py").read_text(encoding="utf-8"), "model.py", "exec")
    camera = kit.coder.check_camera(repo, tmp_path / "check", 9)
    assert camera == {"20417": False, "20418": False, "20419": False, "13615 still works": True}
    answers = kit.coder.check_answers(repo, tmp_path / "check", 9)
    assert answers["starts"] and all(r["problem"] for r in answers["results"].values())

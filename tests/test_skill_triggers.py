"""Deterministic tests of the skill trigger library (TODO C14). No model call."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "benchmark"))
import skill_trigger_lib as lib

NAMES = ["test-first", "debugging", "web-research", "make-document"]


def test_split_is_stable_and_sixty_forty() -> None:
    queries = [f"query number {i}" for i in range(10)]
    train, test = lib.split_queries("s", "should", queries)
    assert (len(train), len(test)) == (6, 4)
    assert set(train) | set(test) == set(queries) and not set(train) & set(test)
    assert lib.split_queries("s", "should", list(reversed(queries))) == (
        train,
        test,
    )  # file order does not matter
    assert lib.split_queries("s", "should", queries) == (train, test)


def test_cases_cover_both_kinds_in_each_part() -> None:
    triggers = {"s": {"should": [f"a{i}" for i in range(10)], "should_not": [f"b{i}" for i in range(10)]}}
    train = lib.cases_for(triggers, "s", "train")
    test = lib.cases_for(triggers, "s", "test")
    assert len(train) == 12 and len(test) == 8
    assert {c.kind for c in train} == {c.kind for c in test} == {"should", "should_not"}
    assert len(lib.cases_for(triggers, "s")) == 20


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("test-first", "test-first"),
        ("  Test-First.  ", "test-first"),
        ("`debugging`", "debugging"),
        ("NONE", None),
        ("None.", None),
        ("none of these fit", None),
        ("I would load web-research first.", "web-research"),
        ("Skill: make-document", "make-document"),
        ("None. The closest is debugging.", None),
        ("not-a-skill", None),
        ("", None),
        ("web-researcher", None),  # a longer, unknown name is not a prefix match
    ],
)
def test_parse_answer(text: str, expected: str | None) -> None:
    assert lib.parse_answer(text, NAMES) == expected


def test_parse_answer_takes_the_earliest_name() -> None:
    assert lib.parse_answer("debugging, then test-first", NAMES) == "debugging"


def test_majority() -> None:
    assert lib.majority(["a", "a", None]) == "a"
    assert lib.majority(["a", None]) is None
    assert lib.majority(["a"]) == "a"
    assert lib.majority([]) is None


def test_scoring() -> None:
    cases = [
        (lib.Case("x", "should", "q1"), "x"),
        (lib.Case("x", "should", "q2"), "y"),
        (lib.Case("x", "should", "q3"), None),
        (lib.Case("x", "should_not", "n1"), "x"),
        (lib.Case("x", "should_not", "n2"), "y"),
        (lib.Case("x", "should_not", "n3"), None),
        (lib.Case("x", "should_not", "n4"), None),
    ]
    score = lib.score_cases(cases)
    assert (score.should_hit, score.should_total, score.not_false, score.not_total) == (1, 3, 1, 4)
    assert score.recall == pytest.approx(1 / 3)
    assert score.false_rate == pytest.approx(1 / 4)
    assert score.accuracy == pytest.approx((1 + 3) / 7)
    assert score.missed == [("q2", "y"), ("q3", None)]
    assert score.false_triggers == ["n1"]
    assert lib.confusions(cases) == {"y": 1, "NONE": 1}


def test_recommend_needs_a_test_gain_without_train_loss() -> None:
    def sc(hit: int, false: int = 0) -> lib.Score:
        return lib.Score(should_total=5, should_hit=hit, not_total=5, not_false=false)

    current = (sc(3), sc(3))
    best, _ = lib.recommend(current, [("a", sc(2), sc(5)), ("b", sc(4), sc(4)), ("c", sc(5), sc(3))])
    assert best == 1  # "a" loses on train, "c" does not beat current on test
    none, _ = lib.recommend(current, [("a", sc(3), sc(3))])
    assert none is None


def test_swap_description_is_in_memory_only() -> None:
    from forge.parity.skills import discover

    skills = discover()
    original = skills["test-first"].description
    swapped = lib.swap_description(skills, "test-first", "Use when testing.")
    assert swapped["test-first"].description == "Use when testing."
    assert skills["test-first"].description == original
    assert "- test-first: Use when testing." in lib.build_index(swapped)


def test_set_description_in_text_keeps_the_rest() -> None:
    text = "---\nname: x\ndescription: old words: here\nother: 1\n---\nBody\ndescription: not me\n"
    new = lib.set_description_in_text(text, "Use when\nnew")
    assert new == "---\nname: x\ndescription: Use when new\nother: 1\n---\nBody\ndescription: not me\n"
    with pytest.raises(ValueError):
        lib.set_description_in_text("no front matter", "x")


def test_description_rules() -> None:
    assert lib.description_problems("Use when you write tests; not for debugging.") == []
    assert lib.description_problems("This is a skill") != []
    assert lib.description_problems("Use when " + "x" * 400) != []
    assert lib.description_problems("Use when ALWAYS do it") != []


def test_parse_candidates() -> None:
    assert lib.parse_candidates('["a", "b"]') == ["a", "b"]
    assert lib.parse_candidates('```json\n["a"]\n```') == ["a"]
    assert lib.parse_candidates("- one\n- two") == ["one", "two"]


def test_triggers_file_is_valid() -> None:
    from forge.parity.skills import discover

    triggers = lib.load_triggers()
    assert len(triggers) == 12
    assert lib.check_triggers(triggers, discover()) == []


def test_check_triggers_finds_problems() -> None:
    bad = {"debugging": {"should": ["use debugging now"] * 2, "should_not": ["x" * 400]}}
    problems = lib.check_triggers(bad, ["debugging"])
    text = "\n".join(problems)
    assert (
        "expected 10" in text
        and "duplicate" in text
        and "contains the skill name" in text
        and "characters" in text
    )

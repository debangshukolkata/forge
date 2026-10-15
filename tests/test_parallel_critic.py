"""X1: design-critic may run side by side with other read-only agents; screenshot names never collide."""

from __future__ import annotations

import re

from forge.agent.loop import PARALLEL_SUBAGENT_TYPES
from forge.tools.browser import unique_stamp


def test_design_critic_is_parallel_safe_and_writers_are_not() -> None:
    assert {"explore", "planner", "reviewer", "design-critic"} <= PARALLEL_SUBAGENT_TYPES
    assert "verifier" not in PARALLEL_SUBAGENT_TYPES
    assert "debugger" not in PARALLEL_SUBAGENT_TYPES


def test_screenshot_stamp_is_unique_within_one_second() -> None:
    stamps = {unique_stamp() for _ in range(200)}
    assert len(stamps) == 200
    assert all(re.fullmatch(r"\d{8}-\d{6}-\d{9}-[0-9a-f]{4}", s) for s in stamps)


def test_the_critic_round_note_tells_the_builder_what_is_left() -> None:
    from forge.subagents.critic import CRITIC_PROMPT, critic_round_note

    assert critic_round_note("SHIP", 0, 3) == ""
    first = critic_round_note("REVISE", 1, 3)
    assert "round 1 of 3" in first and "follow-up review" in first and "BLOCKING" in first
    last = critic_round_note("REVISE", 3, 3)
    assert "the last one" in last and "Do not ask for another review" in last
    assert (
        "ITS BRIEF" in CRITIC_PROMPT
        and "scope creep" in CRITIC_PROMPT
        and "FOLLOW-UP REVIEWS" in CRITIC_PROMPT
    )

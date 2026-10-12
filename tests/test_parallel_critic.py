"""X1: design-critic may run side by side with other read-only agents; screenshot names never collide."""

from __future__ import annotations

import re

from forge.agent.loop import PARALLEL_SUBAGENT_TYPES
from forge.tools.browser import unique_stamp


def test_design_critic_is_parallel_safe_and_writers_are_not() -> None:
    assert {"explore", "reviewer", "design-critic"} <= PARALLEL_SUBAGENT_TYPES
    assert "verifier" not in PARALLEL_SUBAGENT_TYPES
    assert "debugger" not in PARALLEL_SUBAGENT_TYPES


def test_screenshot_stamp_is_unique_within_one_second() -> None:
    stamps = {unique_stamp() for _ in range(200)}
    assert len(stamps) == 200
    assert all(re.fullmatch(r"\d{8}-\d{6}-\d{9}-[0-9a-f]{4}", s) for s in stamps)

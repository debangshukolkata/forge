"""D-298: the user is told the context is filling up, once per level, with what to do."""

from __future__ import annotations

from forge.config import ContextConfig
from forge.context.warnings import next_warning

SETTINGS = ContextConfig()


def test_nothing_is_said_below_the_first_threshold() -> None:
    assert next_warning(40.0, 0, SETTINGS) == (None, 0)
    assert next_warning(69.9, 0, SETTINGS) == (None, 0)


def test_the_first_warning_names_the_percent_and_the_options() -> None:
    text, level = next_warning(72.4, 0, SETTINGS)
    assert level == 1 and text is not None
    assert "72%" in text and "/compact" in text and "new requirement" in text and "80%" in text


def test_each_level_is_said_once() -> None:
    _, level = next_warning(75.0, 0, SETTINGS)
    assert next_warning(78.0, level, SETTINGS) == (None, 1)
    text, level = next_warning(91.0, level, SETTINGS)
    assert level == 2 and text is not None and "less reliable" in text and "/clear" in text
    assert next_warning(95.0, level, SETTINGS) == (None, 2)


def test_jumping_straight_past_both_thresholds_gives_the_stronger_warning_only() -> None:
    text, level = next_warning(93.0, 0, SETTINGS)
    assert level == 2 and text is not None and "less reliable" in text


def test_it_can_warn_again_after_the_context_has_been_cleared_down() -> None:
    _, level = next_warning(92.0, 0, SETTINGS)
    assert next_warning(30.0, level, SETTINGS) == (None, 0)  # after a compaction
    text, level = next_warning(71.0, 0, SETTINGS)
    assert level == 1 and text is not None
    assert next_warning(65.0, 1, SETTINGS) == (None, 1)  # a small dip does not reset it

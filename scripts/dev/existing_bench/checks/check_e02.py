"""E02: a help text that exactly fits is not truncated; the rest of the truncation rules are unchanged."""

from __future__ import annotations

import click
import pytest
from click.utils import make_default_short_help

EXACT = "a" * 20 + " " + "b" * 24  # 45 characters, no full stop


def test_click_comes_from_the_delivered_copy(repo):
    assert str(repo) in click.__file__


def test_exact_fit_is_kept():
    assert len(EXACT) == 45
    assert make_default_short_help(EXACT, 45) == EXACT


def test_one_over_is_truncated():
    text = "a" * 20 + " " + "b" * 25  # 46 characters
    assert make_default_short_help(text, 45).endswith("...")


@pytest.mark.parametrize(
    ("text", "limit", "expected"),
    [
        ("Hello. World", 45, "Hello."),
        ("short", 45, "short"),
        ("one two three four five", 10, "one two..."),
    ],
)
def test_other_rules_unchanged(text, limit, expected):
    assert make_default_short_help(text, limit) == expected

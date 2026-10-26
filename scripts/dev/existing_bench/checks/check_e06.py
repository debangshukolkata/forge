"""E06: Choice conversion is fast on a large list and gives the same results as before."""

from __future__ import annotations

import random
import time

import click
import pytest
from click.testing import CliRunner


def test_click_comes_from_the_delivered_copy(repo):
    assert str(repo) in click.__file__


def test_large_choice_is_fast():
    choices = [f"choice-{i}" for i in range(20000)]
    type_ = click.Choice(choices)
    values = random.Random(1).choices(choices, k=3000)
    started = time.perf_counter()
    for value in values:
        assert type_.convert(value, None, None) == value
    assert time.perf_counter() - started < 1.0


def test_large_case_insensitive_choice_is_fast():
    choices = [f"Choice-{i}" for i in range(20000)]
    type_ = click.Choice(choices, case_sensitive=False)
    values = random.Random(2).choices(choices, k=3000)
    started = time.perf_counter()
    for value in values:
        assert type_.convert(value.upper(), None, None) == value
    assert time.perf_counter() - started < 1.0


def test_case_insensitive_returns_the_original_spelling():
    assert click.Choice(["Red", "Green"], case_sensitive=False).convert("GREEN", None, None) == "Green"


def test_case_sensitive_rejects_other_case():
    with pytest.raises(click.BadParameter):
        click.Choice(["Red"]).convert("red", None, None)


def test_unknown_value_message_is_unchanged():
    with pytest.raises(click.BadParameter) as caught:
        click.Choice(["a", "b"]).convert("c", None, None)
    assert "'c' is not one of 'a', 'b'." in caught.value.message


def test_token_normalize_func_is_still_applied():
    ctx = click.Context(
        click.Command("x"), token_normalize_func=lambda value: value.lower().replace("_", "-")
    )
    assert click.Choice(["Dry-Run"], case_sensitive=False).convert("DRY_RUN", None, ctx) == "Dry-Run"
    assert click.Choice(["dry-run"]).convert("dry_run", None, ctx) == "dry-run"


def test_works_in_a_command():
    @click.command()
    @click.option("--mode", type=click.Choice(["fast", "slow"], case_sensitive=False))
    def cli(mode):
        click.echo(mode)

    assert CliRunner().invoke(cli, ["--mode", "FAST"]).output.strip() == "fast"

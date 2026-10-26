"""E01: the boolean type accepts enable/enabled/disable/disabled and nothing else changed."""

from __future__ import annotations

import click
import pytest
from click.testing import CliRunner


def test_click_comes_from_the_delivered_copy(repo):
    assert str(repo) in click.__file__


@pytest.mark.parametrize("word", ["enable", "enabled", "Enabled", "ENABLE", "  enabled  "])
def test_enable_words_are_true(word):
    assert click.BOOL.convert(word, None, None) is True


@pytest.mark.parametrize("word", ["disable", "disabled", "Disabled", "DISABLE", "  disabled "])
def test_disable_words_are_false(word):
    assert click.BOOL.convert(word, None, None) is False


@pytest.mark.parametrize("word", ["1", "true", "t", "yes", "y", "on"])
def test_old_true_words_still_work(word):
    assert click.BOOL.convert(word, None, None) is True


@pytest.mark.parametrize("word", ["0", "false", "f", "no", "n", "off"])
def test_old_false_words_still_work(word):
    assert click.BOOL.convert(word, None, None) is False


def _cli():
    @click.command()
    @click.option("--flag", type=click.BOOL)
    def cli(flag):
        click.echo(repr(flag))

    return cli


def test_unknown_word_keeps_its_error():
    result = CliRunner().invoke(_cli(), ["--flag", "maybe"])
    assert result.exit_code == 2
    assert "'maybe' is not a valid boolean." in result.output


def test_option_accepts_the_new_words():
    assert CliRunner().invoke(_cli(), ["--flag", "enabled"]).output.strip() == "True"
    assert CliRunner().invoke(_cli(), ["--flag", "disabled"]).output.strip() == "False"

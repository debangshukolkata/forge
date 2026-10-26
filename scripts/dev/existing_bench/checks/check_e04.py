"""E04: prompt() and confirm() share one helper that holds the Ctrl-C / end-of-input handling, and behaviour is unchanged."""

from __future__ import annotations

import ast

import click
import pytest


def _termui(repo):
    source = (repo / "src" / "click" / "termui.py").read_text(encoding="utf-8")
    return source, ast.parse(source)


def _names_used(node):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _catches_interrupt(node):
    return any(
        isinstance(n, ast.ExceptHandler) and n.type is not None and "KeyboardInterrupt" in ast.dump(n.type)
        for n in ast.walk(node)
    )


def test_click_comes_from_the_delivered_copy(repo):
    assert str(repo) in click.__file__


def test_one_helper_holds_the_interrupt_handling(repo):
    _, tree = _termui(repo)
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    helpers = {
        name
        for name, node in functions.items()
        if name not in {"prompt", "confirm"} and _catches_interrupt(node)
    }
    shared = {
        name
        for name in helpers
        if name in _names_used(functions["prompt"]) and name in _names_used(functions["confirm"])
    }
    assert shared, (
        f"no module-level helper is used by both prompt and confirm (helpers with a handler: {helpers})"
    )


def test_duplicate_handlers_are_gone(repo):
    source, _ = _termui(repo)
    # Three handlers at the pinned commit (prompt, confirm, and one in the pager code); prompt and confirm must now share one.
    assert source.count("except (KeyboardInterrupt, EOFError)") <= 2


def test_confirm_aborts_on_end_of_input(monkeypatch):
    def raise_eof(prompt=""):
        raise EOFError

    monkeypatch.setattr("click.termui.visible_prompt_func", raise_eof)
    with pytest.raises(click.Abort):
        click.confirm("Sure")


def test_prompt_aborts_on_ctrl_c(monkeypatch):
    def raise_interrupt(prompt=""):
        raise KeyboardInterrupt

    monkeypatch.setattr("click.termui.visible_prompt_func", raise_interrupt)
    with pytest.raises(click.Abort):
        click.prompt("Name")


def test_hidden_prompt_abort_prints_a_newline(monkeypatch, capsys):
    def raise_interrupt(prompt=""):
        raise KeyboardInterrupt

    monkeypatch.setattr("click.termui.hidden_prompt_func", raise_interrupt)
    with pytest.raises(click.Abort):
        click.prompt("Secret", hide_input=True)
    assert capsys.readouterr().out == "Secret:\n"


def test_visible_prompt_abort_prints_no_extra_newline(monkeypatch, capsys):
    def raise_interrupt(prompt=""):
        raise KeyboardInterrupt

    monkeypatch.setattr("click.termui.visible_prompt_func", raise_interrupt)
    with pytest.raises(click.Abort):
        click.prompt("Name")
    assert capsys.readouterr().out == "Name:"


def test_prompt_and_confirm_still_work(monkeypatch):
    answers = iter(["Ada", "y"])
    monkeypatch.setattr("click.termui.visible_prompt_func", lambda prompt="": next(answers))
    assert click.prompt("Name") == "Ada"
    assert click.confirm("Sure") is True

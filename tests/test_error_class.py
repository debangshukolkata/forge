"""D-673: the same kind of error after fixes asks for the class; outside systems only when suggestions are asked."""

from __future__ import annotations

from forge.agent.error_class import ErrorClasses, asks_for_suggestions, error_kinds

PLAYGROUND = '{"status": "failed", "error": "SyntaxError: unterminated string literal (detected at line 41)"}'


def test_error_kinds_come_from_running_tools_only() -> None:
    assert error_kinds("http_request", PLAYGROUND) == {"SyntaxError"}
    assert error_kinds("run_command", "Traceback ...\nKeyError: 'name'\n") == {"KeyError"}
    assert error_kinds("read_file", "SyntaxError: x") == set()  # the text of a file, not a run
    assert error_kinds("run_command", "except ValueError:\n    pass") == set()
    assert error_kinds("run_command", "RuntimeError: boom\nAssertionError: 1 != 2") == set()  # too general


def test_the_third_code_state_raises_the_class_once_and_stays_in_scope() -> None:
    classes = ErrorClasses()
    assert classes.observe("http_request", PLAYGROUND, 3) == ""
    assert classes.observe("http_request", PLAYGROUND, 3) == ""  # the same code: not a new round
    assert classes.observe("http_request", PLAYGROUND, 7) == ""
    note = classes.observe("http_request", PLAYGROUND, 12)
    assert "SyntaxError again" in note and "cannot happen again" in note
    assert "Do not propose" in note and "for its owners" not in note
    assert classes.observe("http_request", PLAYGROUND, 15) == ""  # said once
    finish = classes.finish_note("Fixed the quote on line 41.")
    assert "common cause" in finish and "Do not propose" in finish
    assert classes.finish_note("Fixed it.") == ""  # asked once
    other = ErrorClasses(raised={"SyntaxError"})
    assert other.finish_note("The cause of every SyntaxError: HTML inside a Python string.") == ""


def test_a_request_for_suggestions_opens_outside_systems() -> None:
    assert asks_for_suggestions("Any suggestions how to avoid these errors?")
    assert asks_for_suggestions("how can we prevent this from happening")
    assert asks_for_suggestions("what would you change so it does not break again")
    assert not asks_for_suggestions("fix the error on the playground")
    assert not asks_for_suggestions(None)
    classes = ErrorClasses(suggestions_asked=True)
    assert classes.suggestion_note() == ""  # nothing came back yet
    for state in (1, 2, 3):
        note = classes.observe("http_request", PLAYGROUND, state)
    assert "for its owners" in note and "Do not propose" not in note
    assert (
        "SyntaxError" in classes.suggestion_note() and "interface accepts today" in classes.suggestion_note()
    )

"""HW3: an edit whose old_string differs only in indentation or trailing spaces is applied (no model)."""

from __future__ import annotations

import pytest

from forge.tools.files import EditError, apply_edit, apply_edit_with_note

FUNCTION = (
    "def total(items):\n    result = 0\n    for item in items:\n        result += item\n    return result\n"
)


def test_wrong_indentation_is_applied_and_new_lines_follow_the_file() -> None:
    text = "class A:\n" + "".join("    " + line for line in FUNCTION.splitlines(keepends=True))
    old = "def total(items):\n    result = 0\n    for item in items:\n        result += item\n"
    new = "def total(items):\n    result = 1\n    for item in items:\n        result += item * 2\n"

    edited, note = apply_edit_with_note(text, old, new, False)

    assert (
        "    def total(items):\n        result = 1\n        for item in items:\n            result += item * 2\n"
        in edited
    )
    assert edited.endswith("        return result\n")
    assert note.startswith("Matched lines 2 to 5 after ignoring a difference in indentation")
    compile(edited, "x.py", "exec")  # the re-indented result is valid Python


def test_trailing_spaces_in_the_file_are_ignored() -> None:
    text = "alpha = compute_value(1)   \nbeta = 2\n"

    edited, note = apply_edit_with_note(
        text, "alpha = compute_value(1)\nbeta = 2", "alpha = 3\nbeta = 4", False
    )

    assert edited == "alpha = 3\nbeta = 4\n"
    assert note


def test_crlf_file_stays_crlf() -> None:
    text = "def f():\r\n    first = 1\r\n    second = 2\r\n"

    edited, note = apply_edit_with_note(
        text, "  first = 1\n  second = 2", "  first = 10\n  second = 20", False
    )

    assert edited == "def f():\r\n    first = 10\r\n    second = 20\r\n"
    assert note


def test_two_candidate_blocks_give_the_matches_error() -> None:
    text = "if a:\n    do_the_thing()\nif b:\n    do_the_thing()\n"

    with pytest.raises(EditError, match=r"matches 2 places \(lines 2, 4\)"):
        apply_edit_with_note(text, "      do_the_thing()", "      other_thing()", False)


def test_a_new_line_less_indented_than_old_is_not_found() -> None:
    text = "  value = compute()\n  other = 1\n"

    with pytest.raises(EditError, match="old_string was not found"):
        apply_edit_with_note(text, "      value = compute()", "    value = 2", False)


def test_tabs_in_the_file_and_spaces_in_old_are_not_found() -> None:
    text = "def f():\n\tvalue = compute()\n"

    with pytest.raises(EditError, match="old_string was not found"):
        apply_edit_with_note(text, "    value = compute()", "    value = 2", False)


def test_a_short_one_line_old_string_never_matches_line_wise() -> None:
    text = "x = 1\n"

    with pytest.raises(EditError, match="old_string was not found"):
        apply_edit_with_note(text, "    x = 1", "    x = 2", False)


def test_an_exact_match_has_no_note() -> None:
    edited, note = apply_edit_with_note("a = 1\nb = 2\n", "b = 2", "b = 3", False)

    assert (edited, note) == ("a = 1\nb = 3\n", "")
    assert apply_edit("a = 1\nb = 2\n", "b = 2", "b = 3", False) == "a = 1\nb = 3\n"


def test_replace_all_never_uses_the_line_wise_match() -> None:
    with pytest.raises(EditError, match="old_string was not found"):
        apply_edit_with_note("value = compute()\n", "    value = compute()", "    value = 2", True)


def test_a_block_at_the_end_of_a_file_without_a_final_newline_keeps_that() -> None:
    edited, _ = apply_edit_with_note(
        "if x:\n    run_the_job()", "  run_the_job()", "  run_other_job()", False
    )

    assert edited == "if x:\n    run_other_job()"

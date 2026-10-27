from __future__ import annotations

import difflib
from typing import Any

import pytest

from patching import Hunk, PatchConflictError, PatchFormatError, apply_patch, parse_patch

ORIGINAL = "one\ntwo\nthree\nfour\nfive\nsix\nseven\neight\n"


def test_exception_classes() -> None:
    assert issubclass(PatchFormatError, ValueError) and issubclass(PatchConflictError, ValueError)
    assert not issubclass(PatchConflictError, PatchFormatError)
    assert not issubclass(PatchFormatError, PatchConflictError)


# ---------- parsing ----------


def test_parse_ignores_headers_and_reads_counts_and_lines() -> None:
    patch = (
        "diff --git a/f.txt b/f.txt\nindex 83db48f..bf2a6c1 100644\n--- a/f.txt\n+++ b/f.txt\n"
        "@@ -2,3 +2,3 @@ def section():\n two\n-three\n+THREE\n four\n"
        "@@ -7 +7,2 @@\n-seven\n+7\n+7b\n"
    )
    first, second = parse_patch(patch)
    assert isinstance(first, Hunk)
    assert (first.old_start, first.old_count, first.new_start, first.new_count) == (2, 3, 2, 3)
    assert first.lines == [(" ", "two"), ("-", "three"), ("+", "THREE"), (" ", "four")]
    assert (second.old_start, second.old_count, second.new_start, second.new_count) == (7, 1, 7, 2)
    assert second.lines == [("-", "seven"), ("+", "7"), ("+", "7b")]
    assert first.old_no_newline is False and first.new_no_newline is False


def test_parse_empty_and_headers_only() -> None:
    assert parse_patch("") == []
    assert parse_patch("--- a/x\n+++ b/x\n") == []
    assert apply_patch(ORIGINAL, "") == ORIGINAL
    assert apply_patch(ORIGINAL, "--- a\n+++ b\n") == ORIGINAL


def test_parse_no_newline_markers() -> None:
    (hunk,) = parse_patch("@@ -1,2 +1,2 @@\n a\n-b\n\\ No newline at end of file\n+c\n")
    assert (hunk.old_no_newline, hunk.new_no_newline) == (True, False)
    (hunk,) = parse_patch("@@ -1,2 +1,2 @@\n a\n-b\n+c\n\\ No newline at end of file\n")
    assert (hunk.old_no_newline, hunk.new_no_newline) == (False, True)
    (hunk,) = parse_patch("@@ -1 +1 @@\n a\n\\ No newline at end of file\n")
    assert (hunk.old_no_newline, hunk.new_no_newline) == (True, True)


def test_body_lines_that_look_like_file_headers_are_content() -> None:
    patch = "@@ -1 +1 @@\n--- a\n+++ b\n"
    (hunk,) = parse_patch(patch)
    assert hunk.lines == [("-", "-- a"), ("+", "++ b")]
    assert apply_patch("-- a\n", patch) == "++ b\n"


def test_blank_line_and_single_space_are_both_empty_context() -> None:
    text = "a\n\nb\n"
    for blank in ("\n", " \n"):
        patch = f"@@ -1,3 +1,3 @@\n a\n{blank}-b\n+B\n"
        assert apply_patch(text, patch) == "a\n\nB\n"
        assert parse_patch(patch)[0].lines[1] == (" ", "")


def test_trailing_blank_lines_after_hunks_are_fine() -> None:
    assert apply_patch("a\n", "@@ -1 +1 @@\n-a\n+b\n\n\n") == "b\n"


@pytest.mark.parametrize(
    "patch",
    [
        "@@ -1,2 +1,2 @@\n a\n",
        "@@ -1,2 +1,2 @@\n a\n@@ -5 +5 @@\n-x\n+y\n",
        "@@ -1 +1 @@\n-a\n+b\n+c\n",
        "@@ -1 +1 @@\n-a\n+b\ngarbage\n",
        "@@ -1 +1 @@\n?a\n",
        "@@ -a +1 @@\n-x\n+y\n",
        "@@ -1 +1\n-a\n+b\n",
        "@@ -1,1 +1,1 @@x\n-a\n+b\n",
        "@@ @@\n",
        "@@ -1 +1 @@\n\\ No newline at end of file\n-a\n+b\n",
        "@@ -1 +1 @@\n",
    ],
)
def test_malformed_patches(patch: str) -> None:
    with pytest.raises(PatchFormatError):
        parse_patch(patch)
    with pytest.raises(PatchFormatError):
        apply_patch("a\n", patch)


# ---------- applying ----------


def test_replace_in_the_middle() -> None:
    patch = "--- a/f\n+++ b/f\n@@ -2,3 +2,3 @@\n two\n-three\n+THREE\n four\n"
    assert apply_patch(ORIGINAL, patch) == ORIGINAL.replace("three", "THREE")


def test_two_hunks_and_growing_and_shrinking() -> None:
    patch = "@@ -2,2 +2,3 @@\n two\n-three\n+3\n+3b\n@@ -7,2 +8 @@ x\n-seven\n eight\n"
    assert apply_patch(ORIGINAL, patch) == "one\ntwo\n3\n3b\nfour\nfive\nsix\neight\n"


def test_insert_after_a_line_with_zero_count() -> None:
    assert apply_patch(ORIGINAL, "@@ -3,0 +4,2 @@\n+x\n+y\n").splitlines()[:6] == ["one", "two", "three", "x", "y", "four"]


def test_insert_at_the_very_beginning_and_end() -> None:
    assert apply_patch(ORIGINAL, "@@ -0,0 +1 @@\n+first\n") == "first\n" + ORIGINAL
    assert apply_patch(ORIGINAL, "@@ -8,0 +9 @@\n+nine\n") == ORIGINAL + "nine\n"


def test_create_from_empty_and_delete_everything() -> None:
    assert apply_patch("", "@@ -0,0 +1,2 @@\n+a\n+b\n") == "a\nb\n"
    assert apply_patch("a\nb\n", "@@ -1,2 +0,0 @@\n-a\n-b\n") == ""


def test_pure_deletion_hunk() -> None:
    assert apply_patch(ORIGINAL, "@@ -2,2 +1,0 @@\n-two\n-three\n") == "one\nfour\nfive\nsix\nseven\neight\n"


def test_unchanged_lines_are_not_touched() -> None:
    text = "keep this\nline  \t\nz\n"
    assert apply_patch(text, "@@ -3 +3 @@\n-z\n+Z\n") == "keep this\nline  \t\nZ\n"


def test_no_newline_at_end_of_file_cases() -> None:
    both = "@@ -1,2 +1,2 @@\n a\n-b\n\\ No newline at end of file\n+c\n\\ No newline at end of file\n"
    assert apply_patch("a\nb", both) == "a\nc"
    add_newline = "@@ -1,2 +1,2 @@\n a\n-b\n\\ No newline at end of file\n+b\n"
    assert apply_patch("a\nb", add_newline) == "a\nb\n"
    drop_newline = "@@ -1,2 +1,2 @@\n a\n-b\n+b\n\\ No newline at end of file\n"
    assert apply_patch("a\nb\n", drop_newline) == "a\nb"
    append_after = "@@ -2 +2,2 @@\n-b\n\\ No newline at end of file\n+b\n+c\n"
    assert apply_patch("a\nb", append_after) == "a\nb\nc\n"


def test_unterminated_last_line_gets_a_terminator_when_lines_follow() -> None:
    patch = "@@ -2,0 +3 @@\n+tail\n"
    assert apply_patch("a\nb", patch) == "a\nb\ntail\n"


def test_crlf_text_keeps_its_endings_and_added_lines_use_crlf() -> None:
    text = "a\r\nb\r\nc\r\n"
    assert apply_patch(text, "@@ -2 +2,2 @@\n-b\n+B\n+B2\n") == "a\r\nB\r\nB2\r\nc\r\n"
    assert apply_patch(text, "@@ -2 +2 @@\r\n-b\r\n+B\r\n") == "a\r\nB\r\nc\r\n"  # a CRLF patch works the same


def test_added_lines_use_the_first_terminator_of_the_text() -> None:
    assert apply_patch("a\nb\r\nc\n", "@@ -2 +2 @@\n-b\n+B\n") == "a\nB\nc\n"
    assert apply_patch("a\r\nb\nc\n", "@@ -2 +2 @@\n-b\n+B\n") == "a\r\nB\r\nc\n"
    assert apply_patch("", "@@ -0,0 +1 @@\n+x\n") == "x\n"
    assert apply_patch("only", "@@ -1 +1,2 @@\n-only\n\\ No newline at end of file\n+only\n+two\n") == "only\ntwo\n"


def test_a_lone_carriage_return_is_part_of_the_line() -> None:
    text = "a\rb\nc\n"
    assert apply_patch(text, "@@ -1 +1 @@\n-a\rb\n+x\n") == "x\nc\n"
    with pytest.raises(PatchConflictError):
        apply_patch(text, "@@ -1 +1 @@\n-a\n+x\n")


# ---------- exact failure behaviour ----------


def test_conflict_reports_hunk_line_expected_and_found() -> None:
    text = "one\ntwo\nTHREE\nfour\n"
    with pytest.raises(PatchConflictError) as raised:
        apply_patch(text, "@@ -2,3 +2,3 @@\n two\n-three\n+x\n four\n")
    error = raised.value
    assert (error.hunk, error.line, error.expected, error.found) == (1, 3, "three", "THREE")


def test_conflict_in_the_second_hunk() -> None:
    patch = "@@ -1 +1 @@\n-one\n+ONE\n@@ -4 +4 @@\n-five\n+x\n"
    with pytest.raises(PatchConflictError) as raised:
        apply_patch(ORIGINAL, patch)
    assert (raised.value.hunk, raised.value.line, raised.value.expected, raised.value.found) == (2, 4, "five", "four")


def test_whitespace_differences_are_conflicts() -> None:
    for text in ("a \nb\n", " a\nb\n", "a\t\nb\n"):
        with pytest.raises(PatchConflictError):
            apply_patch(text, "@@ -1,2 +1,2 @@\n a\n-b\n+B\n")


def test_no_searching_the_right_lines_at_the_wrong_position_conflict() -> None:
    with pytest.raises(PatchConflictError) as raised:
        apply_patch("x\ny\nz\n", "@@ -1 +1 @@\n-z\n+Z\n")
    assert (raised.value.hunk, raised.value.line, raised.value.expected, raised.value.found) == (1, 1, "z", "x")
    with pytest.raises(PatchConflictError):
        apply_patch("x\ny\nz\n", "@@ -2 +2 @@\n-z\n+Z\n")


def test_context_lines_must_match_too() -> None:
    with pytest.raises(PatchConflictError) as raised:
        apply_patch("a\nb\nc\n", "@@ -1,3 +1,3 @@\n a\n-b\n+B\n X\n")
    assert (raised.value.line, raised.value.expected, raised.value.found) == (3, "X", "c")


def test_hunk_running_past_the_end() -> None:
    with pytest.raises(PatchConflictError) as raised:
        apply_patch("a\n", "@@ -1,2 +1,2 @@\n a\n-b\n+B\n")
    assert (raised.value.hunk, raised.value.line, raised.value.expected, raised.value.found) == (1, 2, "b", None)


def test_start_beyond_the_text_conflicts() -> None:
    with pytest.raises(PatchConflictError):
        apply_patch("a\n", "@@ -5 +5 @@\n-x\n+y\n")
    with pytest.raises(PatchConflictError):
        apply_patch("a\n", "@@ -5,0 +6 @@\n+y\n")
    with pytest.raises(PatchConflictError):
        apply_patch("", "@@ -1 +1 @@\n-x\n+y\n")


def test_hunks_out_of_order_or_overlapping_are_format_errors() -> None:
    with pytest.raises(PatchFormatError):
        apply_patch(ORIGINAL, "@@ -3 +3 @@\n-three\n+3\n@@ -1 +1 @@\n-one\n+1\n")
    with pytest.raises(PatchFormatError):
        apply_patch(ORIGINAL, "@@ -1,2 +1,2 @@\n one\n-two\n+2\n@@ -2 +2 @@\n-two\n+x\n")


def test_adjacent_hunks_are_fine() -> None:
    patch = "@@ -1 +1 @@\n-one\n+1\n@@ -2 +2 @@\n-two\n+2\n"
    assert apply_patch(ORIGINAL, patch).startswith("1\n2\nthree\n")


# ---------- reverse ----------


def test_reverse_undoes_the_patch() -> None:
    patch = "@@ -2,3 +2,3 @@\n two\n-three\n+THREE\n four\n@@ -7,2 +7,3 @@\n seven\n+7b\n eight\n"
    patched = apply_patch(ORIGINAL, patch)
    assert patched != ORIGINAL
    assert apply_patch(patched, patch, reverse=True) == ORIGINAL


def test_reverse_of_insertion_and_deletion_hunks() -> None:
    insert = "@@ -3,0 +4,2 @@\n+x\n+y\n"
    assert apply_patch(apply_patch(ORIGINAL, insert), insert, reverse=True) == ORIGINAL
    delete = "@@ -2,2 +1,0 @@\n-two\n-three\n"
    assert apply_patch(apply_patch(ORIGINAL, delete), delete, reverse=True) == ORIGINAL
    with pytest.raises(PatchConflictError):
        apply_patch(ORIGINAL, insert, reverse=True)  # x and y are not there


def test_reverse_swaps_the_no_newline_flags() -> None:
    patch = "@@ -1,2 +1,2 @@\n a\n-b\n\\ No newline at end of file\n+b\n"
    assert apply_patch("a\nb\n", patch, reverse=True) == "a\nb"


PAIRS = [
    ("a\nb\nc\n", "a\nB\nc\n"),
    ("a\nb\nc\n", ""),
    ("", "a\nb\n"),
    ("1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n", "1\n2\nthree\n4\n5\n6\n7\n8\n9\n10\n11\n"),
    ("x\ny\nz\n", "x\nnew\ny\nz\nend\n"),
    ("p\nq\nr\ns\nt\n", "q\nr\nt\n"),
    ("same\nsame\nsame\nsame\n", "same\nsame\nchanged\nsame\nsame\n"),
]


@pytest.mark.parametrize("context", [0, 1, 3])
@pytest.mark.parametrize("before, after", PAIRS)
def test_round_trip_with_difflib_patches(before: str, after: str, context: int) -> None:
    patch = "".join(
        difflib.unified_diff(before.splitlines(True), after.splitlines(True), "a/f", "b/f", n=context)
    )
    assert apply_patch(before, patch) == after
    assert apply_patch(after, patch, reverse=True) == before


def test_patch_text_can_be_passed_without_a_final_newline() -> None:
    assert apply_patch("a\n", "@@ -1 +1 @@\n-a\n+b") == "b\n"


def test_defaults_count_one() -> None:
    (hunk,) = parse_patch("@@ -5 +7 @@\n-x\n+y\n")
    assert (hunk.old_count, hunk.new_count) == (1, 1)
    other: Any = parse_patch("@@ -5,0 +6 @@\n+y\n")[0]
    assert (other.old_count, other.new_count) == (0, 1)

"""Line-wise matching for edit_file (HW3): an old_string that differs from the file only in indentation or
trailing spaces is applied, because the model often gets the whitespace wrong when the text is right."""

from __future__ import annotations

import os
from dataclasses import dataclass

from forge.errors import ForgeError

MIN_SINGLE_LINE_CHARS = 8  # a shorter one-line old_string is too easy to hit on the wrong line


class EditError(ForgeError):
    pass


@dataclass(frozen=True)
class LineMatch:
    start: int  # index of the first matched file line
    count: int
    file_indent: str
    old_indent: str


def _indent_of(line: str) -> str:
    return line[: len(line) - len(line.lstrip())]


def common_indent(lines: list[str]) -> str:
    """Leading whitespace shared by all non-blank lines (blank lines are ignored)."""
    indents = [_indent_of(line) for line in lines if line.strip()]
    return os.path.commonprefix(indents) if indents else ""


def _same_block(file_block: list[str], old_lines: list[str], file_indent: str, old_indent: str) -> bool:
    for file_line, old_line in zip(file_block, old_lines, strict=True):
        if bool(file_line.strip()) != bool(old_line.strip()):
            return False
        if not file_line.strip():
            continue
        if file_line.rstrip()[len(file_indent) :] != old_line.rstrip()[len(old_indent) :]:
            return False
    return True


def find_line_matches(file_lines: list[str], old_lines: list[str]) -> list[LineMatch]:
    """Every block of consecutive file lines equal to `old_lines` after removing trailing whitespace and each
    side's common indentation. Tabs on one side and spaces on the other never match."""
    if not any(line.strip() for line in old_lines):
        return []
    if len(old_lines) == 1 and len(old_lines[0].strip()) < MIN_SINGLE_LINE_CHARS:
        return []
    old_indent = common_indent(old_lines)
    anchor = next(line.strip() for line in old_lines if line.strip())
    anchor_offset = next(index for index, line in enumerate(old_lines) if line.strip())
    found: list[LineMatch] = []
    for start in range(len(file_lines) - len(old_lines) + 1):
        if file_lines[start + anchor_offset].strip() != anchor:
            continue
        block = file_lines[start : start + len(old_lines)]
        file_indent = common_indent(block)
        if file_indent and old_indent and ("\t" in file_indent) != ("\t" in old_indent):
            continue
        if _same_block(block, old_lines, file_indent, old_indent):
            found.append(LineMatch(start, len(old_lines), file_indent, old_indent))
    return found


def reindent(new_lines: list[str], match: LineMatch) -> list[str] | None:
    """`new` moved from the indentation the model assumed to the file's; None when a line of it is less
    indented than that assumption (the intended indentation cannot be known)."""
    out = []
    for line in new_lines:
        if not line.strip():
            out.append(line)
        elif line.startswith(match.old_indent):
            out.append(match.file_indent + line[len(match.old_indent) :])
        else:
            return None
    return out


def line_ending_of(block: list[str], text: str) -> str:
    for line in block:
        if line.endswith("\r\n"):
            return "\r\n"
        if line.endswith("\n"):
            return "\n"
    return "\r\n" if "\r\n" in text else "\n"


def apply_line_match(text: str, old: str, new: str) -> tuple[str, str] | None:
    """The edited text and the note, or None when no block matches (or the new indentation is unknowable).
    Raises EditError when more than one block matches."""
    file_lines = text.splitlines(keepends=True)
    matches = find_line_matches(file_lines, old.splitlines())
    if not matches:
        return None
    if len(matches) > 1:
        lines = ", ".join(str(match.start + 1) for match in matches[:10])
        raise EditError(
            f"old_string matches {len(matches)} places (lines {lines}). "
            "Add surrounding lines to make it unique, or set replace_all."
        )
    match = matches[0]
    new_lines = reindent(new.splitlines(), match)
    if new_lines is None:
        return None
    block = file_lines[match.start : match.start + match.count]
    ending = line_ending_of(block, text)
    replaced_had_ending = block[-1].endswith(("\n", "\r"))
    replacement = ending.join(new_lines) + (ending if new_lines and replaced_had_ending else "")
    edited = (
        "".join(file_lines[: match.start]) + replacement + "".join(file_lines[match.start + match.count :])
    )
    note = (
        f"Matched lines {match.start + 1} to {match.start + match.count} after ignoring a difference in "
        "indentation or trailing spaces; the new text was indented to fit."
    )
    return edited, note

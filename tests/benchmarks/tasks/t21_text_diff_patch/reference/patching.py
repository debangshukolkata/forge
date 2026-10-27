"""Unified diff parsing and exact application."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?$")


class PatchFormatError(ValueError):
    """The patch text is malformed."""


class PatchConflictError(ValueError):
    """The patch does not fit the text."""

    def __init__(self, hunk: int, line: int, expected: str, found: str | None) -> None:
        super().__init__(f"hunk {hunk}: line {line}: expected {expected!r}, found {found!r}")
        self.hunk, self.line, self.expected, self.found = hunk, line, expected, found


@dataclass
class Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[tuple[str, str]] = field(default_factory=list)
    old_no_newline: bool = False
    new_no_newline: bool = False


def _split_lines(text: str) -> list[str]:
    """Lines including their terminator; only \\n and \\r\\n end a line."""
    return re.findall(r"[^\n]*\n|[^\n]+", text)


def _content(line: str) -> str:
    if line.endswith("\r\n"):
        return line[:-2]
    if line.endswith("\n"):
        return line[:-1]
    return line


def parse_patch(patch: str) -> list[Hunk]:
    lines = [_content(line) for line in _split_lines(patch)]
    hunks: list[Hunk] = []
    index = 0
    while index < len(lines) and not lines[index].startswith("@@"):
        index += 1
    while index < len(lines):
        line = lines[index]
        if line.startswith("\\") or not line:
            index += 1  # stray markers and blank lines between hunks
            continue
        match = HEADER.match(line)
        if not match:
            raise PatchFormatError(f"bad hunk header or unexpected line: {line!r}")
        old_start, old_count, new_start, new_count = (
            int(g) if g is not None else 1 for g in match.groups()
        )
        hunk = Hunk(old_start, old_count, new_start, new_count)
        index += 1
        old_seen = new_seen = 0
        while old_seen < old_count or new_seen < new_count:
            if index >= len(lines) or lines[index].startswith("@@") and lines[index] != "":
                raise PatchFormatError("hunk is shorter than its header says")
            body = lines[index]
            index += 1
            if body.startswith("\\"):
                _mark_no_newline(hunk)
                continue
            tag, text = (" ", "") if body == "" else (body[0], body[1:])
            if tag not in " -+":
                raise PatchFormatError(f"bad line in hunk: {body!r}")
            old_seen += tag in " -"
            new_seen += tag in " +"
            hunk.lines.append((tag, text))
        if old_seen > old_count or new_seen > new_count:
            raise PatchFormatError("hunk is longer than its header says")
        while index < len(lines) and lines[index].startswith("\\"):
            _mark_no_newline(hunk)
            index += 1
        hunks.append(hunk)
        while index < len(lines) and lines[index] == "":
            index += 1
        if index < len(lines) and not lines[index].startswith("@@"):
            raise PatchFormatError(f"unexpected line after a hunk: {lines[index]!r}")
    return hunks


def _mark_no_newline(hunk: Hunk) -> None:
    if not hunk.lines:
        raise PatchFormatError("'no newline' marker without a line before it")
    tag = hunk.lines[-1][0]
    if tag in " -":
        hunk.old_no_newline = True
    if tag in " +":
        hunk.new_no_newline = True


def _reversed(hunk: Hunk) -> Hunk:
    swap = {" ": " ", "-": "+", "+": "-"}
    return Hunk(
        hunk.new_start,
        hunk.new_count,
        hunk.old_start,
        hunk.old_count,
        [(swap[tag], text) for tag, text in hunk.lines],
        hunk.new_no_newline,
        hunk.old_no_newline,
    )


def apply_patch(text: str, patch: str, reverse: bool = False) -> str:
    hunks = parse_patch(patch)
    if reverse:
        hunks = [_reversed(h) for h in hunks]
    original = _split_lines(text)
    eol = "\r\n" if original and original[0].endswith("\r\n") else "\n"
    out: list[str] = []

    def emit(line: str) -> None:
        if out and not out[-1].endswith("\n"):
            out[-1] += eol  # lines follow an unterminated line
        out.append(line)

    position = 0
    for number, hunk in enumerate(hunks, start=1):
        start = hunk.old_start - 1 if hunk.old_count > 0 else hunk.old_start
        if start < position:
            raise PatchFormatError(f"hunk {number} overlaps the previous one or is out of order")
        if start > len(original):
            first = next((t for tag, t in hunk.lines if tag in " -"), "")
            raise PatchConflictError(number, start + 1, first, None)
        for line in original[position:start]:
            emit(line)
        cursor = start
        for tag, wanted in hunk.lines:
            if tag in " -":
                found = _content(original[cursor]) if cursor < len(original) else None
                if found != wanted:
                    raise PatchConflictError(number, cursor + 1, wanted, found)
                if tag == " ":
                    emit(original[cursor])
                cursor += 1
            else:
                emit(wanted + eol)
        if hunk.new_no_newline and out and out[-1].endswith("\n"):
            out[-1] = _content(out[-1])
        position = cursor
    for line in original[position:]:
        emit(line)
    return "".join(out)

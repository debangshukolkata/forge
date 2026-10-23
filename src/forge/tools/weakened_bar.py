"""Weakened quality bar (idea from addyosmani/agent-skills, constraint-driven-development; MIT): a task must not turn a check off to get to
green. For each source file DebCraft wrote, the text is compared with the baseline copy of the original (a new file has none): a rise in
the number of suppression comments (`# noqa`, `# type: ignore`, `@ts-ignore`, `eslint-disable`), of skipped or expected-to-fail tests, or a
drop in the number of tests, is reported. A count is compared, not a line, so moving a suppression is not flagged. Never raises."""

from __future__ import annotations

import re
from pathlib import Path

SUPPRESSIONS = re.compile(
    r"#\s*noqa|#\s*type:\s*ignore|#\s*pylint:\s*disable|#\s*pragma:\s*no cover|@ts-(?:ignore|nocheck)|eslint-disable|istanbul ignore|nosemgrep"
)
SKIPS = re.compile(
    r"pytest\.mark\.(?:skip|xfail)\b|pytest\.(?:skip|xfail)\(|unittest\.skip|\b(?:it|test|describe)\.skip\(|\bxit\(|\bxdescribe\("
)
TEST_DEFINITION = re.compile(r"^\s*(?:async\s+)?def\s+test_\w+|^\s*(?:it|test)\(", re.MULTILINE)
SOURCE_SUFFIXES = (".py", ".js", ".jsx", ".ts", ".tsx")


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def weakened_bar_findings(written: list[tuple[str, Path, Path]]) -> list[str]:
    """`written` holds (relative path, current file, baseline copy); a baseline that does not exist means a new file."""
    found: list[str] = []
    for relative, current, baseline in written:
        if not relative.endswith(SOURCE_SUFFIXES):
            continue
        before = _read(baseline) or ""
        after = _read(current)
        if after is None:
            if not before:
                continue
            after = ""  # a deleted file: its tests are gone
        added_suppressions = len(SUPPRESSIONS.findall(after)) - len(SUPPRESSIONS.findall(before))
        if added_suppressions > 0:
            found.append(
                f"bar: {relative}: {added_suppressions} new check suppression(s) (noqa / type: ignore / ts-ignore / eslint-disable): fix the cause instead of silencing the check"
            )
        added_skips = len(SKIPS.findall(after)) - len(SKIPS.findall(before))
        if added_skips > 0:
            found.append(
                f"bar: {relative}: {added_skips} test(s) newly skipped or marked xfail: make them pass instead"
            )
        lost_tests = len(TEST_DEFINITION.findall(before)) - len(TEST_DEFINITION.findall(after))
        if lost_tests > 0:
            found.append(
                f"bar: {relative}: {lost_tests} fewer test(s) than before: a failing test is fixed by fixing the code, not by deleting it (unless the spec changed; say so)"
            )
    return found

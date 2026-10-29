"""Changed expectations in the user's existing tests (D-560).

When an edit rewrites or removes an assertion in a test file that was in the original repository, the change may be a fix of the
test or a bug the test was guarding (TI3, D-559: a count change made new claim numbers repeat an existing one and the test was edited
to expect the duplicate). Nothing is refused: the edit result names the changed assertions and asks for a reason, and the delivery
report lists them so the user sees them without reading every diff. Added assertions are not listed: they only check more."""

from __future__ import annotations

import difflib
import json
import re
from typing import Any

from forge.workspace.workspace import Workspace

RECORD = "test_expectations.jsonl"
TEST_FILE = re.compile(
    r"(^|/)(tests?/.*\.py$|test_[^/]*\.py$|[^/]*_test\.py$|[^/]*\.(test|spec)\.[cm]?[jt]sx?$|__tests__/)",
    re.IGNORECASE,
)
ASSERTION = re.compile(r"^\s*(assert\b|self\.assert\w*\(|expect\(|assert_\w+\(|pytest\.raises\()")
MAX_SHOWN = 5
SAME_ASSERTION = 0.6  # similarity above which an added assertion is the rewrite of a removed one


def is_existing_test(workspace: Workspace, relative: str) -> bool:
    """A test file that was in the original repository (the model's own new tests are its business)."""
    path = relative.replace("\\", "/").lstrip("./")
    return bool(TEST_FILE.search(path)) and path in workspace.manifest.files


def changed_assertions(before: str, after: str) -> list[tuple[str, str]]:
    """(old, new) per assertion line that was rewritten or removed; new is "" for a removed one."""
    old_lines, new_lines = before.splitlines(), after.splitlines()
    pairs: list[tuple[str, str]] = []
    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag not in ("replace", "delete"):
            continue
        removed = [line.strip() for line in old_lines[i1:i2] if ASSERTION.match(line)]
        added = [line.strip() for line in new_lines[j1:j2] if ASSERTION.match(line)]
        for old in removed:
            # The rewrite of an assertion looks like it; an unrelated new assertion in the same block is not its replacement.
            scored = [(difflib.SequenceMatcher(a=old, b=candidate).ratio(), candidate) for candidate in added]
            score, new = max(scored, default=(0.0, ""))
            if score < SAME_ASSERTION:
                new = ""
            elif new:
                added.remove(new)
            if old != new:
                pairs.append((old, new))
    return pairs


def note(relative: str, pairs: list[tuple[str, str]]) -> str:
    shown = "\n".join(
        f"  - `{old}` -> {f'`{new}`' if new else '(removed)'}" for old, new in pairs[:MAX_SHOWN]
    )
    more = f"\n  - and {len(pairs) - MAX_SHOWN} more" if len(pairs) > MAX_SHOWN else ""
    return (
        f"You changed {len(pairs)} expectation(s) in an existing test of the user's ({relative}):\n{shown}{more}\n"
        "If the old value protected something (uniqueness, ordering, a sequence, an error), fix the code instead and keep the test. "
        "Otherwise say in your final summary why the old value is wrong under the new requirement. These changes are listed "
        "in the delivery report for the user."
    )


def record(workspace: Workspace, relative: str, pairs: list[tuple[str, str]]) -> None:
    target = workspace.jail.check(workspace.forge_dir / RECORD)
    with target.open("a", encoding="utf-8") as log:
        for old, new in pairs:
            log.write(json.dumps({"path": relative, "old": old, "new": new}, ensure_ascii=False) + "\n")


def take_all(workspace: Workspace) -> list[dict[str, Any]]:
    """Every recorded change since the last delivery; the record starts empty again for the next change request."""
    target = workspace.jail.check(workspace.forge_dir / RECORD)
    if not target.is_file():
        return []
    entries = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines() if line.strip()]
    target.unlink()
    return entries


def report_lines(entries: list[dict[str, Any]]) -> list[str]:
    if not entries:
        return []
    lines = [
        "## Changed test expectations",
        "",
        "Assertions in tests that were already in your repository and were changed or removed. Check each: a changed expected value "
        "can be a correct update or a bug the test was guarding.",
        "",
    ]
    for entry in entries:
        new = f"`{entry['new']}`" if entry["new"] else "(removed)"
        lines.append(f"- {entry['path']}: `{entry['old']}` -> {new}")
    return [*lines, ""]

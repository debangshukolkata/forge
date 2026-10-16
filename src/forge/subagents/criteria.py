"""The acceptance criteria check (D-456): did the verifier walk the plan's criteria in the running application, and which are not met?

The verifier reports one line per criterion (`3. MET: ...`, `4. NOT MET: ...`, `5. UNCHECKED: ...`). The task_update gate reads them: a large task that has criteria cannot be finished while one is NOT MET (three rounds,
as for the design critic) and cannot be finished at all before the criteria were checked since the last change. A passing build and passing tests are not a finished application."""

from __future__ import annotations

import re
from pathlib import Path

CRITERIA_ROUND_LIMIT = (
    3  # checks that still show a criterion not met before the builder may finish anyway and say so
)
LINE = re.compile(
    r"^[ \t]*(?:[-*][ \t]*)?\**(\d+)[.)]\**[ \t]*\**(NOT MET|MET|UNCHECKED)\**(?![A-Za-z])(.*)$",
    re.IGNORECASE | re.MULTILINE,
)
DASHES = ": -" + chr(0x2013) + chr(0x2014) + "*"
HEADING = re.compile(r"^#{1,4}[ \t]*acceptance criteria\b.*$", re.IGNORECASE | re.MULTILINE)


def parse_criteria(report: str) -> dict[str, list[tuple[int, str]]]:
    """{'met': [...], 'not_met': [...], 'unchecked': [...]} as (number, evidence); empty when the report has no criteria lines."""
    found: dict[str, list[tuple[int, str]]] = {"met": [], "not_met": [], "unchecked": []}
    for number, state, evidence in LINE.findall(report):
        key = state.upper().replace(" ", "_").lower()
        found[key].append((int(number), evidence.lstrip(DASHES).strip()[:200]))
    return found


def has_criteria_lines(parsed: dict[str, list[tuple[int, str]]]) -> bool:
    return any(parsed.values())


def project_criteria(forge_dir: Path) -> str:
    """The acceptance criteria written in .forge/REQUIREMENTS.md (or ANALYSIS.md next to the project), as text; '' when the project has none."""
    for path in (
        forge_dir / "REQUIREMENTS.md",
        forge_dir.parent / "project" / "ANALYSIS.md",
        forge_dir.parent / "ANALYSIS.md",
    ):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        match = HEADING.search(text)
        if match is None:
            continue
        rest = text[match.end() :]
        nxt = re.search(r"^#{1,4}[ \t]+\S", rest, re.MULTILINE)
        body = (rest[: nxt.start()] if nxt else rest).strip()
        if body:
            return body[:3000]
    return ""


def criteria_refusal(criteria: str, parsed: dict[str, list[tuple[int, str]]] | None, rounds: int) -> str:
    """The refusal text for task_update, or '' when the criteria are cleared."""
    if parsed is None:
        return (
            "Not accepted: the plan's acceptance criteria have not been checked against the running application since your last change. Start the app and spawn_subagent with agent 'verifier', "
            "giving it these criteria and the roles to act as; it walks each one with real clicks and reports it MET, NOT MET or UNCHECKED, plus what the user would be stuck on. Criteria:\n"
            + criteria
        )
    missing = parsed["not_met"]
    if missing and rounds < CRITERIA_ROUND_LIMIT:
        listed = "; ".join(f"{number}. {evidence}" for number, evidence in missing)
        return (
            f"Not accepted: acceptance criteria not met (check {rounds} of {CRITERIA_ROUND_LIMIT}): {listed}. Fix them (or, for one you decide is wrong or out of scope, say why in your verification), then run the verifier "
            "again on these criteria only."
        )
    return ""

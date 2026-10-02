"""Compact pytest summaries (spec §9.8, D-159): the counts plus the first N failures with file:line, for
`forge diagnose` and the restructure before/after check. The model itself reads raw, capped pytest output."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MAX_FAILURES = 5

_COUNTS = re.compile(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed|deselected|warnings?)")
_SUMMARY_LINE = re.compile(r"^=*\s*(?:\d+ \w+(?:, )?)+.* in [\d.]+s", re.MULTILINE)
_SHORT_FAILURE = re.compile(r"^(FAILED|ERROR) (\S+)(?: - (.*))?$", re.MULTILINE)
_LOCATION = re.compile(r"^([\w./\\-]+\.py):(\d+): (\w+(?:Error|Exception|Failed)?\w*)", re.MULTILINE)
_COLLECTION_ERROR = re.compile(r"^E\s+(\w+(?:Error|Exception)): (.*)$", re.MULTILINE)


@dataclass
class Failure:
    test: str  # node id, or file for collection errors
    error: str  # exception type and message (first line)
    location: str = ""  # file:line where it was raised, when known


@dataclass
class TestReport:
    counts: dict[str, int] = field(default_factory=dict)
    failures: list[Failure] = field(default_factory=list)
    ran: bool = False  # a pytest summary line was seen

    @property
    def passed(self) -> bool:
        # "no tests ran" (nothing collected, e.g. tests written outside the app folder) proves nothing: seen
        # live reported as "[ok] full test suite", contradicting the evidence rule and looping the agent.
        return (
            self.ran
            and self.counts.get("passed", 0) > 0
            and not self.counts.get("failed")
            and not self.counts.get("error")
        )

    def summary(self) -> str:
        if not self.ran:
            return "pytest did not report a result (see the output)."
        counts = ", ".join(f"{n} {kind}" for kind, n in self.counts.items()) or "no tests ran"
        lines = [f"pytest: {counts}"]
        for failure in self.failures[:MAX_FAILURES]:
            where = f" at {failure.location}" if failure.location else ""
            lines.append(f"- {failure.test}: {failure.error}{where}")
        if len(self.failures) > MAX_FAILURES:
            lines.append(f"- … and {len(self.failures) - MAX_FAILURES} more")
        return "\n".join(lines)


def parse_pytest(output: str) -> TestReport:
    report = TestReport()
    summaries = _SUMMARY_LINE.findall(output) or [
        line for line in output.splitlines() if re.search(r"\b(passed|failed|error|no tests ran)\b", line)
    ]
    if summaries:
        last = summaries[-1]
        report.ran = True
        for number, kind in _COUNTS.findall(last):
            key = {"errors": "error", "warnings": "warning"}.get(kind, kind)
            report.counts[key] = report.counts.get(key, 0) + int(number)
    locations = _LOCATION.findall(output)
    for kind, node, message in _SHORT_FAILURE.findall(output):
        test_file = node.split("::")[0].replace("\\", "/")
        where = next(
            (f"{path}:{line}" for path, line, _ in locations if path.replace("\\", "/").endswith(test_file)),
            "",
        )
        # Setup errors (e.g. a missing fixture) have no message in the short summary: the reason is the
        # first "E ..." line of that test's section above — without it the agent can't tell what's wrong.
        error = (message or _section_reason(output, node) or kind).strip()
        report.failures.append(Failure(node, error[:300], where))
    if not report.failures and report.counts.get("error"):
        for exc, message in _COLLECTION_ERROR.findall(output)[:MAX_FAILURES]:
            report.failures.append(Failure("collection", f"{exc}: {message}"[:300]))
    return report


_SECTION = re.compile(r"^_{3,} (?:ERROR at (?:setup|teardown) of |)(.+?) _{3,}$", re.MULTILINE)


def _section_reason(output: str, node: str) -> str:
    """The first 'E  ...' line in the ERRORS/FAILURES section of this test (by its function name)."""
    name = node.split("::")[-1]
    for match in _SECTION.finditer(output):
        if match.group(1).strip().split("::")[-1] != name:
            continue
        section = output[match.end() : match.end() + 6000]
        next_section = _SECTION.search(section)
        body = section[: next_section.start()] if next_section else section
        reason = next((line[1:].strip() for line in body.splitlines() if line.startswith("E ")), "")
        if reason:
            return reason
    return ""

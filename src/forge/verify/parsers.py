"""Compact summaries of tool output (spec §9.8): the pytest summary plus the first N failures with file:line,
ruff/flake8 and mypy diagnostics, and py_compile errors. Also the *error signature* used by stuck detection:
the same failure, with volatile parts (numbers, addresses, temp paths) removed, maps to the same signature."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MAX_FAILURES = 5
MAX_DIAGNOSTICS = 15

_COUNTS = re.compile(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed|deselected|warnings?)")
_SUMMARY_LINE = re.compile(r"^=*\s*(?:\d+ \w+(?:, )?)+.* in [\d.]+s", re.MULTILINE)
_SHORT_FAILURE = re.compile(r"^(FAILED|ERROR) (\S+)(?: - (.*))?$", re.MULTILINE)
_LOCATION = re.compile(r"^([\w./\\-]+\.py):(\d+): (\w+(?:Error|Exception|Failed)?\w*)", re.MULTILINE)
_COLLECTION_ERROR = re.compile(r"^E\s+(\w+(?:Error|Exception)): (.*)$", re.MULTILINE)
_LINT = re.compile(r"^([\w./\\:-]+\.py):(\d+):(\d+): ([A-Z]+\d+) (.*)$", re.MULTILINE)
_MYPY = re.compile(r"^([\w./\\:-]+\.py):(\d+): error: (.*?)(?:\s+\[([\w-]+)\])?$", re.MULTILINE)
_COMPILE = re.compile(r'File "([^"]+)", line (\d+)[\s\S]*?^(\w*Error): (.*)$', re.MULTILINE)
_VOLATILE = [
    (re.compile(r"0x[0-9a-fA-F]+"), "0x…"),
    (re.compile(r"[A-Za-z]:\\[^\s'\"]+|/tmp/[^\s'\"]+"), "<path>"),
    (re.compile(r"\b\d+(\.\d+)?\b"), "N"),
    (re.compile(r"\s+"), " "),
]


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

    def signatures(self) -> list[str]:
        return [signature(f"{f.test} {f.error}") for f in self.failures]


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


@dataclass
class Diagnostic:
    path: str
    line: int
    code: str
    message: str

    def render(self) -> str:
        return f"{self.path}:{self.line}: {self.code} {self.message}"


def parse_lint(output: str) -> list[Diagnostic]:
    return [
        Diagnostic(path.replace("\\", "/"), int(line), code, message.strip())
        for path, line, _col, code, message in _LINT.findall(output)
    ]


def parse_mypy(output: str) -> list[Diagnostic]:
    return [
        Diagnostic(path.replace("\\", "/"), int(line), code or "error", message.strip())
        for path, line, message, code in _MYPY.findall(output)
    ]


def parse_compile(output: str) -> list[Diagnostic]:
    return [
        Diagnostic(path.replace("\\", "/"), int(line), error, message.strip())
        for path, line, error, message in _COMPILE.findall(output)
    ]


def render_diagnostics(title: str, diagnostics: list[Diagnostic]) -> str:
    if not diagnostics:
        return f"{title}: clean"
    lines = [f"{title}: {len(diagnostics)} problem(s)"]
    lines += [f"- {d.render()}" for d in diagnostics[:MAX_DIAGNOSTICS]]
    if len(diagnostics) > MAX_DIAGNOSTICS:
        lines.append(f"- … and {len(diagnostics) - MAX_DIAGNOSTICS} more")
    return "\n".join(lines)


def signature(text: str) -> str:
    """The same error, whatever its line numbers, ids or temp paths."""
    normalised = text.strip()
    for pattern, replacement in _VOLATILE:
        normalised = pattern.sub(replacement, normalised)
    return normalised[:200]


def error_signature(output: str) -> str | None:
    """A signature for a failed command's output: the pytest failures if any, else its last error line."""
    report = parse_pytest(output)
    if report.failures:
        return " | ".join(sorted(set(report.signatures())))
    error_lines = [
        line
        for line in output.splitlines()
        if re.search(r"(Error|Exception|error:|Traceback|FAILED|failed)", line) and not line.startswith("[")
    ]
    return signature(error_lines[-1]) if error_lines else None

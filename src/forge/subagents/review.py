"""The REVIEW phase's second opinion (spec §9.10, §13.2): a reviewer subagent on the reviewer role's model
reads the requirement and the diff (and any file it wants), and reports findings. Together with the
deterministic test guard, blocking findings become a fix task."""

from __future__ import annotations

import re
from dataclasses import dataclass

from forge.errors import ForgeError
from forge.llm.router import LLMRouter
from forge.safety.redact import default_redactor
from forge.subagents.subagent import _run_subagent
from forge.toolkit.base import ToolContext
from forge.tools.registry import ToolRegistry, default_tools
from forge.workspace.output import build_patch, compute_changes
from forge.workspace.workspace import Workspace

REVIEW_ITERATIONS = 20
MAX_DIFF_CHARS = 40_000

REVIEWER_PROMPT = """You are Forge's reviewer subagent: a senior engineer reviewing another agent's change to
this codebase. You can read files and search; you can't edit. Check, in this order:
1. Does the change do what the requirement asks (every acceptance criterion)? Trace each one to the code that
   ships, not to the tests: an external integration the requirement names (a model API, a database, a
   service) must be really called by the production code path; fakes belong in tests only. A production
   path that returns canned values or "stub" results is blocking.
2. Tests: are there tests for the new behaviour, in the repo's style? Were any existing tests weakened,
   skipped or deleted, or assertions loosened, to make things pass? (That is always blocking.)
3. Bugs: wrong logic, unhandled errors, SQL injection (string-built SQL), secrets in code, broken imports.
4. Conventions: does it follow the patterns of the surrounding code (layering, naming, error handling)?
Read the current file before reporting a problem in it: the diff may be older than the code.
Report ONLY real problems, one per line, exactly in this form:
- [blocking] path:line — the problem — the fix — evidence: `the exact offending code, copied from the file`
- [minor] path:line — the problem — the fix
For something MISSING (a required behaviour with no code), quote the requirement sentence instead:
evidence: `…exact words from the requirement…`. A blocking finding without evidence Forge can find in the file
or the requirement is downgraded to minor.
Then a last line: VERDICT: pass   or   VERDICT: changes needed
Blocking = a requirement not met by the shipped code, a bug with a concrete input that breaks it, weakened
tests, or a security problem. At most 5 blocking findings, the most important first. Extra hardening the
requirement didn't ask for (retries, more validation, more tests of edge cases, documentation wording, style)
is minor, never blocking."""

_FINDING = re.compile(r"^\s*-\s*\[(blocking|minor)\]\s*(.+)$", re.IGNORECASE | re.MULTILINE)


MAX_BLOCKING = 5
_QUOTE = re.compile(r"`([^`]+)`")
_PATH = re.compile(r"([\w./\\-]+\.[A-Za-z0-9]+)(?::[\d,-]+)?")


@dataclass
class ReviewFinding:
    blocking: bool
    text: str
    note: str = ""  # why Forge downgraded it to minor

    def render(self) -> str:
        note = f" (downgraded: {self.note})" if self.note else ""
        return f"[{'blocking' if self.blocking else 'minor'}] {self.text}{note}"


@dataclass
class ReviewResult:
    findings: list[ReviewFinding]
    report: str

    @property
    def blocking(self) -> list[ReviewFinding]:
        return [f for f in self.findings if f.blocking]


def parse_review(report: str) -> list[ReviewFinding]:
    return [
        ReviewFinding(level.lower() == "blocking", text.strip()) for level, text in _FINDING.findall(report)
    ]


async def run_reviewer(router: LLMRouter, context: ToolContext, requirement: str) -> ReviewResult | None:
    changes = compute_changes(context.workspace)
    if not changes:
        return None
    patch = build_patch(context.workspace, changes)
    if len(patch) > MAX_DIFF_CHARS:
        patch = patch[:MAX_DIFF_CHARS] + "\n[… diff truncated: read the remaining files directly …]"
    task = (
        f"Requirement:\n{requirement}\n\nChanged files: {', '.join(c.path for c in changes)}\n\n"
        f"Diff (baseline -> now):\n```diff\n{patch}\n```"
    )
    tools = ToolRegistry([t for t in default_tools() if t.read_only])
    report = await _run_subagent(router, context, tools, REVIEWER_PROMPT, task, REVIEW_ITERATIONS, "reviewer")
    findings = verify_findings(context.workspace, parse_review(report), requirement)
    downgraded = [f for f in findings if not f.blocking and f.note]
    if downgraded:
        report += "\n\nForge downgraded to minor:\n" + "\n".join(f"- {f.render()}" for f in downgraded)
    return ReviewResult(findings, report)


def verify_findings(
    workspace: Workspace, findings: list[ReviewFinding], requirement: str
) -> list[ReviewFinding]:
    """Seen live: blocking findings about code that wasn't there (stale diffs, masked text) and wish-lists of
    extra hardening used up the fix rounds. A blocking finding must quote code that is really in the file it
    names (or words of the requirement, for something missing); at most MAX_BLOCKING stay blocking."""
    checked: list[ReviewFinding] = []
    blocking = 0
    for finding in findings:
        if not finding.blocking:
            checked.append(finding)
            continue
        problem = _unverified(workspace, finding.text, requirement)
        if problem is None and blocking >= MAX_BLOCKING:
            problem = f"more than {MAX_BLOCKING} blocking findings"
        if problem is None:
            blocking += 1
            checked.append(finding)
        else:
            checked.append(ReviewFinding(False, finding.text, note=problem))
    return checked


def _unverified(workspace: Workspace, text: str, requirement: str) -> str | None:
    quotes = _QUOTE.findall(text.split("evidence:", 1)[1]) if "evidence:" in text else []
    if not quotes:
        return "no evidence quoted"
    quote = _normalise(quotes[-1])
    if len(quote) < 4:
        return "evidence too short to check"
    if quote in _normalise(requirement):
        return None
    for path in _PATH.findall(text.split("—", 1)[0]):
        try:
            source = workspace.read_text(path)[0]
        except (ForgeError, OSError, ValueError):
            continue
        if quote in _normalise(source) or quote in _normalise(default_redactor.redact(source)):
            return None
    return "the quoted evidence isn't in the file it names"


def _normalise(text: str) -> str:
    return " ".join(text.split())

"""The REVIEW phase's second opinion (spec §9.10, §13.2): a reviewer subagent on the reviewer role's model
reads the requirement and the diff (and any file it wants), and reports findings. Together with the
deterministic test guard, blocking findings become a fix task."""

from __future__ import annotations

import re
from dataclasses import dataclass

from forge.agent.subagent import _run_subagent
from forge.llm.router import LLMRouter
from forge.tools.base import ToolContext
from forge.tools.registry import ToolRegistry, default_tools
from forge.workspace.output import build_patch, compute_changes

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
Report ONLY real problems, one per line, exactly in this form:
- [blocking] path:line — the problem — the fix
- [minor] path:line — the problem — the fix
Then a last line: VERDICT: pass   or   VERDICT: changes needed
Blocking = wrong behaviour, missing required behaviour, weakened tests, security problems. Style = minor."""

_FINDING = re.compile(r"^\s*-\s*\[(blocking|minor)\]\s*(.+)$", re.IGNORECASE | re.MULTILINE)


@dataclass
class ReviewFinding:
    blocking: bool
    text: str

    def render(self) -> str:
        return f"[{'blocking' if self.blocking else 'minor'}] {self.text}"


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
    return ReviewResult(parse_review(report), report)

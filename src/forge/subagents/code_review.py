"""Two-axis code review (TODO C4, D-308): the change is read by two independent reviewers at the same time, each in its own fresh context.
One checks the project's documented standards (and a short list of common code smells as judgement calls), the other checks the
request: what was asked, nothing missing, nothing extra. Their reports stay apart so one axis cannot hide the other. Blocking
findings must quote evidence that is really in the file (the existing `verify_findings` rule). Ideas from the MIT-licensed Superpowers and
mattpocock/skills (docs/SKILLS_STUDY.md), in our own words."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path

from forge.llm.router import LLMRouter
from forge.subagents.review import (
    MAX_DIFF_CHARS,
    REVIEW_ITERATIONS,
    ReviewFinding,
    parse_review,
    verify_findings,
)
from forge.subagents.subagent import _run_subagent
from forge.toolkit.base import ToolContext
from forge.tools.registry import ToolRegistry, default_tools
from forge.workspace.output import build_patch, compute_changes

WORD_CAP = 400
STANDARDS_FILES = (
    "CODING_STANDARDS.md",
    "CONTRIBUTING.md",
    "docs/CODING_STANDARDS.md",
    "docs/CONTRIBUTING.md",
    "STYLE.md",
)
SMELLS = """Common code smells (judgement calls, never hard violations; a documented project rule beats this list; skip what a linter or formatter
already enforces): long functions doing several things; deep nesting; duplicated logic; a name that says nothing or lies; a boolean or
magic-number parameter whose meaning is unclear at the call site; a comment explaining what bad code does instead of fixing it; dead code
and unused parameters; broad `except` that hides errors; mutable default arguments; speculative generality (options, hooks, base classes
nobody uses); a shallow wrapper that only forwards a call; tests that mirror the implementation or assert nothing."""

STANDARDS_PROMPT = f"""You are a code reviewer checking one thing: whether a change follows the project's CODING STANDARDS. You did not write
the change. You can read files and search; you cannot edit. You are given the diff, the project's documented standards (may be empty)
and the smell list below.

Report in under {WORD_CAP} words, one finding per line:
- [blocking] path:line - the problem - the fix - evidence: `exact code copied from the file`   (a documented rule is broken: cite the rule)
- [minor] path:line - the problem - the fix   (a smell or a judgement call)
Blocking is only for a documented rule that is clearly broken. Read the current file before you report a problem in it. If the standards
are empty, report smells as [minor] only. Do not comment on what the request asked: another reviewer does that.

{SMELLS}"""

SPEC_PROMPT = f"""You are a code reviewer checking one thing: whether a change does what was ASKED. You did not write the change. You can read
files and search; you cannot edit. You are given the request (the requirement and the task) and the diff.

Report in under {WORD_CAP} words, one finding per line:
- [blocking] path:line - the problem - the fix - evidence: `exact code from the file, or the exact words of the request when something is missing`
- [minor] path:line - the problem - the fix
Look for: a requirement with no code that satisfies it (trace each one to the code that ships, not to the tests; a production path that
returns canned values is blocking); behaviour that is wrong for a concrete input; something added that was NOT asked for (scope creep); a
test weakened, skipped or deleted to get green (always blocking). Extra hardening nobody asked for is minor. Do not comment on style:
another reviewer does that."""


@dataclass
class AxisReport:
    name: str
    report: str
    findings: list[ReviewFinding]

    @property
    def blocking(self) -> int:
        return sum(1 for f in self.findings if f.blocking)

    def worst(self) -> str:
        pick = next((f for f in self.findings if f.blocking), None) or (
            self.findings[0] if self.findings else None
        )
        return pick.text[:110] if pick else "nothing found"


def find_standards(root: Path) -> str:
    """The text of the project's documented coding standards: the usual files at the repository root (empty when there are none)."""
    parts = []
    for name in STANDARDS_FILES:
        path = root / name
        try:
            if path.is_file():
                parts.append(f"--- {name} ---\n{path.read_text(encoding='utf-8', errors='replace')[:6000]}")
        except OSError:
            continue
    return "\n\n".join(parts)


def verdict_of(axes: list[AxisReport]) -> str:
    return "REVISE" if any(a.blocking for a in axes) else "SHIP"


def aggregate(axes: list[AxisReport]) -> str:
    """The reports under their own headings, never merged or re-ranked, and a closing summary with counts and the worst issue per axis."""
    lines = []
    for axis in axes:
        lines.append(f"## {axis.name}\n{re.sub(r'(?m)^VERDICT:.*$', '', axis.report).strip()}")
    summary = "; ".join(
        f"{a.name}: {a.blocking} blocking, {len(a.findings) - a.blocking} minor (worst: {a.worst()})"
        for a in axes
    )
    lines.append(f"Summary: {summary}")
    lines.append(f"VERDICT: {verdict_of(axes)}")
    return "\n\n".join(lines)


async def run_code_review(
    router: LLMRouter, context: ToolContext, requirement: str, standards_root: Path | None = None
) -> str:
    """Runs the standards and spec reviewers side by side on the workspace's changes; the spec reviewer is skipped when there is no request."""
    changes = compute_changes(context.workspace)
    if not changes:
        return "Nothing to review: no files were changed.\nVERDICT: SHIP"
    patch = build_patch(context.workspace, changes)
    if len(patch) > MAX_DIFF_CHARS:
        patch = patch[:MAX_DIFF_CHARS] + "\n[... diff truncated: read the remaining files directly ...]"
    files = ", ".join(c.path for c in changes)
    diff = f"Changed files: {files}\n\nDiff (baseline -> now):\n```diff\n{patch}\n```"
    tools = ToolRegistry([t for t in default_tools() if t.read_only])
    standards = find_standards(standards_root or context.workspace.repo_dir)
    jobs = [
        (
            "Standards",
            STANDARDS_PROMPT,
            f"Documented standards:\n{standards or '(none documented)'}\n\n{diff}",
        )
    ]
    if requirement.strip():
        jobs.append(("Spec", SPEC_PROMPT, f"The request:\n{requirement}\n\n{diff}"))

    async def one(name: str, prompt: str, task: str) -> AxisReport:
        report = await _run_subagent(router, context, tools, prompt, task, REVIEW_ITERATIONS, "reviewer")
        return AxisReport(name, report, verify_findings(context.workspace, parse_review(report), requirement))

    axes = list(await asyncio.gather(*(one(*job) for job in jobs)))
    if len(axes) == 1:
        axes[0].report += "\n(no request was found, so the spec axis was skipped)"
    return aggregate(axes)

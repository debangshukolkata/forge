"""Diagnose mode end to end (spec §6.6): integrity check -> fresh copy run -> analysis -> report
(.forge/reports/diagnose-<n>.md). The analysis step is a read-only subagent on the reviewer model; it
gets the evidence (findings, failing tests, a pasted error) and traces the cause in Forge's version of the
code and the KB. Fixes to Forge's own code are made as a change request in the session, which rebuilds
output/ and COPY_INSTRUCTIONS."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from forge.diagnose.fresh_run import FreshRun, fresh_copy_run
from forge.diagnose.integrity import IntegrityReport, check_integrity
from forge.llm.router import LLMRouter
from forge.tools.base import ToolContext
from forge.workspace.workspace import Workspace

ANALYSIS_ITERATIONS = 20
ANALYSIS_PROMPT = """You are Forge's diagnose subagent. The user copied Forge's delivered code (output/)
into their real repository and something doesn't work. You get the evidence: integrity findings (what was
copied wrongly), the result of running their repository's tests on a fresh copy, and maybe an error they
pasted. You can read Forge's version of the code (repo/) and the knowledge base; you can't edit.
Reply in under 400 words:
1. The most likely root cause, citing the evidence (file:line, test, traceback line).
2. Whether it's a copy/setup mistake (the user fixes it: say exactly how) or a defect in Forge's code (say
   what must change — Forge will fix it as a change request).
3. How the user confirms it's fixed (the exact command).
Never ask for secrets or data rows."""


@dataclass
class DiagnoseResult:
    number: int
    integrity: IntegrityReport
    fresh: FreshRun | None
    analysis: str
    report_path: str


def next_number(workspace: Workspace) -> int:
    reports = workspace.forge_dir / "reports"
    numbers = [
        int(m.group(1)) for p in reports.glob("diagnose-*.md") if (m := re.match(r"diagnose-(\d+)", p.stem))
    ]
    return max(numbers, default=0) + 1


async def run_diagnose(
    workspace: Workspace,
    *,
    db: Any = None,
    router: LLMRouter | None = None,
    context: ToolContext | None = None,
    pasted_error: str | None = None,
    fresh_run: bool = True,
    sandbox: bool = True,
) -> DiagnoseResult:
    number = next_number(workspace)
    integrity = check_integrity(workspace, db)
    fresh = await fresh_copy_run(workspace, number, sandbox) if fresh_run else None
    analysis = ""
    needs_analysis = pasted_error or (fresh and fresh.tests and not fresh.tests.passed)
    if router is not None and context is not None and needs_analysis:
        analysis = await _analyse(router, context, integrity, fresh, pasted_error)
    text = render_report(number, workspace, integrity, fresh, analysis, pasted_error)
    path = workspace.jail.check(workspace.forge_dir / "reports" / f"diagnose-{number}.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return DiagnoseResult(number, integrity, fresh, analysis, str(path))


async def _analyse(
    router: LLMRouter,
    context: ToolContext,
    integrity: IntegrityReport,
    fresh: FreshRun | None,
    pasted: str | None,
) -> str:
    from forge.agent.subagent import _run_subagent
    from forge.tools.registry import ToolRegistry, default_tools

    evidence = (
        ["Integrity findings:", *(f.render() for f in integrity.findings)]
        if integrity.findings
        else ["No integrity problems."]
    )
    if fresh is not None:
        evidence += [
            "",
            "Fresh copy test run:",
            fresh.tests.summary() if fresh.tests else fresh.output_tail[-3000:],
        ]
    if pasted:
        evidence += ["", "Error the user pasted:", pasted[-4000:]]
    tools = ToolRegistry([t for t in default_tools() if t.read_only])
    return await _run_subagent(
        router, context, tools, ANALYSIS_PROMPT, "\n".join(evidence), ANALYSIS_ITERATIONS, "reviewer"
    )


def render_report(
    number: int,
    workspace: Workspace,
    integrity: IntegrityReport,
    fresh: FreshRun | None,
    analysis: str,
    pasted: str | None,
) -> str:
    problems = integrity.problems
    lines = [
        f"# Diagnose report {number} — {workspace.info.name}",
        "",
        f"Repository: `{workspace.info.repo_path}`",
        "",
    ]
    verdict = []
    if problems:
        verdict.append(f"{len(problems)} copy/setup problem(s) found — fix them first (below).")
    if fresh is not None and fresh.tests is not None:
        verdict.append(
            f"Tests on a fresh copy of your repository: {'PASSED' if fresh.tests.passed else 'FAILED'}."
        )
    elif fresh is not None:
        verdict.append(f"The tests could not run on the fresh copy{': ' + fresh.note if fresh.note else ''}.")
    if fresh is not None and fresh.smoke:
        verdict.append(
            f"App smoke: the app builds and serves {len(fresh.smoke.get('paths', {}))} route(s)."
            if fresh.smoke.get("ok")
            else f"App smoke: the app could not be built — {str(fresh.smoke.get('error', ''))[:300]}"
        )
    lines += ["## Summary", "", *(f"- {v}" for v in verdict or ["No problems found."]), ""]
    lines += ["## Integrity check (your repository vs output/)", ""]
    if integrity.findings:
        order = {"error": 0, "warning": 1, "info": 2}
        for finding in sorted(integrity.findings, key=lambda f: order[f.severity]):
            lines += [f"- {finding.render()}", ""]
    else:
        lines += [f"All {integrity.checked_files} delivered file(s) are in place and complete.", ""]
    if fresh is not None:
        lines += [
            "## Fresh copy run",
            "",
            f"Copied to `{fresh.folder}` (sandboxed: {'yes' if fresh.sandboxed else 'no'}).",
            "",
        ]
        lines += ["```", fresh.tests.summary() if fresh.tests else fresh.output_tail[-3000:], "```", ""]
    if pasted:
        lines += ["## The error you pasted", "", "```", pasted[-3000:], "```", ""]
    if analysis:
        lines += ["## Analysis", "", analysis, ""]
    lines += ["## Next steps", ""]
    if problems:
        lines.append(
            "1. Apply the fixes above, then run diagnose again (`forge diagnose --workspace ...` "
            "or /diagnose)."
        )
    if analysis and "defect" in analysis.lower():
        lines.append(
            "- If the analysis points at Forge's code, tell Forge in the session and it will fix it as a "
            "change request (output/ and COPY_INSTRUCTIONS are rebuilt)."
        )
    if not problems and not analysis:
        lines.append(
            "Nothing to fix. If something still fails in your environment, paste the error to /diagnose."
        )
    return "\n".join(lines) + "\n"

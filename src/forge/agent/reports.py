"""The final report (reports/final.md) and the closing message of a run."""

from __future__ import annotations

from typing import Any

from forge.agent.state import OrchestratorState
from forge.db.checks import load_checks
from forge.workspace.output import OutputManifest
from forge.workspace.workspace import Workspace


def final_report(
    state: OrchestratorState, requirement: str, output: OutputManifest, workspace: Workspace, db: Any
) -> str:
    done = [t for t in state.tasks if t.status == "done"]
    blocked = [t for t in state.tasks if t.status == "blocked"]
    lines = ["# Final report", "", "## Requirement", requirement, "", "## Tasks"]
    lines += [f"- [x] {t.id} {t.title} — verified: {t.verification or 'n/a'}" for t in done]
    lines += [f"- [!] {t.id} {t.title} — blocked: {t.blocked_reason}" for t in blocked]
    lines += ["", "## Files", *[f"- {f.status}: {f.path}" for f in output.files]]
    lines += ["", *database_report(workspace, db)]
    return "\n".join(lines)


def closing_message(state: OrchestratorState, output: OutputManifest) -> str:
    done = [t for t in state.tasks if t.status == "done"]
    blocked = [t for t in state.tasks if t.status == "blocked"]
    counts = {s: sum(1 for f in output.files if f.status == s) for s in ("added", "modified", "deleted")}
    blocked_note = f", {len(blocked)} blocked" if blocked else ""
    deleted_note = f", and {counts['deleted']} deletion(s)" if counts["deleted"] else ""
    return (
        f"Done: {len(done)} task(s) completed{blocked_note}. "
        f"output/ has {counts['added']} new and {counts['modified']} modified file(s){deleted_note}. "
        "Follow output/COPY_INSTRUCTIONS.md to copy them into your repository."
    )


def database_report(workspace: Workspace, db: Any) -> list[str]:
    """Spec §9.5.2: where DB checks ran and which did not — never implying verification not done."""
    checks = load_checks(workspace)
    if db is None and not checks:
        return []
    lines = ["## Database"]
    if db is not None:
        lines += [f"- {line}" for line in db.status_line().splitlines()]
        if db.scratch is not None:
            lines.append(
                f"- Commands Forge ran used the scratch schema `{db.scratch.schema}` on the "
                f"{db.scratch.target.name} database (PGOPTIONS search_path); nothing outside it was changed."
            )
        lines += [f"- {r.id} [{r.status}] {r.title}" for r in db.requests.all()]
        if db.scratch is not None and db.scratch.registry.objects(db.scratch.key):
            lines.append("- Objects Forge created in the scratch schema remain until you run `/db cleanup`.")
    if checks:
        lines.append(
            f"- NOT run (server-run, see output/SERVER_RUN.md): {', '.join(c.tests for c in checks)}"
        )
    return lines

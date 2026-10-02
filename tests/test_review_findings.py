"""Reviewer report parsing and finding verification (no model involved)."""

from __future__ import annotations

from pathlib import Path

from forge.subagents.review import parse_review
from forge.workspace.create import create_workspace


def test_reviewer_findings_are_parsed() -> None:
    report = """Looks mostly fine.
- [blocking] backend/claims_app/api/policies/routes.py:12 — page_size isn't bounded — cap it at 100
- [minor] backend/tests/test_policies_api.py:3 — unused import — remove it
VERDICT: changes needed"""
    findings = parse_review(report)
    assert [(f.blocking, f.text.split(":")[0]) for f in findings] == [
        (True, "backend/claims_app/api/policies/routes.py"),
        (False, "backend/tests/test_policies_api.py"),
    ]


def test_blocking_findings_need_evidence_that_is_really_there(tmp_path: Path, original_repo: Path) -> None:
    # Seen live: findings about code that wasn't there (stale diffs, masked text) used up the fix rounds.
    from forge.subagents.review import MAX_BLOCKING, verify_findings

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    path = "backend/claims_app/services/claims_service.py"
    requirement = "Claims above 500000 must be rejected with 422."
    report = f"""- [blocking] {path}:33 — no upper limit — add one — evidence: `if amount <= 0:`
- [blocking] {path}:40 — uses a placeholder — fix — evidence: `api_key=[REDACTED:assignment]`
- [blocking] {path}:1 — limit missing — add it — evidence: `Claims above 500000 must be rejected`
- [blocking] {path}:12 — no retries — add backoff
- [minor] {path}:2 — naming — rename
VERDICT: changes needed"""
    findings = verify_findings(workspace, parse_review(report), requirement)
    assert [f.blocking for f in findings] == [True, False, True, False, False]
    assert "isn't in the file" in findings[1].note and "no evidence" in findings[3].note
    many = "\n".join(f"- [blocking] {path}:33 — p{i} — f — evidence: `if amount <= 0:`" for i in range(7))
    capped = verify_findings(workspace, parse_review(many), requirement)
    assert sum(f.blocking for f in capped) == MAX_BLOCKING

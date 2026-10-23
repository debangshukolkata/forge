"""The security-auditor subagent type is registered and its prompt keeps the evidence format the reviewer uses."""

from __future__ import annotations

from forge.subagents.review import parse_review
from forge.subagents.security import SECURITY_AUDITOR_PROMPT
from forge.subagents.spawn_tool import SpawnSubagent
from forge.tools.parity import BUILT_IN_TYPES


def test_the_agent_type_is_listed_and_described() -> None:
    assert "security-auditor" in BUILT_IN_TYPES
    assert "security-auditor" in SpawnSubagent.description


def test_the_prompt_asks_for_findings_the_reviewer_parser_reads() -> None:
    assert "evidence:" in SECURITY_AUDITOR_PROMPT and "VERDICT:" in SECURITY_AUDITOR_PROMPT
    sample = '- [blocking] app.py:3 — SQL from an f-string — id=1 OR 1=1 — use parameters — evidence: `f"select {x}"`'
    assert parse_review(sample)[0].blocking

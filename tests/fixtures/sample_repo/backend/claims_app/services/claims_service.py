"""Business rules for claims."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from langchain_core.language_models import BaseChatModel

from claims_app.db import session_scope
from claims_app.errors import BusinessRuleError, NotFoundError
from claims_app.graphs.triage_graph import build_triage_graph
from claims_app.repositories import claims_repository, policies_repository


def list_claims(page: int, page_size: int, status: str | None = None) -> dict[str, Any]:
    offset = (page - 1) * page_size
    with session_scope() as session:
        items = claims_repository.list_claims(session, status=status, limit=page_size, offset=offset)
        total = claims_repository.count_claims(session, status=status)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def get_claim(claim_id: int) -> dict[str, Any]:
    with session_scope() as session:
        claim = claims_repository.get_claim(session, claim_id)
    if claim is None:
        raise NotFoundError(f"Claim {claim_id} not found")
    return claim


def create_claim(policy_id: int, amount: float, description: str) -> dict[str, Any]:
    if amount <= 0:
        raise BusinessRuleError("Claim amount must be greater than zero")
    with session_scope() as session:
        policy = policies_repository.get_policy(session, policy_id)
        if policy is None:
            raise NotFoundError(f"Policy {policy_id} not found")
        if policy.status != "active":
            raise BusinessRuleError(f"Policy {policy.policy_number} is not active")
        submitted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        next_sequence = claims_repository.count_claims(session) + 1
        claim_id = claims_repository.insert_claim(
            session,
            {
                "claim_number": f"CLM-{submitted_at.year}-{next_sequence:05d}",
                "policy_id": policy_id,
                "status": "submitted",
                "category": None,
                "amount": amount,
                "description": description,
                "submitted_at": submitted_at,
            },
        )
        return claims_repository.get_claim(session, claim_id) or {}


def triage_claim(claim_id: int, llm: BaseChatModel) -> dict[str, Any]:
    claim = get_claim(claim_id)
    result = build_triage_graph(llm).invoke({"claim": claim})
    with session_scope() as session:
        claims_repository.update_claim_triage(session, claim_id, result["category"], status="triaged")
    return {
        "claim_id": claim_id,
        "category": result["category"],
        "priority": result["priority"],
        "summary": result["summary"],
    }

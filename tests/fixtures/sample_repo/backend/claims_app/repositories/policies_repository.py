"""ORM access to policies."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from claims_app.models import Policy


def get_policy(session: Session, policy_id: int) -> Policy | None:
    return session.get(Policy, policy_id)


def list_active_policies(session: Session) -> list[Policy]:
    statement = select(Policy).where(Policy.status == "active").order_by(Policy.policy_number)
    return list(session.scalars(statement))

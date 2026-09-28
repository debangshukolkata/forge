"""Raw SQL access to the claims table."""

from __future__ import annotations

from typing import Any

from sqlalchemy import DateTime, bindparam, text
from sqlalchemy.orm import Session

_CLAIM_COLUMNS = "id, claim_number, policy_id, status, category, amount, description, submitted_at"


def _claim_query(sql: str):  # type: ignore[no-untyped-def]
    # Declaring the column type makes SQLite return datetimes, as Postgres does.
    return text(sql).columns(submitted_at=DateTime)


def list_claims(session: Session, status: str | None, limit: int, offset: int) -> list[dict[str, Any]]:
    sql = f"SELECT {_CLAIM_COLUMNS} FROM claims"
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if status:
        sql += " WHERE status = :status"
        params["status"] = status
    sql += " ORDER BY submitted_at DESC, id DESC LIMIT :limit OFFSET :offset"
    rows = session.execute(_claim_query(sql), params).mappings().all()
    return [dict(row) for row in rows]


def count_claims(session: Session, status: str | None = None) -> int:
    sql = "SELECT COUNT(*) FROM claims"
    params: dict[str, Any] = {}
    if status:
        sql += " WHERE status = :status"
        params["status"] = status
    return int(session.execute(text(sql), params).scalar_one())


def get_claim(session: Session, claim_id: int) -> dict[str, Any] | None:
    sql = f"SELECT {_CLAIM_COLUMNS} FROM claims WHERE id = :claim_id"
    row = session.execute(_claim_query(sql), {"claim_id": claim_id}).mappings().first()
    return dict(row) if row else None


def insert_claim(session: Session, claim: dict[str, Any]) -> int:
    statement = text(
        "INSERT INTO claims (claim_number, policy_id, status, category, amount, description, submitted_at) "
        "VALUES (:claim_number, :policy_id, :status, :category, :amount, :description, :submitted_at) "
        "RETURNING id"
    ).bindparams(bindparam("submitted_at", type_=DateTime))
    result = session.execute(statement, claim)
    return int(result.scalar_one())


def update_claim_triage(session: Session, claim_id: int, category: str, status: str) -> None:
    session.execute(
        text("UPDATE claims SET category = :category, status = :status WHERE id = :claim_id"),
        {"category": category, "status": status, "claim_id": claim_id},
    )

from __future__ import annotations

from flask_smorest import Blueprint

from claims_app.api.policies.schemas import PolicySchema
from claims_app.auth import jwt_required
from claims_app.db import session_scope
from claims_app.errors import NotFoundError
from claims_app.models import Policy
from claims_app.repositories import policies_repository

blp = Blueprint("policies", __name__, url_prefix="/api/policies", description="Insurance policies")


@blp.route("/active")
@blp.response(200, PolicySchema(many=True))
@jwt_required
def list_active_policies() -> list[Policy]:
    """List active policies"""
    with session_scope() as session:
        return policies_repository.list_active_policies(session)


@blp.route("/<int:policy_id>")
@blp.response(200, PolicySchema)
@jwt_required
def get_policy(policy_id: int) -> Policy:
    """Get one policy"""
    with session_scope() as session:
        policy = policies_repository.get_policy(session, policy_id)
    if policy is None:
        raise NotFoundError(f"Policy {policy_id} not found")
    return policy

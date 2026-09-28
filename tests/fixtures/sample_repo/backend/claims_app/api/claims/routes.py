from __future__ import annotations

from typing import Any

from flask.views import MethodView
from flask_smorest import Blueprint

from claims_app.api.claims.schemas import (
    ClaimCreateSchema,
    ClaimPageSchema,
    ClaimQuerySchema,
    ClaimSchema,
    ClaimTriageSchema,
)
from claims_app.auth import jwt_required
from claims_app.llm import get_chat_model
from claims_app.services import claims_service

blp = Blueprint("claims", __name__, url_prefix="/api/claims", description="Insurance claims")


@blp.route("/")
class ClaimList(MethodView):
    @blp.arguments(ClaimQuerySchema, location="query")
    @blp.response(200, ClaimPageSchema)
    @jwt_required
    def get(self, query: dict[str, Any]) -> dict[str, Any]:
        """List claims, newest first"""
        return claims_service.list_claims(query["page"], query["page_size"], query["status"])

    @blp.arguments(ClaimCreateSchema)
    @blp.response(201, ClaimSchema)
    @jwt_required
    def post(self, new_claim: dict[str, Any]) -> dict[str, Any]:
        """Submit a claim against an active policy"""
        return claims_service.create_claim(
            new_claim["policy_id"], new_claim["amount"], new_claim["description"]
        )


@blp.route("/<int:claim_id>")
class ClaimDetail(MethodView):
    @blp.response(200, ClaimSchema)
    @jwt_required
    def get(self, claim_id: int) -> dict[str, Any]:
        """Get one claim"""
        return claims_service.get_claim(claim_id)


@blp.route("/<int:claim_id>/triage")
class ClaimTriage(MethodView):
    @blp.response(200, ClaimTriageSchema)
    @jwt_required
    def post(self, claim_id: int) -> dict[str, Any]:
        """Classify and prioritise a claim with the triage graph"""
        return claims_service.triage_claim(claim_id, get_chat_model())

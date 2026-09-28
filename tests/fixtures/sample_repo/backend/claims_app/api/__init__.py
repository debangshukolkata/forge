"""Blueprint registration."""

from __future__ import annotations

from flask_smorest import Api

from claims_app.api.claims.routes import blp as claims_blp
from claims_app.api.policies.routes import blp as policies_blp


def register_blueprints(api: Api) -> None:
    api.register_blueprint(claims_blp)
    api.register_blueprint(policies_blp)

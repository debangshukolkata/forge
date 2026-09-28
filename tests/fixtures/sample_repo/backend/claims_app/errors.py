"""Domain errors and their HTTP mapping."""

from __future__ import annotations

from flask import Flask, jsonify
from werkzeug.wrappers import Response


class ClaimsAppError(Exception):
    status_code = 400
    status_text = "Bad Request"


class NotFoundError(ClaimsAppError):
    status_code = 404
    status_text = "Not Found"


class BusinessRuleError(ClaimsAppError):
    status_code = 422
    status_text = "Unprocessable Entity"


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ClaimsAppError)
    def handle_claims_app_error(error: ClaimsAppError) -> tuple[Response, int]:
        # Same shape as flask-smorest's own error responses, so clients see one format.
        body = {"code": error.status_code, "status": error.status_text, "message": str(error)}
        return jsonify(body), error.status_code

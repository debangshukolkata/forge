---
id: rcp-flask-extension
type: recipe
title: Flask app factory, blueprints and extensions
summary: "Application factory, blueprints, the init_app extension pattern, config classes, error handlers and test-client tests."
moods: [robust, clean]
products: [web app, api, small backend]
tags: [flask, blueprint, application-factory, extension, testing]
density: any
dependencies: [flask]
licence: original
source: authored for DebCraft (python recipes, 2026-10-27)
tested: not executed (flask is not installed in the build venv); follows the documented Flask 3 API
---

## Flask app factory, blueprints and extensions

Rules:
- Never create a global `app = Flask(__name__)` that other modules import. Build the app inside `create_app(config)` so
  tests get a fresh one with their own config and there are no circular imports.
- Group routes in blueprints, one per feature, each in its own module; register them inside the factory.
- Extensions are created unbound at import time (`db = SQLAlchemy()`), then bound with `init_app(app)` inside the factory.
  Your own extension follows the same shape: `__init__(app=None)`, `init_app(app)`, state stored in `app.extensions[name]`.
- Config: a base class and one subclass per environment, loaded with `app.config.from_object`; secrets from environment
  variables via `from_prefixed_env()`. `SECRET_KEY` is required in production and `DEBUG` is never on there.
- Use `current_app` and `g` inside requests, not imported globals. Register `errorhandler` for 404, 422 and 500 and
  return JSON for API blueprints, so clients never get an HTML stack page.
- Validate input at the edge (pydantic or marshmallow); return the right status (400 bad input, 404, 409 conflict).

Worked example (a small extension plus a blueprint):

```python
# app/extensions.py
from flask import Flask, current_app


class RateNote:
    """Tiny extension: keeps a per-app counter and exposes it as a helper."""

    def __init__(self, app: Flask | None = None) -> None:
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        app.config.setdefault("RATE_NOTE_LIMIT", 100)
        app.extensions["rate_note"] = {"count": 0}  # per app, not module global

    def hit(self) -> int:
        state = current_app.extensions["rate_note"]
        state["count"] += 1
        if state["count"] > current_app.config["RATE_NOTE_LIMIT"]:
            raise RuntimeError("limit reached")
        return state["count"]


rate_note = RateNote()

# app/notes.py
from flask import Blueprint, jsonify, request, abort
from .extensions import rate_note

bp = Blueprint("notes", __name__, url_prefix="/notes")
_NOTES: dict[int, str] = {}


@bp.post("")
def create():
    body = request.get_json(silent=True) or {}
    text = str(body.get("text", "")).strip()
    if not text:
        abort(400, description="text is required")
    note_id = rate_note.hit()
    _NOTES[note_id] = text
    return jsonify(id=note_id, text=text), 201


@bp.get("/<int:note_id>")
def read(note_id: int):
    if note_id not in _NOTES:
        abort(404)
    return jsonify(id=note_id, text=_NOTES[note_id])


# app/__init__.py
from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from . import notes
from .extensions import rate_note


def create_app(overrides: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(SECRET_KEY="dev-only-change-me")
    app.config.from_prefixed_env()  # FLASK_SECRET_KEY etc.
    app.config.update(overrides or {})
    rate_note.init_app(app)
    app.register_blueprint(notes.bp)

    @app.errorhandler(HTTPException)
    def as_json(error: HTTPException):
        return jsonify(error=error.name, detail=error.description), error.code

    return app


# tests/test_notes.py
import pytest

from app import create_app


@pytest.fixture
def client():
    return create_app({"TESTING": True, "RATE_NOTE_LIMIT": 2}).test_client()


def test_create_then_read(client):
    created = client.post("/notes", json={"text": "hi"})
    assert created.status_code == 201
    assert client.get(f"/notes/{created.json['id']}").json["text"] == "hi"


def test_missing_text_is_a_json_400(client):
    response = client.post("/notes", json={})
    assert response.status_code == 400 and response.json["error"] == "Bad Request"
```

Gotchas:
- `app.run(debug=True)` exposes an interactive debugger; use a real server (gunicorn, waitress) in production.
- Code that needs the app (config, database) outside a request needs `with app.app_context():`.
- Module-level dicts like `_NOTES` above are for the demo only; per-process state breaks with several workers.
- Importing the blueprint module inside `create_app` avoids circular imports when models import `db`.
- `TESTING=True` makes errors propagate instead of turning into 500 pages, which is what you want in tests.

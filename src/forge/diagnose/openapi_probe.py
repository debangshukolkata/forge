"""The OpenAPI probe `forge diagnose` runs on a fresh copy of the user's repository (spec §6.6): a small
script, run with the app's own interpreter, that builds the Flask app and prints its OpenAPI paths."""

from __future__ import annotations

MARKER = "FORGE_CHECK_RESULT:"
CHECK_TIMEOUT_S = 180

OPENAPI_SCRIPT = r'''
import json, sys
sys.path.insert(0, ".")
MARKER = "FORGE_CHECK_RESULT:"

def find_spec(app):
    """flask-smorest keeps the Api (with an apispec) in app.extensions; its layout changed across versions."""
    seen = set()
    def walk(value, depth=0):
        if id(value) in seen or depth > 4:
            return None
        seen.add(id(value))
        spec = getattr(value, "spec", None)
        if spec is not None and hasattr(spec, "to_dict"):
            return spec.to_dict()
        if isinstance(value, dict):
            for item in value.values():
                found = walk(item, depth + 1)
                if found:
                    return found
        return None
    found = walk(dict(app.extensions))
    if found:
        return found
    client = app.test_client()
    prefix = (app.config.get("OPENAPI_URL_PREFIX") or "").rstrip("/")
    name = app.config.get("OPENAPI_JSON_PATH") or "openapi.json"
    for route in (f"{prefix}/{name}", "/openapi.json", "/api/openapi.json", "/swagger.json", "/apispec.json"):
        response = client.get(route)
        if response.status_code == 200 and response.is_json:
            return response.get_json()
    return None

try:
__SETUP__
    spec = find_spec(app)
    if spec is None:
        print(MARKER + json.dumps({"ok": False, "error": "no OpenAPI spec found (no flask-smorest Api, no JSON route)"}))
    else:
        paths = {path: sorted(k.upper() for k in item if k in ("get","post","put","patch","delete")) for path, item in spec.get("paths", {}).items()}
        schemas = sorted((spec.get("components") or {}).get("schemas", {}) or spec.get("definitions", {}))
        print(MARKER + json.dumps({"ok": True, "paths": paths, "schemas": schemas}))
except Exception as error:
    print(MARKER + json.dumps({"ok": False, "error": f"{type(error).__name__}: {error}"}))
'''

DEFAULT_OPENAPI_SETUP = "from {package} import create_app\napp = create_app()"

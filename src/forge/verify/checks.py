"""App-level checks (spec §13.1 rungs 7-8), run as small scripts in the app's own venv from the app folder:

- OpenAPI: build the app (by default `create_app()`; the agent can pass setup code that uses the repo's test
  config), take the spec from flask-smorest/apispec or a served JSON route, and list its paths and schemas.
- LangGraph: import a graph (or a function that builds one), compile it, list nodes and edges.

Scripts print one JSON line after a marker, so app logging can't confuse the result.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from forge.toolkit.base import ToolContext
from forge.toolkit.powershell import ps_quote
from forge.toolkit.shell import execute

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

LANGGRAPH_SCRIPT = r"""
import importlib, inspect, json, sys
sys.path.insert(0, ".")
MARKER = "FORGE_CHECK_RESULT:"
try:
__SETUP__
    target = graph
    if callable(target) and not hasattr(target, "compile") and not hasattr(target, "get_graph"):
        parameters = [p for p in inspect.signature(target).parameters.values() if p.default is p.empty]
        if parameters:
            raise TypeError(f"the builder needs arguments {[p.name for p in parameters]}; pass setup code that calls it (e.g. with a fake LLM) and assigns graph")
        target = target()
    compiled = target.compile() if hasattr(target, "compile") and not hasattr(target, "invoke") else target
    drawn = compiled.get_graph()
    nodes = sorted(str(n) for n in drawn.nodes)
    edges = sorted(f"{e.source} -> {e.target}" + (" (conditional)" if getattr(e, "conditional", False) else "") for e in drawn.edges)
    print(MARKER + json.dumps({"ok": True, "nodes": nodes, "edges": edges}))
except Exception as error:
    print(MARKER + json.dumps({"ok": False, "error": f"{type(error).__name__}: {error}"}))
"""


@dataclass
class CheckOutcome:
    ok: bool
    text: str
    data: dict[str, object] = field(default_factory=dict)


async def openapi_check(context: ToolContext, setup: str | None, expect_paths: list[str]) -> CheckOutcome:
    packages = (
        context.workspace.info.python_env.top_packages if context.workspace.info.python_env else []
    ) or ["app"]
    if setup:
        code = setup
    elif context.workspace.mode_b:  # Mode B: the harness app registers the new blueprints (spec §6A.4)
        code = "from run_app import create_app\napp = create_app()"
    else:
        code = DEFAULT_OPENAPI_SETUP.format(package=packages[0])
    indented = "\n".join("    " + line for line in code.splitlines())
    data = await _run_script(context, "openapi_check.py", OPENAPI_SCRIPT.replace("__SETUP__", indented))
    if not data.get("ok"):
        return CheckOutcome(False, f"OpenAPI check could not build the spec: {data.get('error')}", data)
    paths: dict[str, list[str]] = data.get("paths", {})  # type: ignore[assignment]
    missing = [p for p in expect_paths if _normalise(p) not in {_normalise(k) for k in paths}]
    lines = [f"OpenAPI: {len(paths)} path(s), {len(data.get('schemas', []))} schema(s)"]  # type: ignore[arg-type]
    lines += [f"- {path} {' '.join(methods)}" for path, methods in sorted(paths.items())[:40]]
    if missing:
        lines.append(f"MISSING expected paths: {', '.join(missing)}")
    return CheckOutcome(not missing, "\n".join(lines), data)


async def langgraph_check(
    context: ToolContext, target: str | None, setup: str | None, expect_nodes: list[str]
) -> CheckOutcome:
    if setup is None:
        if not target or not re.fullmatch(r"[\w.]+:\w+", target):
            return CheckOutcome(False, "pass target 'package.module:name', or setup code that assigns graph")
        module, attribute = target.split(":")
        setup = f"from {module} import {attribute} as graph"
    indented = "\n".join("    " + line for line in setup.splitlines())
    data = await _run_script(context, "langgraph_check.py", LANGGRAPH_SCRIPT.replace("__SETUP__", indented))
    if not data.get("ok"):
        return CheckOutcome(False, f"LangGraph check failed: {data.get('error')}", data)
    nodes: list[str] = data.get("nodes", [])  # type: ignore[assignment]
    edges: list[str] = data.get("edges", [])  # type: ignore[assignment]
    missing = [n for n in expect_nodes if n not in nodes]
    lines = [f"Graph compiles: {len(nodes)} node(s), {len(edges)} edge(s)", "nodes: " + ", ".join(nodes)]
    lines += [f"- {edge}" for edge in edges[:40]]
    if missing:
        lines.append(f"MISSING expected nodes: {', '.join(missing)}")
    return CheckOutcome(not missing, "\n".join(lines), data)


async def _run_script(context: ToolContext, name: str, source: str) -> dict[str, object]:
    assert context.shell is not None
    folder = context.workspace.jail.check(context.shell.scratch_dir)
    folder.mkdir(parents=True, exist_ok=True)
    script = context.workspace.jail.check(folder / name)
    script.write_text(source, encoding="utf-8")
    python = context.shell.python or "python"
    result = await execute(
        context,
        f"& {ps_quote(python)} {ps_quote(str(script))}",
        CHECK_TIMEOUT_S,
        context.workspace.info.app_subfolder or None,
    )
    for line in reversed(result.content.splitlines()):
        if line.startswith(MARKER):
            parsed: dict[str, object] = json.loads(line[len(MARKER) :])
            return parsed
    return {"ok": False, "error": "the check script produced no result:\n" + result.content[-1500:]}


def _normalise(path: str) -> str:
    """/api/policies/{policy_id} and /api/policies/<int:policy_id> are the same route."""
    return re.sub(r"\{[^}]+\}|<[^>]+>", "{}", path.rstrip("/") or "/")

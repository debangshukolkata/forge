"""M10B live acceptance: with a scripted host interview (profile) and the fixture's structure export, the live
agent builds a standalone feature whose tests pass in the harness; copying output/ into a clean copy of the
fixture and following INTEGRATION_GUIDE makes the feature tests and contract tests pass there.
Run with: pytest -m live tests/test_live_modeb.py"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from forge.engine.headless import EXIT_OK, run_headless
from forge.modeb import forge_structure_export as exporter
from forge.modeb.profile import ProfileStore
from forge.modeb.workspace import create_standalone_workspace
from forge.session import build_session
from forge.tools.base import ToolContext
from forge.tools.shell import ShellSession
from forge.verify.ladder import VerifyLadder
from forge.workspace.workspace import Workspace
from tests.conftest import FIXTURE_BACKEND, REPO_ROOT

pytestmark = pytest.mark.live
FIXTURE_PYTHON = FIXTURE_BACKEND / "venv" / "Scripts" / "python.exe"
FORGE_DOCS = {
    "INTEGRATION_GUIDE.md",
    "INTERFACE_CONTRACT.md",
    "ASSUMPTIONS.md",
    "REVISION_NOTES.md",
    "MANIFEST.json",
    "DB_CHANGES.sql",
}

PROFILE = """# Host profile: claims-host

## 1. Stack & versions
Python 3.13. Flask 3.1, flask-smorest 0.47 (Blueprint, MethodView or function routes), marshmallow 4,
SQLAlchemy 2.1 (sessions; queries in repositories use raw SQL through `session.execute(text(...))`),
PyJWT, LangGraph. Exact pins: profile_read packages.

## 2. Structure
Top-level package `claims_app` (host root = the app folder). Blueprints: `claims_app/api/<resource>/routes.py`
with `blp = Blueprint(...)` and schemas in `claims_app/api/<resource>/schemas.py`. Services:
`claims_app/services/<name>_service.py`. Repositories (raw SQL): `claims_app/repositories/<name>_repository.py`.
Models: `claims_app/models/`. Tests: `tests/test_<resource>_api.py`.

## 3. App wiring
App factory `claims_app.create_app(config_object)`. Blueprints are registered in
`claims_app/api/__init__.py`, function `register_blueprints(api)`, as `api.register_blueprint(<name>_blp)` after
`from claims_app.api.<resource>.routes import blp as <name>_blp`. DB: `from claims_app.db import session_scope`
— a context manager yielding a SQLAlchemy `Session` (commits on success). Config from env (never literals).

## 4. Conventions
Function routes: `@blp.route(path)`, `@blp.response(200, Schema)`, then `@jwt_required` (from
`claims_app.auth`). Errors: raise `claims_app.errors.NotFoundError(message)` -> 404 JSON via the host's error
handlers. Type hints everywhere, `from __future__ import annotations`, docstring = OpenAPI summary.

## 5. Data
Tables: `policies(id, policy_number, holder_name, status, start_date, end_date)`,
`claims(id, claim_number, policy_id -> policies.id, status, category, amount, description, submitted_at)`.

## 6. LLM layer
Not needed for this requirement.

## 7. Testing
pytest. `tests/conftest.py` provides fixtures `client` (Flask test client on a fresh SQLite DB built from the
models) and `auth_headers` (a valid Bearer token). Seed data: policy 1 (active) has 3 claims; policy 2 (lapsed)
has 0 claims; no policy 999. Tests call e.g. `client.get("/api/policies/1", headers=auth_headers)`.
"""

EXEMPLAR = '''from __future__ import annotations

from flask_smorest import Blueprint

from claims_app.api.policies.schemas import PolicySchema
from claims_app.auth import jwt_required
from claims_app.db import session_scope
from claims_app.errors import NotFoundError
from claims_app.repositories import policies_repository

blp = Blueprint("policies", __name__, url_prefix="/api/policies", description="Insurance policies")


@blp.route("/<int:policy_id>")
@blp.response(200, PolicySchema)
@jwt_required
def get_policy(policy_id: int):
    """Get one policy"""
    with session_scope() as session:
        policy = policies_repository.get_policy(session, policy_id)
    if policy is None:
        raise NotFoundError(f"Policy {policy_id} not found")
    return policy
'''

REQUIREMENT = (
    "Add a new endpoint GET /api/policy-stats/<policy_id>/claims-count that returns "
    '{"policy_id": <id>, "claim_count": <number of claims for that policy>} for one policy, 404 if the policy '
    "doesn't exist, protected by the host's jwt_required. Put it in its own blueprint module "
    "claims_app/api/policy_stats/routes.py (with a schema), a service and a raw-SQL repository, following the "
    "host conventions. Deliver feature tests (tests/test_policy_stats_api.py, using the host's client and "
    "auth_headers fixtures) and contract tests (tests/test_contract_policy_stats.py) that pin the host "
    "assumptions the code relies on. Make everything pass in the harness."
)


@pytest.fixture
def standalone(tmp_path: Path, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch) -> Workspace:
    if not FIXTURE_PYTHON.exists():
        pytest.skip("run scripts/dev/setup_fixture_venv.ps1 first")
    monkeypatch.setenv("FORGE_ENV_FILE", str(REPO_ROOT / ".env"))
    store = ProfileStore(isolated_forge_home)
    profile = store.create("claims-host", sensitive_terms=["Contoso Insurance"])
    out = tmp_path / "structure_export"
    subprocess.run([sys.executable, exporter.__file__, str(FIXTURE_BACKEND), "--out", str(out)], check=True)
    profile.import_structure(json.loads((tmp_path / "structure_export.json").read_text(encoding="utf-8")))
    profile.write("PROFILE", PROFILE, "scripted interview")
    profile.add_exemplar(
        EXEMPLAR, "function-route blueprint with schema, jwt_required, session_scope, NotFoundError"
    )
    workspace = create_standalone_workspace(tmp_path / "wsb", profile)
    # The workspace venv would get the host's pinned versions by `pip install` (with approval); the fixture's
    # venv has exactly those versions, so the test uses it instead of downloading them again.
    assert workspace.info.python_env is not None
    workspace.info.python_env = workspace.info.python_env.model_copy(update={"python": str(FIXTURE_PYTHON)})
    workspace.save_info()
    return Workspace.open(workspace.root)


def keep_evidence(workspace: Workspace) -> Path:
    """pytest keeps only its last few temp folders: save .forge (state, events, logs) and _harness."""
    import time

    folder = REPO_ROOT / "test-artifacts" / f"modeb-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copytree(
        workspace.forge_dir, folder / "forge", ignore=shutil.ignore_patterns("checkpoints", "baseline")
    )
    shutil.copytree(workspace.harness_dir, folder / "_harness")
    shutil.copytree(workspace.repo_dir, folder / "project")
    return folder


def _register_blueprint(host: Path, guide: str, output: Path) -> None:
    """Follows INTEGRATION_GUIDE's registration step (the import + api.register_blueprint line)."""
    init = host / "claims_app" / "api" / "__init__.py"
    text = init.read_text(encoding="utf-8")
    # The guide may show the same step twice (example + checklist): apply each once.
    imports = list(dict.fromkeys(re.findall(r"from claims_app\.api\.[\w.]+ import blp as \w+", guide)))
    registrations = list(dict.fromkeys(re.findall(r"api\.register_blueprint\((\w+)\)", guide)))
    if not imports:  # fall back to the delivered blueprint module
        module = next(p for p in output.rglob("routes.py") if "Blueprint(" in p.read_text(encoding="utf-8"))
        dotted = module.relative_to(output).with_suffix("").as_posix().replace("/", ".")
        imports, registrations = [f"from {dotted} import blp as forge_new_blp"], ["forge_new_blp"]
    text = text.replace(
        "\n\ndef register_blueprints", "\n" + "\n".join(imports) + "\n\n\ndef register_blueprints", 1
    )
    text = (
        text.rstrip("\n")
        + "\n"
        + "".join(
            f"    api.register_blueprint({r})\n"
            for r in registrations
            if f"register_blueprint({r})" not in text
        )
    )
    init.write_text(text, encoding="utf-8")


async def test_standalone_feature_passes_in_harness_and_in_the_host(
    standalone: Workspace, tmp_path: Path
) -> None:
    host = build_session(workspace=standalone, orchestrated=True)
    result = await run_headless(host, REQUIREMENT, auto_approve=True)
    if result.exit_code != EXIT_OK:
        pytest.fail(f"{result}\nevidence in {keep_evidence(standalone)}")

    # 1. In the harness.
    context = ToolContext(workspace=standalone, shell=ShellSession(standalone, sandbox="off"))
    step, _ = await VerifyLadder(context).run_tests("")
    assert step.ok, step.summary
    out = standalone.output_dir
    assert (out / "INTEGRATION_GUIDE.md").exists() and (out / "INTERFACE_CONTRACT.md").exists()
    assert not any(p.name == "harness_conftest.py" for p in out.rglob("*"))
    delivered_tests = sorted(p.relative_to(out).as_posix() for p in out.rglob("test_*.py"))
    assert any("contract" in t for t in delivered_tests), delivered_tests

    # 2. In a clean copy of the host, following the guide.
    first = _run_in_host(out, tmp_path / "host1", delivered_tests)
    print(f"First attempt in the host: {'PASSED' if first.returncode == 0 else 'FAILED'}")
    if first.returncode == 0:
        return

    # 3. Acceptance 3 (spec M10B): the user pastes the host's failure; Forge classifies it, fixes the code and
    #    issues a revision whose notes list only the changed files; the revision passes in a fresh host copy.
    before = {p.relative_to(out).as_posix(): p.read_bytes() for p in out.rglob("*") if p.is_file()}
    pasted = (
        "I copied output/ into the host and followed INTEGRATION_GUIDE. These delivered tests fail there:\n\n"
        + _failure_excerpt(first.stdout)
    )
    host = build_session(workspace=standalone, orchestrated=True)
    revision = await run_headless(host, pasted, auto_approve=True)
    second = _run_in_host(
        out, tmp_path / "host2", sorted(p.relative_to(out).as_posix() for p in out.rglob("test_*.py"))
    )
    if revision.exit_code != EXIT_OK or second.returncode != 0:
        evidence = keep_evidence(standalone)
        shutil.copytree(out, evidence / "output")
        (evidence / "host_pytest_1.txt").write_text(first.stdout + first.stderr, encoding="utf-8")
        (evidence / "host_pytest_2.txt").write_text(second.stdout + second.stderr, encoding="utf-8")
        pytest.fail(f"revision failed ({revision}); evidence in {evidence}: " + second.stdout[-3000:])
    notes = (out / "REVISION_NOTES.md").read_text(encoding="utf-8")
    changed = [
        path
        for path in {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()}
        if path not in FORGE_DOCS
        and not path.startswith("_merge/")
        and before.get(path) != (out / path).read_bytes()
    ]
    assert notes.startswith("# Revision 2"), notes[:300]
    for path in changed:
        assert f"`{path}`" in notes, (path, notes)
    unchanged = [p for p in before if p not in FORGE_DOCS and p not in changed and (out / p).exists()]
    assert not [p for p in unchanged if f"`{p}`" in notes], notes


def _run_in_host(out: Path, host_copy: Path, delivered_tests: list[str]) -> subprocess.CompletedProcess[str]:
    shutil.copytree(
        FIXTURE_BACKEND, host_copy, ignore=shutil.ignore_patterns("venv", "__pycache__", ".pytest_cache")
    )
    for file in out.rglob("*"):
        relative = file.relative_to(out)
        if file.is_file() and relative.as_posix() not in FORGE_DOCS and relative.parts[0] != "_merge":
            target = host_copy / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(file, target)
    guide = (out / "INTEGRATION_GUIDE.md").read_text(encoding="utf-8")
    _register_blueprint(host_copy, guide, out)
    return subprocess.run(
        [str(FIXTURE_PYTHON), "-m", "pytest", "-q", "-p", "no:cacheprovider", *delivered_tests],
        cwd=host_copy,
        capture_output=True,
        text=True,
        timeout=300,
        env={**__import__("os").environ, "PYTHONPATH": str(host_copy)},
    )


def _failure_excerpt(output: str) -> str:
    """What a user would paste: the short summary and the error lines, with local paths removed."""
    keep = [line for line in output.splitlines() if line.startswith(("FAILED", "ERROR", "E   ", "E       "))]
    text = "\n".join(keep[:60])
    return re.sub(r"[A-Za-z]:\\[^\s'\"]+", "<path>", text)

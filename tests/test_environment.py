"""D-186: the saved environment, the model plan and the setup screen's endpoints. No model calls (the Azure
connectivity check itself is the same code `forge doctor` runs and is covered by the live tests)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from forge.config import ROLES, ForgeConfig
from forge.environment import checks, store
from forge.environment.plan import apply_saved_plan, propose_plan, validate_plan
from forge.safety.server_security import ServerSecurity
from forge.web.manager import WebSessionManager
from forge.web.server import create_app
from tests.helpers import default_config, mocked_router
from tests.test_web import direct_session

BOTH = {"azure": {"status": "ok", "models": {"gpt51": True, "gpt41": True}}}


def by_role(plan: dict[str, object]) -> dict[str, dict[str, str]]:
    return {entry["role"]: entry for entry in plan["roles"]}  # type: ignore[index, union-attr]


def test_store_round_trip_and_damaged_file(tmp_path: Path) -> None:
    assert store.load(tmp_path) == {"results": {}, "plan": {}, "confirmed_at": None}
    store.save_result(tmp_path, "azure", {"status": "ok"})
    store.save_plan(tmp_path, {"coder": "gpt51"})
    data = store.load(tmp_path)
    assert data["results"]["azure"]["status"] == "ok" and data["results"]["azure"]["checked_at"]
    assert data["plan"] == {"coder": "gpt51"} and data["confirmed_at"]
    (tmp_path / store.FILE).write_text("{not json", encoding="utf-8")
    assert store.load(tmp_path)["plan"] == {}


def test_default_plan_when_everything_answers() -> None:
    config = default_config()
    plan = by_role(propose_plan(config, BOTH, {}))
    assert plan["coder"]["model"] == config.llm.roles.coder
    assert plan["reviewer"]["model"] == config.llm.roles.reviewer
    assert all(entry["reason"] == "Default for this role" for entry in plan.values())


def test_a_model_that_does_not_answer_is_replaced() -> None:
    config = default_config()
    results = {"azure": {"status": "warn", "models": {"gpt51": True, "gpt41": False}}}
    plan = by_role(propose_plan(config, results, {}))
    assert plan["reviewer"]["model"] == "gpt51" and "not answering" in plan["reviewer"]["reason"]
    assert plan["coder"]["model"] == "gpt51"


def test_no_model_answering_leaves_roles_empty() -> None:
    results = {"azure": {"status": "fail", "models": {"gpt51": False, "gpt41": False}}}
    plan = by_role(propose_plan(default_config(), results, {}))
    assert all(entry["model"] is None for entry in plan.values())


def test_saved_choice_is_kept_and_unknown_keys_ignored() -> None:
    plan = by_role(propose_plan(default_config(), BOTH, {"reviewer": "gpt51", "judge": "gone"}))
    assert plan["reviewer"]["model"] == "gpt51" and plan["reviewer"]["reason"] == "Your earlier choice"
    assert plan["judge"]["reason"] == "Default for this role"


def test_database_note_only_when_it_is_not_ok() -> None:
    config = default_config()
    assert propose_plan(config, {"postgres": {"status": "ok"}}, {})["notes"] == []
    assert propose_plan(config, {"postgres": {"status": "warn"}}, {})["notes"]


def test_validate_plan_rejects_what_cannot_be_applied() -> None:
    config: ForgeConfig = default_config()
    everything = {role: "gpt51" for role in ROLES}
    assert validate_plan(config, everything) == everything
    with pytest.raises(ValueError, match="Unknown model"):
        validate_plan(config, {**everything, "coder": "nope"})
    with pytest.raises(ValueError, match="Unknown role"):
        validate_plan(config, {**everything, "poet": "gpt51"})
    with pytest.raises(ValueError, match="No model chosen"):
        validate_plan(config, {"coder": "gpt51"})


def test_saved_plan_is_applied_to_the_router(tmp_path: Path) -> None:
    router = mocked_router(lambda request: (_ for _ in ()).throw(AssertionError("no call")))
    store.save_plan(tmp_path, {"reviewer": "gpt51", "coder": "gone", "poet": "gpt51"})
    apply_saved_plan(router, tmp_path)
    assert router.model_for_role("reviewer") == "gpt51"
    assert router.model_for_role("coder") == router.config.llm.roles.coder  # unknown key skipped


def test_unknown_check_and_missing_tesseract(
    monkeypatch: pytest.MonkeyPatch, isolated_forge_home: Path
) -> None:
    import asyncio

    with pytest.raises(KeyError):
        asyncio.run(checks.run_check("nonsense"))
    monkeypatch.setattr(checks.shutil, "which", lambda name: None)
    monkeypatch.setattr(checks.Path, "exists", lambda self: False)
    outcome = asyncio.run(checks.run_check("tesseract"))
    assert outcome.status == "warn" and "Not found" in outcome.detail and outcome.hint


def test_check_details_are_redacted() -> None:
    from forge.safety.redact import default_redactor

    default_redactor.register("s3cr3t-value-123", "TEST_KEY")  # check_secrets: fake
    outcome = checks.Outcome("azure", "fail", "it said s3cr3t-value-123 here", "retry s3cr3t-value-123")
    assert "s3cr3t-value-123" not in json.dumps(outcome.to_dict())


@pytest.fixture
def client(isolated_forge_home: Path) -> Iterator[TestClient]:
    security = ServerSecurity(port=8797, token="test-token-0123456789")  # check_secrets: fake
    manager = WebSessionManager(isolated_forge_home, direct_session)
    with TestClient(create_app(manager, security), base_url="http://127.0.0.1:8797") as test_client:
        test_client.get(f"/?t={security.token}", follow_redirects=False)
        yield test_client


def test_environment_endpoints(
    client: TestClient, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin = {"origin": "http://127.0.0.1:8797"}
    overview = client.get("/api/environment").json()
    assert [c["id"] for c in overview["checks"]] == ["system", "azure", "postgres", "gemini", "tesseract"]
    assert overview["saved"]["confirmed_at"] is None and len(overview["plan"]["roles"]) == len(ROLES)

    monkeypatch.setattr(checks.shutil, "which", lambda name: None)
    monkeypatch.setattr(checks.Path, "exists", lambda self: False)
    ran = client.post("/api/environment/check/tesseract", headers=origin).json()
    assert ran["result"]["status"] == "warn"
    assert store.load(isolated_forge_home)["results"]["tesseract"]["status"] == "warn"
    assert client.post("/api/environment/check/nonsense", headers=origin).status_code == 404

    roles = {role: "gpt51" for role in ROLES}
    bad = client.post("/api/environment/confirm", json={"roles": {**roles, "coder": "nope"}}, headers=origin)
    assert bad.status_code == 400 and "Unknown model" in bad.json()["detail"]
    good = client.post("/api/environment/confirm", json={"roles": roles}, headers=origin)
    assert good.status_code == 200 and good.json()["saved"]["plan"] == roles
    assert good.json()["saved"]["confirmed_at"]

"""D-186: the saved environment, the model plan and the setup screen's endpoints. No model calls (the Azure
connectivity check itself is the same code `forge doctor` runs and is covered by the live tests)."""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from forge.config import ROLES, ForgeConfig
from forge.environment import checks, store
from forge.environment.plan import apply_saved_plan, propose_plan, validate_plan
from forge.safety.server_security import ServerSecurity
from forge.vision import ocr
from forge.web.manager import WebSessionManager
from forge.web.server import create_app
from tests.helpers import default_config, mocked_router
from tests.test_web import direct_session

BOTH = {"azure": {"status": "ok", "models": {"gpt51": True, "gpt41": True, "gpt4o": True}}}


def by_role(plan: dict[str, object]) -> dict[str, dict[str, str]]:
    return {entry["role"]: entry for entry in plan["roles"]}  # type: ignore[index, union-attr]


def test_store_round_trip_and_damaged_file(tmp_path: Path) -> None:
    assert store.load(tmp_path) == {"results": {}, "plan": {}, "confirmed_at": None, "answers": {}}
    store.save_result(tmp_path, "azure", {"status": "ok"})
    store.save_plan(tmp_path, {"coder": "gpt51"})
    data = store.load(tmp_path)
    assert data["results"]["azure"]["status"] == "ok" and data["results"]["azure"]["checked_at"]
    assert data["plan"] == {"coder": "gpt51"} and data["confirmed_at"]
    store.save_answer(tmp_path, "tesseract", True)
    store.save_answer(tmp_path, "gemini", False)
    assert store.load(tmp_path)["answers"] == {"tesseract": True, "gemini": False}
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
    assert propose_plan(config, {"postgres_local": {"status": "ok"}}, {})["notes"] == []
    assert propose_plan(config, {"postgres_local": {"status": "warn"}}, {})["notes"]


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
    monkeypatch.setattr(ocr.shutil, "which", lambda name: None)
    monkeypatch.setattr(ocr.Path, "exists", lambda self: False)
    outcome = asyncio.run(checks.run_check("tesseract"))
    # The check only runs after a "yes", so not finding it is a failure, not a shrug.
    assert outcome.status == "fail" and "cannot find it" in outcome.detail and outcome.hint


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
    assert [c["id"] for c in overview["checks"]] == [
        "system",
        "azure",
        "postgres_local",
        "postgres_dev",
        "gemini",
        "node",
        "tavily",
        "tesseract",
    ]
    assert overview["saved"]["confirmed_at"] is None and len(overview["plan"]["roles"]) == len(ROLES)

    tested: list[str] = []
    monkeypatch.setattr(checks, "check_tesseract", lambda: tested.append("tesseract"))  # must not run
    # Nothing is tested until the user answers yes: no answer, then no.
    unanswered = client.post("/api/environment/check/tesseract", headers=origin).json()["result"]
    assert unanswered["status"] == "off" and "Answer the question" in unanswered["detail"]
    said_no = client.post(
        "/api/environment/answer", json={"check": "tesseract", "enabled": False}, headers=origin
    )
    assert said_no.json()["saved"]["answers"] == {"tesseract": False}
    assert said_no.json()["saved"]["results"]["tesseract"]["detail"] == "Not in use."
    assert client.post("/api/environment/check/tesseract", headers=origin).json()["result"]["status"] == "off"
    assert tested == []
    bad_answer = client.post(
        "/api/environment/answer", json={"check": "azure", "enabled": True}, headers=origin
    )
    assert bad_answer.status_code == 400  # only optional tools can be switched off

    client.post("/api/environment/answer", json={"check": "tesseract", "enabled": True}, headers=origin)
    monkeypatch.undo()  # the real check, with the program made to look missing
    monkeypatch.setattr(ocr.shutil, "which", lambda name: None)
    monkeypatch.setattr(ocr.Path, "exists", lambda self: False)
    ran = client.post("/api/environment/check/tesseract", headers=origin).json()
    assert ran["result"]["status"] == "fail"
    assert store.load(isolated_forge_home)["results"]["tesseract"]["status"] == "fail"
    assert client.post("/api/environment/check/nonsense", headers=origin).status_code == 404

    roles = {role: "gpt51" for role in ROLES}
    bad = client.post("/api/environment/confirm", json={"roles": {**roles, "coder": "nope"}}, headers=origin)
    assert bad.status_code == 400 and "Unknown model" in bad.json()["detail"]
    good = client.post("/api/environment/confirm", json={"roles": roles}, headers=origin)
    assert good.status_code == 200 and good.json()["saved"]["plan"] == roles
    assert good.json()["saved"]["confirmed_at"]


def test_azure_check_names_the_missing_values_without_calling_the_network(
    isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import asyncio

    from forge.config import load_config
    from forge.doctor import required_secret_names

    monkeypatch.delenv("FORGE_ENV_FILE", raising=False)
    for name in required_secret_names(load_config(isolated_forge_home)):
        monkeypatch.delenv(name, raising=False)

    outcome = asyncio.run(checks.run_check("azure"))

    assert outcome.status == "fail" and "AZURE_OPENAI_API_KEY" in outcome.missing
    assert "setup guide" in outcome.hint and outcome.to_dict()["missing"] == outcome.missing


def test_the_overview_says_which_checks_ask_a_question(client: TestClient) -> None:
    asked = {c["id"]: c["ask"] for c in client.get("/api/environment").json()["checks"] if c["ask"]}
    assert set(asked) == {"gemini", "tavily", "tesseract", "node"} and "installed" in asked["tesseract"]


WINDOWS_TESSERACT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
TESSERACT = shutil.which("tesseract") or (str(WINDOWS_TESSERACT) if WINDOWS_TESSERACT.exists() else None)


@pytest.mark.skipif(TESSERACT is None, reason="Tesseract is not installed on this machine")
def test_the_real_tesseract_reads_the_test_image() -> None:
    reads, _ = checks._ocr_reads_a_test_image(str(TESSERACT))
    assert reads
    outcome = checks.check_tesseract()
    assert outcome.status == "ok" and "read a test image correctly" in outcome.detail


def test_a_tesseract_that_cannot_read_is_a_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    class Done:
        returncode = 0
        stdout = "tesseract v9.9.9\n"
        stderr = ""

    monkeypatch.setattr(ocr.shutil, "which", lambda name: "tesseract-fake")
    monkeypatch.setattr(checks.subprocess, "run", lambda *a, **k: Done())
    monkeypatch.setattr(checks, "_ocr_reads_a_test_image", lambda binary: (False, "Error opening data file"))
    outcome = checks.check_tesseract()
    assert outcome.status == "warn" and "could not read a test image" in outcome.detail
    assert "Error opening data file" in outcome.detail and "eng.traineddata" in outcome.hint


def test_the_gemini_row_tests_every_gemini_model_and_the_small_one(isolated_forge_home: Path) -> None:
    from forge.config import load_config

    config = load_config(isolated_forge_home)
    tested = checks.gemini_models_to_test(config)
    keys = [key for key, _model in tested]
    assert {"gemini4argon", "gemini31pro", "gemini3flash", "gemini38flash"} <= set(keys) and keys[-1] is None
    assert tested[-1][1].model_name == checks.GEMINI_PROBE_MODEL


GEMINI_ANSWERED = {
    "gemini": {"status": "ok", "models": {"gemini31pro": True, "gemini3flash": True, "gemini38flash": False}}
}


def test_a_gemini_test_that_passed_makes_gemini_the_critic_and_the_judge_and_leaves_the_builder_on_azure() -> (
    None
):
    config = default_config()
    with_argon = {
        "gemini": {"status": "ok", "models": {**GEMINI_ANSWERED["gemini"]["models"], "gemini4argon": True}}
    }
    plan = by_role(propose_plan(config, {**BOTH, **with_argon}, {}))
    for role in ("critic", "judge", "reviewer"):
        assert plan[role]["model"] == "gemini4argon" and "proposed by default" in plan[role]["reason"]
    for role in ("coder", "kb_builder", "summariser", "vision"):
        assert plan[role]["model"] == getattr(
            config.llm.roles, role
        )  # the builder side keeps its Azure model
    no_argon = by_role(propose_plan(config, {**BOTH, **GEMINI_ANSWERED}, {}))
    assert no_argon["critic"]["model"] == "gemini31pro"  # Argon did not answer: the next one in line


def test_the_critic_is_the_coders_model_until_a_critic_is_chosen() -> None:
    config = default_config()
    assert config.llm.roles.critic is None
    plan = by_role(propose_plan(config, BOTH, {}))
    assert plan["critic"]["model"] == config.llm.roles.coder


def test_no_gemini_test_or_a_failed_one_keeps_the_azure_defaults() -> None:
    config = default_config()
    assert by_role(propose_plan(config, BOTH, {}))["judge"]["model"] == config.llm.roles.judge
    failed = {
        "gemini": {
            "status": "fail",
            "models": {"gemini31pro": False, "gemini3flash": False, "gemini38flash": False},
        }
    }
    assert by_role(propose_plan(config, {**BOTH, **failed}, {}))["coder"]["model"] == config.llm.roles.coder


def test_the_model_lists_offer_every_model_with_its_state() -> None:
    config = default_config()
    options = {o["key"]: o for o in propose_plan(config, {**BOTH, **GEMINI_ANSWERED}, {})["options"]}  # type: ignore[index, union-attr]
    assert {"gpt51", "gpt41", "gpt4o", "gemini31pro", "gemini3flash", "gemini38flash"} <= set(options)
    assert options["gemini31pro"]["state"] == "ok" and options["gemini38flash"]["state"] == "failed"
    untested = {o["key"]: o for o in propose_plan(config, BOTH, {})["options"]}  # type: ignore[index, union-attr]
    assert untested["gemini31pro"]["state"] == "untested" and untested["gpt51"]["state"] == "ok"


def test_an_earlier_choice_beats_the_gemini_default() -> None:
    plan = by_role(propose_plan(default_config(), {**BOTH, **GEMINI_ANSWERED}, {"judge": "gpt51"}))
    assert plan["judge"]["model"] == "gpt51" and plan["judge"]["reason"] == "Your earlier choice"


def test_the_node_row_reports_a_missing_node_and_a_certificate_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess

    monkeypatch.setattr("forge.net.installed_node_version", lambda: None)
    missing = checks.check_node()
    assert missing.status == "fail" and "Node.js was not found" in missing.detail and missing.steps

    monkeypatch.setattr("forge.net.installed_node_version", lambda: "v24.7.0")
    monkeypatch.setattr("shutil.which", lambda name: "npm")

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 1, "", "npm error unable to get local issuer certificate")

    monkeypatch.setattr(subprocess, "run", fake_run)
    blocked = checks.check_node()
    assert blocked.status == "fail" and "certificate is not trusted" in blocked.detail and blocked.steps

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, "4.21.5", ""))
    working = checks.check_node()
    assert (
        working.status == "ok"
        and "4.21.5" in working.detail
        and "Windows certificate store" in working.detail
    )


def test_the_planner_is_proposed_on_gemini_once_it_answered_and_follows_the_coder_otherwise() -> None:
    config = default_config()
    with_argon = {"gemini": {"status": "ok", "models": {"gemini4argon": True, "gemini31pro": True}}}
    assert by_role(propose_plan(config, {**BOTH, **with_argon}, {}))["planner"]["model"] == "gemini4argon"
    assert by_role(propose_plan(config, BOTH, {}))["planner"]["model"] == config.llm.roles.coder


def test_the_coder_is_gpt_5_4_once_its_resource_answers_and_the_fallback_is_another_family() -> None:
    config = default_config()
    both_54 = {"azure": {"status": "ok", "models": {**BOTH["azure"]["models"], "gpt54": True}}}
    gemini = {"gemini": {"status": "ok", "models": {"gemini4argon": True, "gemini31pro": True}}}
    plan = by_role(propose_plan(config, {**both_54, **gemini}, {}))
    assert plan["coder"]["model"] == "gpt54" and plan["fallback"]["model"] == "gemini31pro"
    for role in ("kb_builder", "summariser", "vision"):
        assert plan[role]["model"] == getattr(
            config.llm.roles, role
        )  # the high-volume reading work stays on gpt-5.1
    azure_only = by_role(propose_plan(config, both_54, {}))
    assert azure_only["coder"]["model"] == "gpt54" and azure_only["fallback"]["model"] == "gpt51"
    assert (
        by_role(propose_plan(config, BOTH, {}))["coder"]["model"] == config.llm.roles.coder
    )  # no second resource: unchanged

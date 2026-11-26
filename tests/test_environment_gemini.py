"""The Gemini check reports every way it can fail with the steps to fix it (D-205); no Google call is made."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.config import load_config
from forge.environment import checks


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORGE_HOME", str(tmp_path))
    monkeypatch.setenv("FORGE_ENV_FILE", str(tmp_path / ".env"))
    for name in ("GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION"):
        monkeypatch.delenv(name, raising=False)


def test_no_credentials_fail_with_steps(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "some-project")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(tmp_path / "missing.json"))
    outcome = checks.check_gemini(load_config())
    assert outcome.status == "fail" and outcome.steps
    assert "some-project" not in str(outcome.to_dict())  # names only, never values


def test_project_and_location_are_optional(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from forge.doctor import required_secret_names

    config = load_config()
    config.llm.models["gem"] = config.llm.models[next(iter(config.llm.models))].model_copy(
        update={"provider": "gemini", "model_name": "gemini-2.5-pro", "deployment_env": None}
    )
    config.llm.roles.vision = "gem"
    assert not {"GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION"} & required_secret_names(config)


def test_the_models_are_tested_at_once_and_a_silent_one_is_cut_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """The user (2026-11-26): the Gemini test took long; every model is asked at the same time, each one at most
    GEMINI_PROBE_TIMEOUT_S, so a silent model neither blocks the others nor the panel."""
    import asyncio
    import time

    import forge.llm.gemini as gemini_module
    from forge.llm.base import LLMResponse

    class FakeGemini:
        def __init__(self, name: str, model: object, provider: object, secrets: object) -> None:
            self.model = model

        async def chat(self, request: object) -> LLMResponse:
            await asyncio.sleep(30 if self.model.model_name == "silent-model" else 1)  # type: ignore[attr-defined]
            return LLMResponse(text="ready")

        async def close(self) -> None:
            return None

    monkeypatch.setattr(gemini_module, "GeminiProvider", FakeGemini)
    monkeypatch.setattr(checks, "GEMINI_PROBE_TIMEOUT_S", 3)
    config = load_config()
    base = next(iter(config.llm.models.values()))
    for key, name in (("one", "gemini-a"), ("two", "gemini-b"), ("quiet", "silent-model")):
        config.llm.models[key] = base.model_copy(
            update={"provider": "gemini", "model_name": name, "deployment_env": None}
        )
    began = time.monotonic()
    outcome = checks.check_gemini(config)
    assert (
        time.monotonic() - began < 4.5
    )  # one after the other: 1 + 1 + 3 + 1 (the 2.5 probe) = 6 s; at once: 3 s
    assert outcome.models["one"] and outcome.models["two"] and outcome.models["quiet"] is False
    assert "silent-model: no answer within 3 s" in outcome.detail

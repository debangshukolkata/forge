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

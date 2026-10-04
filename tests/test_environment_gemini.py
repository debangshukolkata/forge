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


def test_missing_names_fail_with_steps() -> None:
    outcome = checks.check_gemini(load_config())
    assert outcome.status == "fail" and "GOOGLE_CLOUD_PROJECT" in outcome.detail
    assert outcome.steps == checks.GEMINI_STEPS


def test_no_credentials_fail_with_steps(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "some-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(tmp_path / "missing.json"))
    outcome = checks.check_gemini(load_config())
    assert outcome.status == "fail" and outcome.steps
    assert "some-project" not in str(outcome.to_dict())  # names only, never values

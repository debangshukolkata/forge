from __future__ import annotations

from pathlib import Path

import pytest

from forge.config import load_config, load_secrets
from forge.errors import ConfigError
from forge.safety.redact import Redactor


def test_defaults_load_with_d024_roles(isolated_forge_home: Path) -> None:
    config = load_config(isolated_forge_home)

    assert config.llm.roles.coder == "gpt51"
    assert config.llm.roles.reviewer == "gpt41"
    assert config.llm.models["gpt51"].reasoning_effort == "medium"
    assert config.llm.models["gpt41"].reasoning_effort is None


def test_user_config_is_deep_merged(isolated_forge_home: Path) -> None:
    (isolated_forge_home / "config.yaml").write_text(
        "llm:\n  roles:\n    reviewer: gpt51\nlimits:\n  session_budget_usd: 5\n", encoding="utf-8"
    )

    config = load_config(isolated_forge_home)

    assert config.llm.roles.reviewer == "gpt51"
    assert config.llm.roles.coder == "gpt51"  # untouched keys keep their defaults
    assert config.limits.session_budget_usd == 5


def test_role_pointing_at_unknown_model_is_rejected(isolated_forge_home: Path) -> None:
    (isolated_forge_home / "config.yaml").write_text("llm:\n  roles:\n    coder: gpt99\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="unknown model 'gpt99'"):
        load_config(isolated_forge_home)


def test_typo_in_known_section_is_rejected(isolated_forge_home: Path) -> None:
    (isolated_forge_home / "config.yaml").write_text("limits:\n  session_budget: 5\n", encoding="utf-8")

    with pytest.raises(ConfigError):
        load_config(isolated_forge_home)


def test_secrets_come_from_forge_env_not_current_directory(
    isolated_forge_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FORGE_ENV_FILE", raising=False)
    monkeypatch.delenv("HOST_ONLY_SECRET", raising=False)
    (isolated_forge_home / ".env").write_text("AZURE_OPENAI_API_KEY=forge-key-0123456789\n", encoding="utf-8")
    host_repo = tmp_path / "host_repo"
    host_repo.mkdir()
    (host_repo / ".env").write_text("HOST_ONLY_SECRET=host-secret-0123456789\n", encoding="utf-8")
    monkeypatch.chdir(host_repo)

    secrets = load_secrets(isolated_forge_home, redactor=Redactor())

    assert secrets.get("AZURE_OPENAI_API_KEY") == "forge-key-0123456789"
    assert secrets.get("HOST_ONLY_SECRET") is None


def test_loaded_secrets_are_registered_for_redaction(
    isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FORGE_ENV_FILE", raising=False)
    pg_url = "postgresql://u:pg-password-1@localhost/db"  # check_secrets: fake
    env_text = f"AZURE_OPENAI_API_KEY=abcdef0123456789\nLOCAL_PG_URL={pg_url}\n"
    env_text += "AZURE_OPENAI_ENDPOINT=https://x.openai.azure.com/\n"
    (isolated_forge_home / ".env").write_text(env_text, encoding="utf-8")
    redactor = Redactor()

    load_secrets(isolated_forge_home, redactor=redactor)

    assert redactor.redact("key abcdef0123456789") == "key [REDACTED:AZURE_OPENAI_API_KEY]"
    assert "pg-password-1" not in redactor.redact("login with pg-password-1")
    assert redactor.redact("https://x.openai.azure.com/") == "https://x.openai.azure.com/"  # not a secret


def test_missing_secret_explains_where_to_put_it(
    isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FORGE_ENV_FILE", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    secrets = load_secrets(isolated_forge_home, redactor=Redactor())

    with pytest.raises(ConfigError, match=r"AZURE_OPENAI_API_KEY is not set.*\.env\.example"):
        secrets.require("AZURE_OPENAI_API_KEY")

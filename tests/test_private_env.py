"""D-202: Forge's own variables are not inherited by the commands the model runs."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from forge.toolkit.private_env import private_names, without_private
from forge.toolkit.shell import ShellSession
from forge.workspace.create import create_workspace

SECRET = "exported-secret-0123456789"  # check_secrets: fake
FAKE_PG = "postgresql://u:p@localhost/db"  # check_secrets: fake


@pytest.fixture
def forge_env(isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    env_file = isolated_forge_home / ".env"
    env_file.write_text(f"MY_TOOL_TOKEN=abc\nLOCAL_PG_URL={FAKE_PG}\n", encoding="utf-8")
    monkeypatch.setenv("FORGE_ENV_FILE", str(env_file))
    return env_file


def test_the_names_forge_uses_are_removed_and_the_rest_kept(forge_env: Path) -> None:
    inherited = {
        "PATH": "/usr/bin",
        "MY_UNRELATED": "1",
        "MY_TOOL_TOKEN": SECRET,  # a name in Forge's .env
        "LOCAL_PG_URL": "postgresql://x",  # also in .env
        "FORGE_ENV_FILE": str(forge_env),
        "FORGE_HOME": "/home/a/.forge",
        "AZURE_OPENAI_API_KEY": SECRET,  # the provider settings from config.yaml
        "AZURE_OPENAI_ENDPOINT": "https://x",
        "azure_openai_deployment": "gpt",  # variable names are not case-sensitive on Windows
    }
    kept = without_private(inherited)
    assert kept == {"PATH": "/usr/bin", "MY_UNRELATED": "1"}
    assert {"MY_TOOL_TOKEN", "LOCAL_PG_URL", "FORGE_ENV_FILE", "AZURE_OPENAI_API_KEY"} <= private_names()


def test_a_key_added_later_is_hidden_at_once(forge_env: Path) -> None:
    assert "NEW_KEY_FROM_DRAWER" not in private_names()
    forge_env.write_text(forge_env.read_text(encoding="utf-8") + "NEW_KEY_FROM_DRAWER=v\n", encoding="utf-8")
    stat = forge_env.stat()
    os.utime(forge_env, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))  # the file's modified time moved
    assert "NEW_KEY_FROM_DRAWER" in private_names()


def test_without_any_env_file_only_the_fixed_and_provider_names_go(
    isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FORGE_ENV_FILE", raising=False)
    kept = without_private({"FORGE_ENV_FILE": "x", "AZURE_OPENAI_API_KEY": SECRET, "MY_UNRELATED": "1"})
    assert kept == {"MY_UNRELATED": "1"}


def test_a_command_the_model_runs_does_not_see_them(
    original_repo: Path, tmp_path: Path, forge_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", SECRET)
    monkeypatch.setenv("MY_TOOL_TOKEN", SECRET)
    monkeypatch.setenv("MY_UNRELATED", "kept")
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    shell = ShellSession(workspace, sandbox="off")
    # What Forge sets on purpose (the scratch database of this requirement) is added after and kept.
    shell.extra_env = {"LOCAL_PG_URL": "postgresql://scratch"}

    environment = shell.environment()
    assert "FORGE_ENV_FILE" not in environment and "AZURE_OPENAI_API_KEY" not in environment
    assert "MY_TOOL_TOKEN" not in environment and environment["MY_UNRELATED"] == "kept"
    assert environment["LOCAL_PG_URL"] == "postgresql://scratch"

    shown = subprocess.run(
        [sys.executable, "-c", "import os; print(sorted(os.environ))"],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert SECRET not in shown and "FORGE_ENV_FILE" not in shown and "MY_UNRELATED" in shown


def test_sandboxed_node_tools_get_caches_inside_the_sandbox_folder(
    original_repo: Path, tmp_path: Path
) -> None:
    # Low integrity can't write the profile's npm cache, so npm install failed with EPERM (D-223).
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    shell = ShellSession(workspace, sandbox="off")
    shell.sandbox_active = True
    environment = shell.environment()
    for name in ("npm_config_cache", "YARN_CACHE_FOLDER", "npm_config_store_dir"):
        assert Path(environment[name]).is_relative_to(shell.sandbox_dir)
    shell.sandbox_active = False
    assert "npm_config_cache" not in shell.environment()

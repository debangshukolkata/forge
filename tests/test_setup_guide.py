"""D-204: the settings-file guide (where the .env is, which names, a template, what is filled in), the two
database checks, and that nothing in the web app writes keys. No model calls."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient

from forge.config import load_config, load_secrets
from forge.environment import checks
from forge.environment.guide import build_guide
from forge.safety.server_security import ServerSecurity
from forge.web.manager import WebSessionManager
from forge.web.server import create_app
from tests.conftest import REPO_ROOT
from tests.test_web import direct_session

SECRET = "typed-azure-key-0123456789"  # check_secrets: fake
FAKE_PG = "postgresql://user:pw-0123@localhost:5432/forge_dev"  # check_secrets: fake
UNREACHABLE_PG = "postgresql://nobody:nothing@127.0.0.1:1/none?connect_timeout=2"  # check_secrets: fake


@pytest.fixture
def env_file(isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = isolated_forge_home / ".env"
    monkeypatch.setenv("FORGE_ENV_FILE", str(path))
    for name in (
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_VERSION",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_DEPLOYMENT",
        "AZURE_OPENAI_SECONDARY_DEPLOYMENT",
        "LOCAL_PG_URL",
        "DEV_PG_URL",
        "SERPAPI_API_KEY",
        "TAVILY_TOOL_URL",
        "TAVILY_TOOL_ID",
        "TAVILY_BEARER_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)
    return path


def guide(home: Path) -> dict[str, object]:
    return build_guide(load_config(home), load_secrets(home), home)


def test_the_guide_says_where_the_file_is_and_whether_it_exists(
    isolated_forge_home: Path, env_file: Path
) -> None:
    before = guide(isolated_forge_home)
    assert before["path"] == str(env_file) and before["exists"] is False and before["overridden"] is True
    env_file.write_text("AZURE_OPENAI_API_KEY=x\n", encoding="utf-8")
    assert guide(isolated_forge_home)["exists"] is True


def test_it_names_what_forge_reads_and_what_is_required(isolated_forge_home: Path, env_file: Path) -> None:
    info = guide(isolated_forge_home)
    variables = {v["name"]: v for v in info["variables"]}  # type: ignore[attr-defined, union-attr]
    azure = {n for n, v in variables.items() if v["group"] == "Azure OpenAI"}
    assert azure == {
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_VERSION",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_DEPLOYMENT",
        "AZURE_OPENAI_SECONDARY_DEPLOYMENT",
        "AZURE_FALLBACK_ENDPOINT",
        "AZURE_FALLBACK_API_VERSION",
        "AZURE_FALLBACK_API_KEY",
        "AZURE_FALLBACK_DEPLOYMENT",
    }
    # The fallback model's four values are optional: without them Forge works, it just has no fallback.
    assert all(variables[n]["required"] == (not n.startswith("AZURE_FALLBACK")) for n in azure)
    # Two databases, each with its own variable and its own words; both optional.
    assert (
        variables["LOCAL_PG_URL"]["group"] == "Forge database" and not variables["LOCAL_PG_URL"]["required"]
    )
    assert variables["DEV_PG_URL"]["group"] == "Development database (read-only)"
    assert "never writes" in variables["DEV_PG_URL"]["why"]  # read-only, said in words
    assert {"SERPAPI_API_KEY", "TAVILY_TOOL_URL", "TAVILY_TOOL_ID", "TAVILY_BEARER_TOKEN"} <= set(variables)
    assert "TAVILY_API_KEY" not in variables  # the key itself is not used (D-210)
    assert not any(variables[n]["required"] for n in variables if n.startswith("TAVILY"))
    assert "FORGE_PG_URL" not in variables  # that one is for testing Forge itself, not for using it


def test_the_template_has_every_name_and_only_placeholders(isolated_forge_home: Path, env_file: Path) -> None:
    info = guide(isolated_forge_home)
    template = str(info["template"])
    for variable in info["variables"]:  # type: ignore[attr-defined, union-attr]
        assert f"{variable['name']}={variable['expects']}" in template
    assert "<key>" in template and "https://<resource>.openai.azure.com/" in template
    assert "postgresql://<user>:<password>@localhost:5432/<database>" in template
    assert "Azure OpenAI: required" in template and "Forge database: optional" in template
    assert "one database" not in template.lower()  # no "use one database for both" suggestion


def test_the_guide_never_returns_a_value_only_whether_a_name_is_filled(
    isolated_forge_home: Path, env_file: Path
) -> None:
    env_file.write_text(
        f"AZURE_OPENAI_API_KEY={SECRET}\nLOCAL_PG_URL={FAKE_PG}\nTAVILY_TOOL_URL=\n", encoding="utf-8"
    )
    info = guide(isolated_forge_home)
    assert SECRET not in json.dumps(info) and "pw-0123" not in json.dumps(info)
    filled = {v["name"]: v["filled"] for v in info["variables"]}  # type: ignore[attr-defined, union-attr]
    assert filled["AZURE_OPENAI_API_KEY"] is True and filled["LOCAL_PG_URL"] is True
    assert (
        filled["AZURE_OPENAI_ENDPOINT"] is False and filled["TAVILY_TOOL_URL"] is False
    )  # empty counts as not set


@pytest.fixture
def client(isolated_forge_home: Path) -> Iterator[TestClient]:
    security = ServerSecurity(port=8795, token="test-token-0123456789")  # check_secrets: fake
    manager = WebSessionManager(isolated_forge_home, direct_session)
    with TestClient(create_app(manager, security), base_url="http://127.0.0.1:8795") as test_client:
        test_client.get(f"/?t={security.token}", follow_redirects=False)
        yield test_client


def test_the_setup_endpoint_serves_the_guide_and_nothing_writes_keys(
    client: TestClient, env_file: Path
) -> None:
    origin = {"origin": "http://127.0.0.1:8795"}
    status = client.get("/api/setup", headers=origin).json()
    assert status["path"] == str(env_file) and "AZURE_OPENAI_API_KEY" in status["missing"]
    assert "Copy" not in status["template"] and "AZURE_OPENAI_API_KEY=<key>" in status["template"]
    # Keys are never typed into the app (D-204): there is no endpoint that accepts them.
    for method in ("post", "put"):
        refused = getattr(client, method)(
            "/api/setup/secrets", json={"values": {"AZURE_OPENAI_API_KEY": SECRET}}, headers=origin
        )
        assert refused.status_code in (404, 405) and not env_file.exists()

    env_file.write_text(
        "\n".join(
            f"{n}=value-{i}"
            for i, n in enumerate(
                [
                    "AZURE_OPENAI_ENDPOINT",
                    "AZURE_OPENAI_API_VERSION",
                    "AZURE_OPENAI_API_KEY",
                    "AZURE_OPENAI_DEPLOYMENT",
                    "AZURE_OPENAI_SECONDARY_DEPLOYMENT",
                ]
            )
        ),
        encoding="utf-8",
    )
    after = client.get("/api/setup", headers=origin)
    assert after.json()["missing"] == [] and "value-2" not in after.text  # all filled in; no value comes back


# --- the two database rows ---


def test_a_database_that_is_not_set_is_a_warning_with_its_variable_named(
    env_file: Path, isolated_forge_home: Path
) -> None:
    local = asyncio.run(checks.run_check("postgres_local"))
    dev = asyncio.run(checks.run_check("postgres_dev"))
    assert (
        local.status == "warn" and "LOCAL_PG_URL is not set" in local.detail and "LOCAL_PG_URL" in local.hint
    )
    assert dev.status == "warn" and "DEV_PG_URL is not set" in dev.detail and "DEV_PG_URL" in dev.hint


def test_the_two_databases_are_tested_on_their_own(env_file: Path, isolated_forge_home: Path) -> None:
    """An unreachable development database must not change the Forge database row, and the reverse."""
    env_file.write_text(f"DEV_PG_URL={UNREACHABLE_PG}\n", encoding="utf-8")
    local = asyncio.run(checks.run_check("postgres_local"))
    dev = asyncio.run(checks.run_check("postgres_dev"))
    assert "LOCAL_PG_URL is not set" in local.detail  # the Forge row says nothing about the other database
    assert dev.status in ("warn", "fail") and "LOCAL_PG_URL" not in dev.detail


@pytest.mark.pg
def test_the_real_forge_database_connects(env_file: Path, isolated_forge_home: Path) -> None:
    repo_env = REPO_ROOT / ".env"
    url = dotenv_values(repo_env).get("LOCAL_PG_URL") if repo_env.exists() else None
    if not url:
        pytest.skip("LOCAL_PG_URL not configured in the repo .env")
    try:
        with psycopg.connect(url, connect_timeout=3):
            pass
    except psycopg.Error:
        pytest.skip("local Postgres not reachable")
    env_file.write_text(f"LOCAL_PG_URL={url}\n", encoding="utf-8")
    local = asyncio.run(checks.run_check("postgres_local"))
    assert local.status == "ok" and "pw" not in local.detail.lower().replace("passw", "")
    assert url.split(":", 2)[2].split("@")[0] not in local.detail  # the password never shows

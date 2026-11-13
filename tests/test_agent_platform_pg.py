"""The second test bed, AgentHub PG (RS8, D-592): its API and its two seeded defects, without a model.

The app runs in the fixture's own venv (tests/fixtures/agent_platform_pg/venv, made from its requirements.txt) against
the local Postgres in a `forge_*` schema that is dropped afterwards. The tests skip when either is missing."""

from __future__ import annotations

import hashlib
import json
import secrets
import shutil
import socket
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import psycopg
import pytest
from dotenv import dotenv_values

from tests.conftest import REPO_ROOT

pytestmark = pytest.mark.pg

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "agent_platform_pg"
VENV_PYTHON = FIXTURE / "venv" / "Scripts" / "python.exe"
TOKEN = "console-" + "7hQ2mX9a" * 4  # check_secrets: fake
QUESTION = "What are the names of the deployments?"


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def local_pg_url() -> str:
    env_file = REPO_ROOT / ".env"
    url = dotenv_values(env_file).get("LOCAL_PG_URL") if env_file.exists() else None
    if not url:
        pytest.skip("LOCAL_PG_URL not configured in .env")
    try:
        with psycopg.connect(url, connect_timeout=3):
            pass
    except psycopg.Error:
        pytest.skip("local Postgres not reachable")
    return url


def fill_applications(url: str, schema: str) -> None:
    """The deployment system's state: 120 applications, as a real development database would hold them."""
    import sys

    sys.path.insert(0, str(FIXTURE))
    try:
        from agenthub_pg.sample_data import rows
    finally:
        sys.path.remove(str(FIXTURE))
    with psycopg.connect(url, options=f"-c search_path={schema}", autocommit=True) as connection:
        for name, document in rows():
            connection.execute("INSERT INTO applications VALUES (%s, %s::jsonb)", (name, document))


def copy_app(
    target: Path,
    database_url: str,
    schema: str,
    port: int,
    fake_model: bool,
    extra: dict[str, str] | None = None,
) -> Path:
    shutil.copytree(
        FIXTURE,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "venv", "logs", "*.log", "README.md", ".env"),
    )
    lines = [
        f"APP_DATABASE_URL={database_url}",
        f"APP_SCHEMA_NAME={schema}",
        f"APP_CONSOLE_TOKEN_SHA256={hashlib.sha256(TOKEN.encode()).hexdigest()}",
        f"APP_PORT={port}",
    ]
    if fake_model:
        lines.append("APP_FAKE_MODEL=1")
    lines += [f"{name}={value}" for name, value in (extra or {}).items()]
    (target / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def start_app(folder: Path, port: int) -> subprocess.Popen[bytes]:
    process = subprocess.Popen(
        [str(VENV_PYTHON), "-m", "agenthub_pg.server"],
        cwd=folder,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"AgentHub PG stopped: {process.stderr.read().decode()[-600:]}")  # type: ignore[union-attr]
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                return process
        time.sleep(0.2)
    process.kill()
    raise RuntimeError("AgentHub PG did not start")


@pytest.fixture
def schema() -> Iterator[tuple[str, str]]:
    if not VENV_PYTHON.is_file():
        pytest.skip(
            "the fixture venv is missing (py -3.13 -m venv venv; venv\\Scripts\\pip install -r requirements.txt)"
        )
    url = local_pg_url()
    name = f"forge_hubpg_{secrets.token_hex(4)}"
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(f'CREATE SCHEMA "{name}"')
    yield url, name
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(f'DROP SCHEMA IF EXISTS "{name}" CASCADE')


@pytest.fixture
def hub(schema: tuple[str, str], tmp_path: Path) -> Iterator[tuple[str, Path, tuple[str, str]]]:
    url, name = schema
    port = free_port()
    folder = copy_app(tmp_path / "app", url, name, port, fake_model=True)
    process = start_app(
        folder, port
    )  # seeds the empty schema: the tables exist, the applications table is empty
    fill_applications(schema[0], schema[1])
    yield f"http://127.0.0.1:{port}", folder, schema
    process.kill()
    process.wait(timeout=10)


AUTH = {"Authorization": f"Bearer {TOKEN}"}


def test_the_api_needs_the_console_token(hub: tuple[str, Path, tuple[str, str]]) -> None:
    base, _, _ = hub
    assert httpx.get(f"{base}/api/agents").status_code == 401
    assert httpx.get(f"{base}/api/agents", headers={"Authorization": "Bearer nope"}).status_code == 401
    listed = httpx.get(f"{base}/api/agents", headers=AUTH)
    assert listed.status_code == 200 and listed.json()["agents"] == ["billing", "ops", "support"]


def test_a_run_is_logged_and_has_the_documented_shape(hub: tuple[str, Path, tuple[str, str]]) -> None:
    base, folder, _ = hub
    answer = httpx.post(
        f"{base}/api/agents/billing/run", json={"question": "list the invoices"}, headers=AUTH, timeout=30
    ).json()
    assert answer["status"] == "ok" and answer["tool"] == "list_invoices" and "INV-0000" in answer["answer"]
    unknown = httpx.post(f"{base}/api/agents/nobody/run", json={"question": "x"}, headers=AUTH)
    assert unknown.status_code == 404
    runs = [
        json.loads(line) for line in (folder / "logs" / "runs.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert runs[0]["agent"] == "billing" and runs[0]["status"] == "ok"


def test_the_ops_agent_cannot_list_the_deployments_and_the_reason_is_only_in_the_log(
    hub: tuple[str, Path, tuple[str, str]],
) -> None:
    """Defect 1: the tool's answer is larger than the agent's context."""
    base, folder, _ = hub
    answer = httpx.post(
        f"{base}/api/agents/ops/run", json={"question": QUESTION}, headers=AUTH, timeout=60
    ).json()
    assert answer == {"status": "failed", "error": "the agent could not finish"}
    entry = json.loads((folder / "logs" / "runs.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert entry["tool"] == "list_deployments" and entry["tool_result_chars"] > entry["limit"] == 20000


def test_the_support_prompt_tells_the_agent_to_answer_in_english(
    hub: tuple[str, Path, tuple[str, str]],
) -> None:
    """Defect 2: the cause is a row of the agents table; the tool and the API are fine."""
    base, _, (url, schema) = hub
    with psycopg.connect(url, options=f"-c search_path={schema}") as connection:
        prompt = connection.execute("SELECT system_prompt FROM agents WHERE name = 'support'").fetchone()[0]  # type: ignore[index]
    assert "Always answer in English" in prompt
    answer = httpx.post(
        f"{base}/api/agents/support/run",
        json={"question": "Wie kann ich mein Passwort zuruecksetzen?"},
        headers=AUTH,
        timeout=30,
    ).json()
    assert (
        answer["status"] == "ok" and answer["tool"] == "faq_lookup" and "Reset password" in answer["answer"]
    )


async def test_the_stream_endpoint_is_read_by_event_through_http_request(
    hub: tuple[str, Path, tuple[str, str]],
    original_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RS9 (D-599): the ops agent's run, as a stream: the call that stalls is visible, the error comes in the middle."""
    from forge.toolkit.base import ToolContext
    from forge.tools.http_request import HttpRequest
    from forge.workspace.create import create_workspace

    base, _, _ = hub
    env_file = tmp_path / "debcraft.env"
    env_file.write_text(f"DEVELOPMENT_INSTANCE_TOKEN={TOKEN}\n", encoding="utf-8")
    monkeypatch.setenv("FORGE_ENV_FILE", str(env_file))
    monkeypatch.delenv("DEVELOPMENT_INSTANCE_TOKEN", raising=False)
    context = ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))

    result = await HttpRequest().run(
        HttpRequest.Args(
            method="POST",
            url=f"{base}/api/agents/ops/stream",
            json={"question": QUESTION},
            token_env="DEVELOPMENT_INSTANCE_TOKEN",
            stream=True,
            timeout_s=60,
        ),
        context,
    )

    assert result.ok and "HTTP 200" in result.content
    assert "run_started x1" in result.content and "tool_call list_deployments" in result.content
    assert "tool_result list_deployments (" in result.content  # its size is in the account
    assert "Error event" in result.content and "the agent could not finish" in result.content
    assert TOKEN not in result.content

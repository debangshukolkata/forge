"""http_request against a running application that needs a token only the user has (D-568).

The application is the AgentHub fixture (tests/fixtures/agent_platform): an agent platform whose API wants
`Authorization: Bearer <console token>`. The token sits in DebCraft's .env under a name; the model gives the
name, DebCraft sends the value, and the value appears in no result."""

from __future__ import annotations

import hashlib
import json
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from forge.toolkit.base import ToolContext, ToolResult
from forge.tools.http_request import HttpRequest, allowed_token_names, json_shape
from forge.workspace.create import create_workspace
from tests.conftest import REPO_ROOT

TOKEN = "console-" + "7hQ2mX9a" * 4  # check_secrets: fake
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "agent_platform"


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def copy_fixture(target: Path, port: int) -> Path:
    shutil.copytree(FIXTURE, target, ignore=shutil.ignore_patterns("__pycache__", "data", "logs"))
    (target / ".env").write_text(
        f"CONSOLE_TOKEN_SHA256={hashlib.sha256(TOKEN.encode()).hexdigest()}\nPORT={port}\n", encoding="utf-8"
    )
    return target


def start_hub(folder: Path, port: int) -> subprocess.Popen[bytes]:
    process = subprocess.Popen(
        [sys.executable, "-m", "agenthub.server"],
        cwd=folder,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                return process
        time.sleep(0.2)
    process.kill()
    raise RuntimeError("the AgentHub fixture did not start")


@pytest.fixture
def hub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[str, ToolContext, Path]]:
    port = free_port()
    folder = copy_fixture(tmp_path / "hub", port)
    env_file = tmp_path / "debcraft.env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("FORGE_ENV_FILE", str(env_file))
    monkeypatch.delenv("DEVELOPMENT_INSTANCE_TOKEN", raising=False)
    process = start_hub(folder, port)
    workspace = create_workspace(folder, tmp_path / "ws", "")
    yield f"http://127.0.0.1:{port}", ToolContext(workspace=workspace), env_file
    process.kill()
    process.wait(timeout=10)


async def _call(context: ToolContext, **fields: object) -> ToolResult:
    return await HttpRequest().run(HttpRequest.Args(**fields), context)  # type: ignore[arg-type]


async def test_a_token_from_the_env_file_is_sent_by_name_and_never_shown(
    hub: tuple[str, ToolContext, Path],
) -> None:
    base, context, env_file = hub
    plain = await _call(context, url=f"{base}/api/agents")
    assert (
        "HTTP 401" in plain.content and "DEVELOPMENT_INSTANCE_TOKEN" in plain.content
    )  # says what is needed

    absent = await _call(context, url=f"{base}/api/agents", token_env="DEVELOPMENT_INSTANCE_TOKEN")
    assert not absent.ok and "is not set in" in absent.content and str(env_file) in absent.content
    assert "ask_user" in absent.content and "paste the token into the chat" in absent.content

    env_file.write_text(
        f"DEVELOPMENT_INSTANCE_TOKEN={TOKEN}\n", encoding="utf-8"
    )  # the user adds it mid-session
    listed = await _call(context, url=f"{base}/api/agents", token_env="DEVELOPMENT_INSTANCE_TOKEN")
    assert listed.ok and "HTTP 200" in listed.content and '"ops"' in listed.content
    assert TOKEN not in listed.content and TOKEN not in json.dumps(listed.meta)

    env_file.write_text("DEVELOPMENT_INSTANCE_TOKEN=an-expired-token\n", encoding="utf-8")
    expired = await _call(context, url=f"{base}/api/agents", token_env="DEVELOPMENT_INSTANCE_TOKEN")
    assert "HTTP 401" in expired.content and "may have expired" in expired.content


async def test_only_names_the_user_released_can_be_sent(hub: tuple[str, ToolContext, Path]) -> None:
    base, context, env_file = hub
    own_key = "sk-own-" + "Zz91Kk02" * 4  # check_secrets: fake
    env_file.write_text(f"AZURE_OPENAI_API_KEY={own_key}\nSTAGING_TOKEN={TOKEN}\n", encoding="utf-8")
    refused = await _call(context, url=f"{base}/api/agents", token_env="AZURE_OPENAI_API_KEY")
    assert (
        not refused.ok
        and "not a token the user has released" in refused.content
        and own_key not in refused.content
    )
    other = await _call(context, url=f"{base}/api/agents", token_env="STAGING_TOKEN")
    assert not other.ok  # not released yet

    env_file.write_text(f"FORGE_REQUEST_TOKEN_NAMES=STAGING_TOKEN\nSTAGING_TOKEN={TOKEN}\n", encoding="utf-8")
    released = await _call(context, url=f"{base}/api/agents", token_env="STAGING_TOKEN")
    assert released.ok and "HTTP 200" in released.content
    assert allowed_token_names("A, B") == {"DEVELOPMENT_INSTANCE_TOKEN", "A", "B"}

    elsewhere = await _call(context, url="https://example.com/api", token_env="STAGING_TOKEN")
    assert not elsewhere.ok and "localhost" in elsewhere.content  # a token never leaves this machine


async def test_an_agent_run_is_reported_with_its_size(hub: tuple[str, ToolContext, Path]) -> None:
    base, context, env_file = hub
    env_file.write_text(f"DEVELOPMENT_INSTANCE_TOKEN={TOKEN}\n", encoding="utf-8")
    failed = await _call(
        context,
        method="POST",
        url=f"{base}/api/agents/ops/run",
        json={"question": "What are the names of the deployments?"},
        token_env="DEVELOPMENT_INSTANCE_TOKEN",
        timeout_s=120,
    )
    assert failed.ok and '"status": "failed"' in failed.content and "Answer: " in failed.content
    worked = await _call(
        context,
        method="POST",
        url=f"{base}/api/agents/billing/run",
        json={"question": "list the invoices"},
        token_env="DEVELOPMENT_INSTANCE_TOKEN",
    )
    assert (
        '"status": "ok"' in worked.content
        and "Parts by size:" in worked.content
        and "answer: str" in worked.content
    )


def test_the_shape_of_a_large_answer_shows_which_part_is_large() -> None:
    sys.path.insert(0, str(FIXTURE))
    try:
        from agenthub import deployment_api  # type: ignore[import-not-found]

        body = json.loads(deployment_api.call("/api/v1/applications"))
    finally:
        sys.path.remove(str(FIXTURE))
    lines = json_shape(body)
    assert lines[0].startswith("body: object with 1 keys, 3") and "characters" in lines[0]
    assert "items: list of 120 items" in lines[1]
    text = "\n".join(lines)
    assert (
        "each item (the first): object with 3 keys" in text
        and "status: object" in text
        and "metadata: object" in text
    )


async def test_a_missing_token_is_asked_for_by_the_tool_itself(hub: tuple[str, ToolContext, Path]) -> None:
    base, context, env_file = hub
    asked: list[str] = []

    async def user_adds_it(question: str, detail: str, options: list[object], recommended: str | None) -> str:
        asked.append(question + "\n" + detail)
        env_file.write_text(f"DEVELOPMENT_INSTANCE_TOKEN={TOKEN}\n", encoding="utf-8")
        return "The user chose: I have added it"

    context.ask_user = user_adds_it
    result = await _call(context, url=f"{base}/api/agents", token_env="DEVELOPMENT_INSTANCE_TOKEN")
    assert result.ok and "HTTP 200" in result.content and TOKEN not in result.content
    assert (
        len(asked) == 1 and "DEVELOPMENT_INSTANCE_TOKEN=<the token>" in asked[0] and str(env_file) in asked[0]
    )
    assert "Do not paste it into the chat" in asked[0]

    again = await _call(context, url=f"{base}/api/agents", token_env="DEVELOPMENT_INSTANCE_TOKEN")
    assert again.ok and len(asked) == 1  # it is there now: no second question

    env_file.write_text("", encoding="utf-8")

    async def user_cannot(question: str, detail: str, options: list[object], recommended: str | None) -> str:
        return "The user chose: I cannot get a token"

    context.ask_user = user_cannot
    refused = await _call(context, url=f"{base}/api/agents", token_env="DEVELOPMENT_INSTANCE_TOKEN")
    assert not refused.ok and "was not verified" in refused.content

    async def user_says_added_but_did_not(
        question: str, detail: str, options: list[object], recommended: str | None
    ) -> str:
        return "The user chose: I have added it"

    context.ask_user = user_says_added_but_did_not
    still = await _call(context, url=f"{base}/api/agents", token_env="DEVELOPMENT_INSTANCE_TOKEN")
    assert not still.ok and "is not set in" in still.content

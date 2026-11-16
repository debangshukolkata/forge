"""Live (real Azure model): DebCraft fixes the user's `app_logins.yaml` through `settings_file` (D-618).

The file is the unfinished one found on the office laptop (`dev:` and `sit:` at the top, no `environments:`, no sign-in
settings). The user gives the login addresses and steps in their message. The model has to find the tool (it is in a
deferred group), read the file, and propose a whole valid file; the red card is approved, as a user would.
Set SETTINGS_LOG to a file to get one JSON line."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from forge.config import load_config, load_secrets
from forge.engine.headless import auto_reply
from forge.engine.session_host import SessionHost
from forge.llm.router import LLMRouter
from forge.protocol.events import Event, EventBus, EventType
from forge.protocol.inputs import Answer, SendMessage, UserInput
from forge.toolkit.app_logins import load_logins
from forge.workspace.create import create_workspace
from tests.conftest import REPO_ROOT

pytestmark = pytest.mark.live

UNFINISHED = (
    "dev:\n  check_url: https://dev.example.com/wnxtv4/api/me\n  warn_without_token: true\n"
    "sit:\n  check_url: https://sit.example.com/wnxt/api/me\n  warn_without_token: true\n"
)
REQUEST = (
    "My app_logins.yaml is unfinished, so sign-in to dev does not work. Fix it. For dev: the login page is "
    "https://dev.example.com/wnxtv4/ ; the token is the cookie access_token_cookie and is kept under the name "
    "DEVELOPMENT_INSTANCE_TOKEN; the steps are: click 'Sign in', wait for an address containing uuid_key, click "
    "'Proceed', wait for an address containing landing-home. Keep the check addresses and the warning setting that "
    "are already there. Leave sit as it is for now."
)


async def test_the_model_finds_the_tool_and_writes_a_file_the_reader_accepts(
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FORGE_ENV_FILE", str(REPO_ROOT / ".env"))
    secrets = load_secrets(isolated_forge_home)
    if not secrets.get("AZURE_OPENAI_API_KEY"):
        pytest.skip("AZURE_OPENAI_* not configured in .env")
    (isolated_forge_home / "app_logins.yaml").write_text(UNFINISHED, encoding="utf-8")
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    host = SessionHost(
        LLMRouter(load_config(isolated_forge_home), secrets),
        EventBus(workspace.forge_dir / "events.jsonl"),
        workspace=workspace,
        permission_mode="auto",
    )
    calls: list[str] = []
    cards: list[str] = []
    said: list[str] = []

    def react(event: Event) -> UserInput | None:
        if event.type == EventType.TOOL_CALL_STARTED:
            calls.append(f"{event.payload['name']} {str(event.payload['arguments'])[:80]}")
        if event.type == EventType.MESSAGE_DONE:
            said.append(str(event.payload.get("text", "")))
        if event.type == EventType.ERROR:
            said.append(f"ERROR {event.payload}")
        if event.type == EventType.QUESTION_ASKED and event.payload.get("danger"):
            cards.append(str(event.payload.get("context", "")))
            return Answer(
                question_id=event.payload["id"], choice=event.payload["options"][0]["label"], text=None
            )
        if event.type == EventType.QUESTION_ASKED and "stronger model" in str(event.payload.get("question")):
            # The model sometimes offers the picture-task switch; this machine has no stronger deployment, so decline.
            return Answer(
                question_id=event.payload["id"], choice=event.payload["options"][-1]["label"], text=None
            )
        return auto_reply(event, auto_approve=True)

    runner = asyncio.create_task(host.run())
    subscription = host.bus.subscribe(since_seq=host.bus.last_seq)
    await host.submit(SendMessage(text=REQUEST))
    try:
        async with asyncio.timeout(420):
            async for event in subscription:
                if (reply := react(event)) is not None:
                    await host.submit(reply)
                if event.type in (EventType.COST_UPDATED, EventType.ERROR):
                    break
    finally:
        subscription.close()
        runner.cancel()
        await host.close()
    final = (isolated_forge_home / "app_logins.yaml").read_text(encoding="utf-8")
    if os.environ.get("SETTINGS_LOG"):
        with open(os.environ["SETTINGS_LOG"], "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"calls": calls, "cards": len(cards), "file": final}) + "\n")
    print(f"\nCALLS: {calls}\nCARDS: {len(cards)}\nSAID: {said[-1:]}\nFILE:\n{final}")
    assert any(call.startswith("settings_file") for call in calls), calls
    assert cards, "the user was never shown a card"
    assert "REDACTED" not in cards[-1] and "token_name: DEVELOPMENT_INSTANCE_TOKEN" in cards[-1], cards[-1]
    logins = load_logins(isolated_forge_home)  # the real reader accepts what the model wrote
    dev = logins["dev"]
    assert (
        dev.login_url == "https://dev.example.com/wnxtv4/" and dev.token_name == "DEVELOPMENT_INSTANCE_TOKEN"
    )
    assert dev.token_cookie == "access_token_cookie" and len(dev.steps) == 4
    assert dev.check_url.endswith("/wnxtv4/api/me") and dev.warn_without_token

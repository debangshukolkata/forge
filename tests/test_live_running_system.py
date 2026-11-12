"""Live (real Azure model): DebCraft makes an existing system fulfil a requirement by running it (D-568).

The system is the AgentHub fixture: agents and their tools are rows in a database, the API needs a console
token, and the ops agent cannot answer "What are the names of the deployments?" because its only fitting tool
returns 343,634 characters and its context holds 20,000. The API's answer says only "the agent could not
finish"; the reason is in the run log. DebCraft is given the requirement and nothing else.

`token_ready`: the token is already in DebCraft's .env. `token_asked`: it is not; DebCraft has to ask the user
for it, and the test then puts it into the file and answers "done".

A run passes when the test itself, afterwards, starts the changed copy and the agent answers with the names.
Set RUNNING_SYSTEM_LOG to a file to get one JSON line per run."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import httpx
import pytest

from forge.config import load_config, load_secrets
from forge.engine.headless import auto_reply
from forge.engine.session_host import SessionHost
from forge.llm.router import LLMRouter
from forge.protocol.events import Event, EventBus, EventType
from forge.protocol.inputs import Answer, SendMessage, UserInput
from forge.workspace.create import create_workspace
from tests.conftest import REPO_ROOT
from tests.test_http_request import TOKEN, copy_fixture, free_port, start_hub

pytestmark = pytest.mark.live

QUESTION = "What are the names of the deployments?"
REQUIREMENT = (
    f"The ops agent of this platform should be able to answer the question '{QUESTION}' with the names of the "
    "deployments. Make that work."
)
TURN_SECONDS = 1500


@pytest.mark.parametrize("scenario", ["token_ready", "token_asked"])
async def test_a_requirement_is_solved_by_running_the_system(
    scenario: str, tmp_path: Path, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    own_env = (REPO_ROOT / ".env").read_text(encoding="utf-8")
    env_file = tmp_path / "debcraft.env"
    env_file.write_text(
        own_env + (f"\nDEVELOPMENT_INSTANCE_TOKEN={TOKEN}\n" if scenario == "token_ready" else "\n"),
        encoding="utf-8",
    )
    monkeypatch.setenv("FORGE_ENV_FILE", str(env_file))
    monkeypatch.delenv("DEVELOPMENT_INSTANCE_TOKEN", raising=False)
    secrets = load_secrets(isolated_forge_home)
    if not secrets.get("AZURE_OPENAI_API_KEY"):
        pytest.skip("AZURE_OPENAI_* not configured in .env")
    repo = copy_fixture(tmp_path / "repo", free_port())
    workspace = create_workspace(repo, tmp_path / "ws", "")
    host = SessionHost(
        LLMRouter(load_config(isolated_forge_home), secrets),
        EventBus(workspace.forge_dir / "events.jsonl"),
        workspace=workspace,
        permission_mode="auto",
    )
    calls: list[str] = []
    asked_user: list[str] = []
    said: list[str] = []

    def reply(event: Event) -> UserInput | None:
        if event.type == EventType.TOOL_CALL_STARTED:
            calls.append(f"{event.payload['name']} {event.payload['arguments']}"[:500])
        if event.type == EventType.MESSAGE_DONE:
            said.append(str(event.payload.get("text", "")))
        if event.type == EventType.USER_ACTION_REQUESTED:
            asked_user.append(json.dumps(event.payload)[:700])
            with env_file.open("a", encoding="utf-8") as handle:  # the user does what was asked
                handle.write(f"\nDEVELOPMENT_INSTANCE_TOKEN={TOKEN}\n")
            return Answer(question_id=event.payload["id"], choice="done", text=None)
        if event.type == EventType.QUESTION_ASKED and "DEVELOPMENT_INSTANCE_TOKEN" in json.dumps(
            event.payload
        ):
            asked_user.append(json.dumps(event.payload)[:700])
            with env_file.open("a", encoding="utf-8") as handle:  # the user adds the token, then answers
                handle.write(f"\nDEVELOPMENT_INSTANCE_TOKEN={TOKEN}\n")
            return Answer(question_id=event.payload["id"], choice="I have added it", text=None)
        return auto_reply(event, auto_approve=True)

    runner = asyncio.create_task(host.run())
    subscription = host.bus.subscribe(since_seq=host.bus.last_seq)
    await host.submit(SendMessage(text=REQUIREMENT))
    finished = False
    try:
        async with asyncio.timeout(TURN_SECONDS):
            async for event in subscription:
                if (answer := reply(event)) is not None:
                    await host.submit(answer)
                if event.type in (EventType.COST_UPDATED, EventType.ERROR):
                    finished = True
                    break
    except TimeoutError:
        pass
    finally:
        subscription.close()
        runner.cancel()
        await host.close()

    # The test's own check, on the copy DebCraft changed: start it and ask the agent.
    port = free_port()
    monkeypatch.setenv("PORT", str(port))
    process = start_hub(workspace.repo_dir, port)
    try:
        response = httpx.post(
            f"http://127.0.0.1:{port}/api/agents/ops/run",
            json={"question": QUESTION},
            headers={"Authorization": f"Bearer {TOKEN}"},
            timeout=60,
        )
        other = httpx.post(
            f"http://127.0.0.1:{port}/api/agents/billing/run",
            json={"question": "list the invoices"},
            headers={"Authorization": f"Bearer {TOKEN}"},
            timeout=60,
        )
    finally:
        process.kill()
        process.wait(timeout=10)
    body = response.json()
    answer_text = str(body.get("answer", ""))
    names = [
        name for name in ("payments-api-000", "search-worker-001", "shipping-api-005") if name in answer_text
    ]
    tools_used = [call.split(" ")[0] for call in calls]
    row = {
        "scenario": scenario,
        "finished": finished,
        "calls": len(calls),
        "used_token_by_name": any("token_env" in call for call in calls),
        "asked_user": asked_user,
        "read_run_log": any("runs.jsonl" in call or "logs" in call for call in calls),
        "loaded_skill": any("solve-against-running-system" in call for call in calls),
        "called_the_api": sum(1 for call in calls if call.startswith("http_request")),
        "wrote_knowledge": "knowledge_write" in tools_used,
        "changed": sorted({change.path for change in workspace.changes()}),
        "final_status": body.get("status"),
        "final_tool": body.get("tool"),
        "answer_chars": len(answer_text),
        "names_found": names,
        "other_agent_still_ok": other.json().get("status"),
        "asks": [
            call[:260]
            for call in calls
            if call.startswith(("request_app_secret", "ask_user", "request_user_action"))
        ],
        "tools": tools_used,
        "said": "\n".join(said)[-900:],
    }
    log = os.environ.get("RUNNING_SYSTEM_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
    print(
        "\n"
        + json.dumps({key: value for key, value in row.items() if key not in ("said", "tools")}, indent=1)
    )
    assert TOKEN not in json.dumps(row), "the token reached an event or the model's text"
    assert body.get("status") == "ok", f"the agent still cannot answer: {body}; calls: {tools_used}"
    assert len(names) == 3 and len(answer_text) <= 20000, f"the answer is not the names: {answer_text[:200]}"
    assert other.json().get("status") == "ok", "the change broke another agent"
    if scenario == "token_asked":
        assert asked_user and "DEVELOPMENT_INSTANCE_TOKEN" in asked_user[0], (
            f"the user was not asked: {asked_user}"
        )

"""Live (real Azure model): a command needs a secret only the user has (D-569).

Seen on the office laptop: a script needed a JWT; DebCraft asked for it "in your next message", the chat masked
it, and DebCraft asked again, three times. Here the repository has `scripts/list_out_of_sync.py`, which calls a
deployment service with `ARGOCD_TOKEN` from the environment. The service (started by the test on localhost)
answers 401 without the token.

`not_given`: the user only states the requirement. `pasted`: the user pastes the JWT into the message, as on
the office laptop; the model sees `[REDACTED]`.

A run passes when DebCraft got the secret through `request_app_secret` (the test plays the user: it writes the
lines the card names into DebCraft's .env and agrees), the final answer names the two applications that are out
of sync, and the token is in no event. Set APP_SECRET_LOG to a file to get one JSON line per run."""

from __future__ import annotations

import asyncio
import json
import os
import re
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from forge.config import load_config, load_secrets
from forge.engine.headless import auto_reply
from forge.engine.session_host import SessionHost
from forge.llm.router import LLMRouter
from forge.protocol.events import Event, EventBus, EventType
from forge.protocol.inputs import Answer, SendMessage, UserInput
from forge.tools.app_keys_tool import ALLOW
from forge.workspace.create import create_workspace
from tests.conftest import REPO_ROOT

pytestmark = pytest.mark.live

JWT = ".".join(
    ["eyJhbGciOiJIUzI1NiJ9", "eyJzdWIiOiJkZWJjcmFmdC10ZXN0In0", "c2lnbmF0dXJl" + "Qq7Ww8" * 4]
)  # check_secrets: fake
APPLICATIONS = [
    {"name": "ledger-sync-014", "sync": "OutOfSync"},
    {"name": "mail-router-007", "sync": "OutOfSync"},
    {"name": "search-indexer-002", "sync": "Synced"},
    {"name": "invoice-pdf-021", "sync": "Synced"},
]
SCRIPT = '''"""Lists the applications that are out of sync. Needs ARGOCD_TOKEN (a JWT from the ArgoCD console)."""

import json
import os
import sys
import urllib.error
import urllib.request

URL = "http://127.0.0.1:{port}/api/v1/applications"


def main() -> int:
    token = os.environ.get("ARGOCD_TOKEN")
    if not token:
        print("ARGOCD_TOKEN is not set", file=sys.stderr)
        return 2
    request = urllib.request.Request(URL, headers={{"Authorization": "Bearer " + token}})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            applications = json.load(response)["items"]
    except urllib.error.HTTPError as error:
        print(f"the deployment service answered {{error.code}}", file=sys.stderr)
        return 1
    for application in applications:
        if application["sync"] != "Synced":
            print(application["name"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''
REQUIREMENT = {
    "not_given": "Run scripts/list_out_of_sync.py and tell me which applications are out of sync.",
    "pasted": "Run scripts/list_out_of_sync.py and tell me which applications are out of sync. "
    f"It needs my ArgoCD token, here it is: {JWT}",
    # D-570, as on the office laptop: the value is already in DebCraft's .env and the user says so. DebCraft
    # must use it (one click) instead of asking the user to restart, to copy it or to set it somewhere else.
    "in_file": "Run scripts/list_out_of_sync.py and tell me which applications are out of sync. "
    "I have already put ARGOCD_TOKEN into DebCraft's .env file.",
}
TURN_SECONDS = 900


@pytest.fixture
def deployment_service() -> Iterator[int]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            allowed = self.headers.get("Authorization") == f"Bearer {JWT}"
            body = json.dumps({"items": APPLICATIONS} if allowed else {"error": "unauthenticated"}).encode()
            self.send_response(200 if allowed else 401)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:  # keep the test output quiet
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield int(server.server_address[1])
    server.shutdown()


@pytest.mark.parametrize("scenario", ["not_given", "pasted", "in_file"])
async def test_a_command_gets_the_users_secret_without_the_model_seeing_it(
    scenario: str,
    tmp_path: Path,
    isolated_forge_home: Path,
    monkeypatch: pytest.MonkeyPatch,
    deployment_service: int,
) -> None:
    env_file = tmp_path / "debcraft.env"
    env_file.write_text(
        (REPO_ROOT / ".env").read_text(encoding="utf-8")
        + (f"\nARGOCD_TOKEN={JWT}\n" if scenario == "in_file" else "\n"),
        encoding="utf-8",
    )
    monkeypatch.setenv("FORGE_ENV_FILE", str(env_file))
    monkeypatch.delenv("ARGOCD_TOKEN", raising=False)
    secrets = load_secrets(isolated_forge_home)
    if not secrets.get("AZURE_OPENAI_API_KEY"):
        pytest.skip("AZURE_OPENAI_* not configured in .env")
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "list_out_of_sync.py").write_text(
        SCRIPT.format(port=deployment_service), encoding="utf-8"
    )
    (repo / "README.md").write_text(
        "# Deployment helpers\n\nSmall scripts for the release team.\n", encoding="utf-8"
    )
    workspace = create_workspace(repo, tmp_path / "ws", "")
    host = SessionHost(
        LLMRouter(load_config(isolated_forge_home), secrets),
        EventBus(workspace.forge_dir / "events.jsonl"),
        workspace=workspace,
        permission_mode="auto",
    )
    calls: list[str] = []
    cards: list[str] = []
    other_questions: list[str] = []
    said: list[str] = []
    released: list[str] = []

    def reply(event: Event) -> UserInput | None:
        if event.type == EventType.TOOL_CALL_STARTED:
            calls.append(f"{event.payload['name']} {event.payload['arguments']}"[:400])
        if event.type == EventType.MESSAGE_DONE:
            said.append(str(event.payload.get("text", "")))
        if event.type == EventType.QUESTION_ASKED:
            text = json.dumps(event.payload)
            card = re.search(r"commands of this project use ([A-Z0-9_, ]+) from your DebCraft", text)
            if card:  # the request_app_secret card: the user adds what the card says is missing, then agrees
                cards.append(text[:900])
                names = [name.strip() for name in card.group(1).split(",")]
                released.extend(names)
                if "<the value>" in text:
                    with env_file.open("a", encoding="utf-8") as handle:
                        handle.write("".join(f"\n{name}={JWT}\n" for name in names))
                return Answer(question_id=event.payload["id"], choice=ALLOW, text=None)
            other_questions.append(text[:500])
        return auto_reply(event, auto_approve=True)

    runner = asyncio.create_task(host.run())
    subscription = host.bus.subscribe(since_seq=host.bus.last_seq)
    await host.submit(SendMessage(text=REQUIREMENT[scenario]))
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

    tools_used = [call.split(" ")[0] for call in calls]
    final = said[-1] if said else ""
    events_text = (workspace.forge_dir / "events.jsonl").read_text(encoding="utf-8")
    row = {
        "scenario": scenario,
        "finished": finished,
        "calls": len(calls),
        "asked_for_the_secret_by_name": [
            call[:160] for call in calls if call.startswith("request_app_secret")
        ],
        "cards": len(cards),
        "ask_user_calls": tools_used.count("ask_user"),
        "user_action_calls": [call[:300] for call in calls if call.startswith("request_user_action")],
        "other_questions": other_questions,
        "names_in_answer": [app["name"] for app in APPLICATIONS if app["name"] in final],
        "token_in_events": JWT in events_text,
        "tools": tools_used,
        "said": final[-700:],
    }
    log = os.environ.get("APP_SECRET_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
    print("\n" + json.dumps({key: value for key, value in row.items() if key != "tools"}, indent=1))
    assert JWT not in events_text and JWT not in json.dumps(row), "the token reached an event or the model"
    assert cards and "ARGOCD_TOKEN" in released, f"the secret was not asked for by name: {tools_used}"
    assert row["names_in_answer"] == ["ledger-sync-014", "mail-router-007"], f"wrong answer: {final[-400:]}"

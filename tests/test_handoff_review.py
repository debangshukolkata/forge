"""D-571: app.env, the facts the model is told about its installation, the remembered token form, and the
second model that looks at a hand-off before the user sees it."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from forge.agent.loop import system_prompt
from forge.toolkit.app_keys import installation_facts, remembered_auth
from forge.toolkit.base import ToolContext, ToolResult
from forge.toolkit.shell import ShellSession
from forge.tools.app_keys_tool import RequestAppSecret
from forge.tools.http_request import HttpRequest
from forge.tools.interaction import RequestUserAction
from forge.workspace.create import create_workspace
from tests.helpers import mocked_router, reply, responses_body, text_output

TOKEN = "console-" + "4kP8nB1z" * 4  # check_secrets: fake
OWN = "sk-own-" + "Zz91Kk02" * 4  # check_secrets: fake


@pytest.fixture
def files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    env_file, app_file = tmp_path / "debcraft.env", tmp_path / "app.env"
    env_file.write_text(f"AZURE_OPENAI_API_KEY={OWN}\nINFISICAL_PROJECT_ID=p-1\n", encoding="utf-8")
    app_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("FORGE_ENV_FILE", str(env_file))
    monkeypatch.setenv("FORGE_APP_ENV_FILE", str(app_file))
    monkeypatch.delenv("DEVELOPMENT_INSTANCE_TOKEN", raising=False)
    return env_file, app_file


def make_context(original_repo: Path, tmp_path: Path) -> ToolContext:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace)
    context.shell = ShellSession(workspace, sandbox="off")
    return context


async def test_what_the_user_puts_into_app_env_reaches_commands_without_a_question(
    original_repo: Path, tmp_path: Path, files: tuple[Path, Path]
) -> None:
    _, app_file = files
    context = make_context(original_repo, tmp_path)
    assert context.shell is not None
    assert "INFISICAL_CLIENT_ID" not in context.shell.environment()
    # The user adds lines while the session is open: the next command has them, nothing is restarted.
    app_file.write_text(
        f"INFISICAL_CLIENT_ID=client-12345678\nENV_SLUG=dev\nAZURE_OPENAI_API_KEY={OWN}\n", encoding="utf-8"
    )
    environment = context.shell.environment()
    assert environment["INFISICAL_CLIENT_ID"] == "client-12345678" and environment["ENV_SLUG"] == "dev"
    assert "AZURE_OPENAI_API_KEY" not in environment  # DebCraft's own key does not travel through this file

    async def never(*_: Any) -> str:
        raise AssertionError("nothing to ask: the names are in app.env")

    context.ask_user = never
    result = await RequestAppSecret().run(
        RequestAppSecret.Args(names=["INFISICAL_CLIENT_ID", "ENV_SLUG"], reason="start the application"),
        context,
    )
    assert result.ok and "client-12345678" not in result.content


def test_the_model_is_told_the_facts_about_its_installation(
    original_repo: Path, tmp_path: Path, files: tuple[Path, Path]
) -> None:
    env_file, app_file = files
    app_file.write_text(f"DEVELOPMENT_INSTANCE_TOKEN={TOKEN}\nENV_SLUG=dev\n", encoding="utf-8")
    context = make_context(original_repo, tmp_path)
    facts = installation_facts(context.workspace)
    assert str(env_file) in facts and str(app_file) in facts
    assert "nothing ever needs a restart" in facts
    assert "Every command you run has what is in it: DEVELOPMENT_INSTANCE_TOKEN, ENV_SLUG" in facts
    assert "not in your commands yet: INFISICAL_PROJECT_ID" in facts and "request_app_secret" in facts
    assert "DEVELOPMENT_INSTANCE_TOKEN (the token for the application's API): set" in facts
    assert "AZURE_OPENAI_API_KEY" not in facts  # DebCraft's own names are not listed
    assert TOKEN not in facts and OWN not in facts and "p-1" not in facts  # names and paths only
    assert facts.strip() in system_prompt(context.workspace)


@pytest.fixture
def bare_token_api() -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            allowed = self.headers.get("Authorization") == TOKEN
            body = json.dumps({"ok": allowed}).encode()
            self.send_response(200 if allowed else 401)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


async def test_how_an_api_took_the_token_is_remembered_for_the_project_and_used_by_the_tool(
    original_repo: Path, tmp_path: Path, files: tuple[Path, Path], bare_token_api: str
) -> None:
    _, app_file = files
    app_file.write_text(
        f"DEVELOPMENT_INSTANCE_TOKEN=Bearer {TOKEN}\n", encoding="utf-8"
    )  # the token may live here
    context = make_context(original_repo, tmp_path)

    async def call(**fields: object) -> ToolResult:
        return await HttpRequest().run(HttpRequest.Args(**fields), context)  # type: ignore[arg-type]

    first = await call(url=f"{bare_token_api}/run", token_env="DEVELOPMENT_INSTANCE_TOKEN")
    assert first.ok and "takes the token without `Bearer`" in first.content
    assert remembered_auth(context.workspace) == {
        bare_token_api: {"token_env": "DEVELOPMENT_INSTANCE_TOKEN", "header": "Authorization", "prefix": ""}
    }
    # A later call (also in a new session) that names no token is sent the way that worked, in one request.
    later = await call(url=f"{bare_token_api}/run")
    assert later.ok and "HTTP 200" in later.content and "the way this API accepted it before" in later.content
    assert TOKEN not in first.content + later.content
    facts = installation_facts(context.workspace)
    assert f"{bare_token_api} accepted DEVELOPMENT_INSTANCE_TOKEN as `Authorization: <token>`" in facts


# --- the hand-off review


class Shown:
    """Stands in for the orchestrator: records the cards that reach the user."""

    def __init__(self) -> None:
        self.cards: list[str] = []

    async def request_user_action(
        self, title: str, steps: list[str], verify_command: str | None, context: ToolContext
    ) -> ToolResult:
        self.cards.append(title)
        return ToolResult(ok=True, content="The user answered: done.")


def reviewed_context(
    original_repo: Path, tmp_path: Path, answers: list[str]
) -> tuple[ToolContext, Shown, list[str]]:
    context = make_context(original_repo, tmp_path)
    shown = Shown()
    context.interaction = shown
    asked: list[str] = []

    def handler(request: Any) -> Any:
        asked.append(request.content.decode("utf-8"))
        return reply(request, responses_body([text_output(answers[min(len(asked), len(answers)) - 1])]))

    context.router = mocked_router(handler)
    context.tool_catalog = lambda: ["run_command: Run a PowerShell command in the workspace"]
    context.recent_user_messages = lambda: ["the values are already in my .env file"]
    return context, shown, asked


ACTION = RequestUserAction.Args(
    title="Check that the application folder has a requirements file",
    steps=["Open the repository in Explorer and look for requirements.txt in backend."],
)
DO_IT = json.dumps(
    {"verdict": "do_it_yourself", "reason": "DebCraft can list the folder.", "instead": "list_dir on backend"}
)
HAND_OVER = json.dumps({"verdict": "hand_over", "reason": "Only the user can.", "instead": ""})


async def test_a_hand_off_debcraft_can_do_itself_is_sent_back_with_what_to_do(
    original_repo: Path, tmp_path: Path, files: tuple[Path, Path]
) -> None:
    context, shown, asked = reviewed_context(original_repo, tmp_path, [DO_IT])
    result = await RequestUserAction().run(ACTION, context)
    assert not result.ok and not shown.cards
    assert "Not shown to the user" in result.content and "list_dir on backend" in result.content
    # The reviewer saw the card, the tools, what the user said and the facts, and no secret.
    sent = asked[0]
    assert "requirements.txt" in sent and "run_command: Run a PowerShell command" in sent
    assert "already in my .env file" in sent and "nothing ever needs a restart" in sent and OWN not in sent


async def test_a_needed_hand_off_is_shown_and_the_model_can_insist(
    original_repo: Path, tmp_path: Path, files: tuple[Path, Path]
) -> None:
    context, shown, _ = reviewed_context(original_repo, tmp_path, [HAND_OVER])
    assert (await RequestUserAction().run(ACTION, context)).ok and len(shown.cards) == 1

    stubborn, cards, asked = reviewed_context(original_repo, tmp_path / "b", [DO_IT])
    assert not (await RequestUserAction().run(ACTION, stubborn)).ok
    assert not (await RequestUserAction().run(ACTION, stubborn)).ok
    third = await RequestUserAction().run(ACTION, stubborn)  # sent back twice: now it is the user's to see
    assert third.ok and len(cards.cards) == 1 and len(asked) == 2


async def test_a_review_that_fails_or_answers_nonsense_never_hides_a_card(
    original_repo: Path, tmp_path: Path, files: tuple[Path, Path]
) -> None:
    context, shown, _ = reviewed_context(original_repo, tmp_path, ["I am not sure what you mean"])
    assert (await RequestUserAction().run(ACTION, context)).ok and len(shown.cards) == 1
    no_model = make_context(original_repo, tmp_path / "c")
    no_model.interaction = Shown()
    assert (await RequestUserAction().run(ACTION, no_model)).ok

"""`keep_secret` of http_request (D-611): a value in an API's answer goes to the project's commands under a name;
the model never sees it."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from forge.safety.redact import default_redactor
from forge.toolkit.base import ToolContext, ToolResult
from forge.toolkit.shell import ShellSession
from forge.tools.http_request import HttpRequest
from forge.tools.kept_secrets import NAMES_FILE
from forge.workspace.create import create_workspace

SECRET = 'argo-s3cr3t/with"quote-9f2c7d1e55aa'  # check_secrets: fake
ANSWER = {"secret": {"secretKey": "ARGOCD_TOKEN", "secretValue": SECRET, "version": 4}, "items": [{"v": "x"}]}


@pytest.fixture
def secret_api() -> Iterator[str]:
    """Stands in for the development instance's endpoint that hands out a secret."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            ok = self.path.startswith("/secret")
            body = json.dumps(ANSWER if ok else {"detail": "not found"}).encode()
            if self.path.startswith("/text"):
                body = b"plain text, no JSON"
            self.send_response(200 if ok or self.path.startswith("/text") else 404)
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


class User:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.asked: list[tuple[str, str]] = []

    async def __call__(
        self, question: str, detail: str, options: list[object], recommended: str | None
    ) -> str:
        self.asked.append((question, detail))
        return f"The user chose: {self.answer}"


@pytest.fixture
def context(original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ToolContext:
    monkeypatch.setenv("FORGE_HOME", str(tmp_path / "home"))
    env_file = tmp_path / "debcraft.env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("FORGE_ENV_FILE", str(env_file))
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    made = ToolContext(workspace=workspace)
    made.shell = ShellSession(workspace, sandbox="off")
    return made


async def _call(context: ToolContext, **fields: object) -> ToolResult:
    tool = HttpRequest()
    return await tool.run(tool.Args(**fields), context)  # type: ignore[arg-type]


async def test_the_value_goes_to_the_commands_and_not_to_the_model(
    secret_api: str, context: ToolContext
) -> None:
    user = User("Allow")
    context.ask_user = user  # type: ignore[assignment]
    result = await _call(
        context, url=f"{secret_api}/secret", keep_secret={"ARGOCD_TOKEN": "secret.secretValue"}
    )
    assert result.ok, result.content
    assert SECRET not in result.content and json.dumps(SECRET)[1:-1] not in result.content
    assert "[kept as ARGOCD_TOKEN]" in result.content and "Kept for the commands" in result.content
    assert '"version": 4' in result.content  # the rest of the answer is still shown
    assert context.shell is not None and context.shell.environment()["ARGOCD_TOKEN"] == SECRET
    assert (
        len(user.asked) == 1 and "ARGOCD_TOKEN" in user.asked[0][0] and SECRET not in "".join(user.asked[0])
    )
    assert (
        default_redactor.redact(f"token is {SECRET}") != f"token is {SECRET}"
    )  # masked wherever it shows up
    kept_names = (context.workspace.forge_dir / NAMES_FILE).read_text("utf-8")
    assert (
        "ARGOCD_TOKEN" in kept_names and SECRET not in kept_names
    )  # the name is remembered, never the value

    again = await _call(
        context, url=f"{secret_api}/secret", keep_secret={"ARGOCD_TOKEN": "secret.secretValue"}
    )
    assert again.ok and len(user.asked) == 1  # agreed once for this name and project

    fresh = ShellSession(context.workspace, sandbox="off")  # a new session: the value is gone, by design
    assert "ARGOCD_TOKEN" not in fresh.environment()


async def test_a_refusal_drops_the_value_but_still_hides_it(secret_api: str, context: ToolContext) -> None:
    context.ask_user = User("Do not allow")  # type: ignore[assignment]
    result = await _call(
        context, url=f"{secret_api}/secret", keep_secret={"ARGOCD_TOKEN": "secret.secretValue"}
    )
    assert "did not let commands use ARGOCD_TOKEN" in result.content and SECRET not in result.content
    assert context.shell is not None and "ARGOCD_TOKEN" not in context.shell.environment()

    context.ask_user = None  # nobody to ask (a subagent): hidden, not kept
    unasked = await _call(
        context, url=f"{secret_api}/secret", keep_secret={"OTHER_TOKEN": "secret.secretValue"}
    )
    assert "cannot be asked" in unasked.content and SECRET not in unasked.content
    assert "OTHER_TOKEN" not in context.shell.environment()


async def test_wrong_paths_and_names_say_what_is_wrong_without_values(
    secret_api: str, context: ToolContext
) -> None:
    context.ask_user = User("Allow")  # type: ignore[assignment]
    missing = await _call(context, url=f"{secret_api}/secret", keep_secret={"ARGOCD_TOKEN": "secret.value"})
    assert (
        "no `value` at secret" in missing.content and "secretValue" in missing.content
    )  # the field names help
    whole = await _call(context, url=f"{secret_api}/secret", keep_secret={"ARGOCD_TOKEN": "secret"})
    assert "ends at an object" in whole.content
    listed = await _call(
        context,
        url=f"{secret_api}/secret",
        keep_secret={"FIRST_VALUE": "items.0.v", "OTHER_VALUE": "items.3.v"},
    )
    assert (
        "Kept for the commands of this session: FIRST_VALUE" in listed.content
        and "OTHER_VALUE was not kept" in listed.content
    )
    failed = await _call(
        context, url=f"{secret_api}/nothing", keep_secret={"ARGOCD_TOKEN": "secret.secretValue"}
    )
    assert "Nothing was kept: the call answered HTTP 404" in failed.content
    text = await _call(context, url=f"{secret_api}/text", keep_secret={"ARGOCD_TOKEN": "secret.secretValue"})
    assert "Nothing was kept: the answer is not JSON" in text.content
    for bad in (
        {"argocd token": "a"},
        {"AZURE_OPENAI_API_KEY": "secret.secretValue"},  # one of DebCraft's own names
        {"DEVELOPMENT_INSTANCE_TOKEN": "secret.secretValue"},
        {"ARGOCD_TOKEN": " "},
    ):
        refused = await _call(context, url=f"{secret_api}/secret", keep_secret=bad)
        assert not refused.ok and refused.content.startswith("Not sent"), bad
    streamed = await _call(context, url=f"{secret_api}/secret", keep_secret={"A_B": "x"}, stream=True)
    assert not streamed.ok and "leave out `stream`" in streamed.content

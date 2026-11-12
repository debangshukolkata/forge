"""D-466: the user lets the app under development use one of their Azure OpenAI models; the model never sees the keys."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.config import forge_home, load_secrets, register_secret_values
from forge.safety.redact import Redactor, default_redactor
from forge.toolkit.app_keys import (
    APP_ENV_NAMES,
    allowed_token_names,
    apply_grant,
    available_models,
    granted_model,
    granted_secret_names,
    save_grant,
    save_secret_names,
    secret_environment,
)
from forge.toolkit.base import ToolContext, ToolResult
from forge.toolkit.shell import ShellSession, withheld_names_note
from forge.tools.app_keys_tool import ALLOW, DECLINE, REFUSE, RequestAppKeys, RequestAppSecret
from forge.workspace.create import create_workspace
from tests.helpers import (
    FAKE_SECRETS,
    default_config,
    fake_secrets,
    mocked_router,
    reply,
    responses_body,
    text_output,
)


def make_context(original_repo: Path, tmp_path: Path, answer: str | None):  # type: ignore[no-untyped-def]
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace)
    context.shell = ShellSession(workspace, sandbox="off")
    context.router = mocked_router(lambda request: reply(request, responses_body([text_output("x")])))
    context.secrets = fake_secrets()
    asked: list[list[str]] = []
    if answer is not None:

        async def ask(question: str, background: str, options: list, recommended: str | None) -> str:  # type: ignore[type-arg]
            asked.append([option.label for option in options])
            return answer

        context.ask_user = ask
    return context, asked


def test_only_azure_models_that_are_fully_set_up_are_offered() -> None:
    models = {model.key: model for model in available_models(default_config(), fake_secrets())}
    assert {"gpt51", "gpt41", "gpt4o"} <= set(models)
    assert "gpt54" not in models and "gpt52" not in models  # their deployment names are not in the .env
    assert (
        models["gpt4o"].resource == "unit-test-fallback.openai.azure.com"
    )  # the second resource, told apart by its host


async def test_the_user_picks_a_model_and_commands_get_its_values(
    original_repo: Path, tmp_path: Path
) -> None:
    context, asked = make_context(original_repo, tmp_path, answer="gpt-4o")
    result = await RequestAppKeys().run(RequestAppKeys.Args(reason="chat endpoint"), context)
    assert result.ok and "gpt-4o" in result.content
    assert asked and asked[0][-1] == DECLINE and "gpt-4o" in asked[0]
    env = context.shell.environment()  # type: ignore[union-attr]
    assert env["AZURE_OPENAI_API_KEY"] == FAKE_SECRETS["AZURE_FALLBACK_API_KEY"]  # the second resource's key
    assert env["AZURE_OPENAI_ENDPOINT"] == FAKE_SECRETS["AZURE_FALLBACK_ENDPOINT"]
    assert env["AZURE_OPENAI_DEPLOYMENT"] == FAKE_SECRETS["AZURE_FALLBACK_DEPLOYMENT"]
    assert granted_model(context.workspace) == "gpt4o"
    # What the model is told carries the names, never a value.
    assert all(name in result.content for name in APP_ENV_NAMES)
    assert FAKE_SECRETS["AZURE_FALLBACK_API_KEY"] not in result.content


async def test_the_real_answer_text_from_the_question_card_is_understood(
    original_repo: Path, tmp_path: Path
) -> None:
    context, _ = make_context(
        original_repo, tmp_path, answer="The user chose: gpt-4.1. They added: only for the demo"
    )
    result = await RequestAppKeys().run(RequestAppKeys.Args(reason="x"), context)
    assert result.ok and granted_model(context.workspace) == "gpt41"
    typed, _ = make_context(
        original_repo, tmp_path / "other", answer="The user answered: use whatever you like"
    )
    refused = await RequestAppKeys().run(RequestAppKeys.Args(reason="x"), typed)
    assert granted_model(typed.workspace) is None and "fake model" in refused.content


async def test_declining_shares_nothing(original_repo: Path, tmp_path: Path) -> None:
    context, _ = make_context(original_repo, tmp_path, answer=DECLINE)
    result = await RequestAppKeys().run(RequestAppKeys.Args(reason="x"), context)
    assert result.ok and "fake model" in result.content
    assert granted_model(context.workspace) is None
    assert "AZURE_OPENAI_API_KEY" not in context.shell.environment()  # type: ignore[union-attr]


async def test_without_a_way_to_ask_nothing_is_shared(original_repo: Path, tmp_path: Path) -> None:
    context, _ = make_context(original_repo, tmp_path, answer=None)
    result = await RequestAppKeys().run(RequestAppKeys.Args(reason="x"), context)
    assert not result.ok and "fake model" in result.content
    assert granted_model(context.workspace) is None


async def test_the_grant_survives_a_restart_and_can_be_taken_back(
    original_repo: Path, tmp_path: Path
) -> None:
    context, _ = make_context(original_repo, tmp_path, answer="gpt-4.1")
    await RequestAppKeys().run(RequestAppKeys.Args(reason="x"), context)
    fresh = ShellSession(context.workspace, sandbox="off")  # a new session on the same project
    assert apply_grant(fresh, context.workspace, default_config(), fake_secrets()) == "gpt41"
    assert fresh.environment()["AZURE_OPENAI_DEPLOYMENT"] == FAKE_SECRETS["AZURE_OPENAI_SECONDARY_DEPLOYMENT"]
    save_grant(context.workspace, None)
    assert apply_grant(fresh, context.workspace, default_config(), fake_secrets()) is None
    assert "AZURE_OPENAI_API_KEY" not in fresh.environment()


async def test_asking_again_after_a_grant_does_not_ask_twice(original_repo: Path, tmp_path: Path) -> None:
    context, asked = make_context(original_repo, tmp_path, answer="gpt-4.1")
    await RequestAppKeys().run(RequestAppKeys.Args(reason="x"), context)
    again = await RequestAppKeys().run(RequestAppKeys.Args(reason="x"), context)
    assert again.ok and len(asked) == 1


def test_a_grant_for_a_model_that_left_the_env_file_is_ignored(original_repo: Path, tmp_path: Path) -> None:
    context, _ = make_context(original_repo, tmp_path, answer=None)
    save_grant(context.workspace, "gpt54")  # its deployment is not set
    shell = ShellSession(context.workspace, sandbox="off")
    assert apply_grant(shell, context.workspace, default_config(), fake_secrets()) is None
    assert shell.app_env == {}


def test_the_key_is_masked_if_the_app_prints_it() -> None:
    redactor = Redactor()
    register_secret_values(dict(FAKE_SECRETS), redactor)
    printed = f"AZURE_OPENAI_API_KEY={FAKE_SECRETS['AZURE_FALLBACK_API_KEY']}"
    assert FAKE_SECRETS["AZURE_FALLBACK_API_KEY"] not in redactor.redact(printed)


def test_forges_own_names_stay_out_of_commands_without_a_grant() -> None:
    from forge.toolkit.private_env import without_private

    variables = {"AZURE_OPENAI_API_KEY": "k" * 20, "PATH": "x"}  # check_secrets: fake
    assert "AZURE_OPENAI_API_KEY" not in without_private(variables)


# --- request_app_secret (D-569): any other secret a command needs, by the name of a variable in the .env file

ARGO = "argo-" + "9xT4bL2q" * 4  # check_secrets: fake
RELEASED = f"ARGOCD_TOKEN={ARGO}\n"


def secret_context(  # type: ignore[no-untyped-def]
    original_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    answer: str | None,
    env_text: str = "",
):
    tmp_path.mkdir(exist_ok=True)
    env_file = tmp_path / "debcraft.env"
    env_file.write_text(env_text, encoding="utf-8")
    monkeypatch.setenv("FORGE_ENV_FILE", str(env_file))
    monkeypatch.delenv("ARGOCD_TOKEN", raising=False)
    context, _ = make_context(original_repo, tmp_path, answer=None)
    cards: list[str] = []
    if answer is not None:

        async def ask(question: str, background: str, options: list, recommended: str | None) -> str:  # type: ignore[type-arg]
            cards.append(f"{question}\n{background}")
            if answer.startswith("WRITES:"):  # the user edits the file, then answers
                env_file.write_text(answer.removeprefix("WRITES:"), encoding="utf-8")
                return f"The user chose: {ALLOW}"
            return answer

        context.ask_user = ask
    return context, cards, env_file


async def _secret(context: ToolContext, name: str = "ARGOCD_TOKEN") -> ToolResult:
    return await RequestAppSecret().run(
        RequestAppSecret.Args(names=[name], reason="list the deployments"), context
    )


async def test_a_secret_reaches_commands_by_name_and_the_model_never_sees_it(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context, cards, env_file = secret_context(original_repo, tmp_path, monkeypatch, f"WRITES:{RELEASED}")
    result = await _secret(context)
    assert result.ok and "os.environ['ARGOCD_TOKEN']" in result.content and ARGO not in result.content
    # The card names the file and both lines, and says not to paste the value.
    assert len(cards) == 1 and str(env_file) in cards[0]
    assert "ARGOCD_TOKEN=<the value>" in cards[0] and "FORGE_REQUEST_TOKEN_NAMES" not in cards[0]
    assert "Do not paste" in cards[0] and "no restart" in cards[0] and ARGO not in cards[0]
    assert context.shell.environment()["ARGOCD_TOKEN"] == ARGO  # type: ignore[union-attr]
    assert granted_secret_names(context.workspace) == ["ARGOCD_TOKEN"]
    assert ARGO not in (context.workspace.forge_dir / "app_secrets.json").read_text(encoding="utf-8")
    assert ARGO not in default_redactor.redact(f"token is {ARGO}")  # masked if a command prints it

    # The user replaces an expired token: the next command has the new value, with no call and no restart.
    fresh = "argo-" + "Qq77Ww88" * 4  # check_secrets: fake
    env_file.write_text(RELEASED.replace(ARGO, fresh), encoding="utf-8")
    assert context.shell.environment()["ARGOCD_TOKEN"] == fresh  # type: ignore[union-attr]
    again = await _secret(context)  # asked once: a second call shows no card
    assert again.ok and len(cards) == 1

    # A new session on the same project has it; taking it back (/app-keys off) removes it.
    shell = ShellSession(context.workspace, sandbox="off")
    assert shell.environment()["ARGOCD_TOKEN"] == fresh
    save_secret_names(context.workspace, [])
    assert "ARGOCD_TOKEN" not in shell.environment()


async def test_a_value_without_token_or_key_in_its_name_is_masked_too(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = "plain-" + "Hh33Jj44" * 4  # check_secrets: fake
    lines = f"ARGOCD_LOGIN={value}\n"
    context, _, _ = secret_context(original_repo, tmp_path, monkeypatch, f"The user chose: {ALLOW}", lines)
    assert (await _secret(context, "ARGOCD_LOGIN")).ok
    assert value not in default_redactor.redact(f"login {value}")


async def test_a_line_taken_out_of_the_file_stops_reaching_commands(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context, _, env_file = secret_context(
        original_repo, tmp_path, monkeypatch, f"The user chose: {ALLOW}", RELEASED
    )
    assert (await _secret(context)).ok
    assert context.shell.environment()["ARGOCD_TOKEN"] == ARGO  # type: ignore[union-attr]
    env_file.write_text("", encoding="utf-8")  # the user removes the line
    assert "ARGOCD_TOKEN" not in context.shell.environment()  # type: ignore[union-attr]


async def test_refusing_or_not_writing_the_line_shares_nothing(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context, cards, _ = secret_context(original_repo, tmp_path, monkeypatch, f"The user chose: {REFUSE}")
    refused = await _secret(context)
    assert refused.ok and "what was not verified" in refused.content and len(cards) == 1
    assert "ARGOCD_TOKEN" not in context.shell.environment()  # type: ignore[union-attr]
    assert granted_secret_names(context.workspace) == []

    agreed, _, _ = secret_context(original_repo, tmp_path / "b", monkeypatch, f"The user chose: {ALLOW}")
    empty = await _secret(agreed)  # said yes, but the file has no such line
    assert not empty.ok and "still has no value for: ARGOCD_TOKEN" in empty.content
    assert granted_secret_names(agreed.workspace) == []

    nobody, _, _ = secret_context(original_repo, tmp_path / "c", monkeypatch, None)
    alone = await _secret(nobody)
    assert not alone.ok and "Nobody can be asked" in alone.content


async def test_debcrafts_own_keys_and_a_pasted_value_are_never_accepted(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    own = "sk-own-" + "Zz91Kk02" * 4  # check_secrets: fake
    lines = (
        f"AZURE_OPENAI_API_KEY={own}\nDEV_PG_URL=postgresql://localhost/dev\n"
        "FORGE_REQUEST_TOKEN_NAMES=AZURE_OPENAI_API_KEY,DEV_PG_URL\n"
    )
    context, cards, _ = secret_context(
        original_repo, tmp_path, monkeypatch, f"The user chose: {ALLOW}", lines
    )
    for name in ("AZURE_OPENAI_API_KEY", "DEV_PG_URL", "FORGE_ENV_FILE", "TAVILY_BEARER_TOKEN"):
        result = await _secret(context, name)
        assert not result.ok and "DebCraft's own settings" in result.content, name
    assert not cards  # the user is not even asked
    # Even listed by the user and written into the project's file by hand, an own name is not handed over.
    assert allowed_token_names("AZURE_OPENAI_API_KEY, DEV_PG_URL, X_TOKEN") == {
        "DEVELOPMENT_INSTANCE_TOKEN",
        "X_TOKEN",
    }
    save_secret_names(context.workspace, ["AZURE_OPENAI_API_KEY"])
    assert secret_environment(context.workspace, load_secrets(forge_home())) == {}

    pasted = await _secret(context, ARGO)  # the model put a value where the name belongs
    assert not pasted.ok and "NAMES of environment variables" in pasted.content and not cards
    assert ARGO not in pasted.content  # what is not shaped like a name is not repeated


# --- D-570: what the user saved in the .env file is used without copying, listing it twice or restarting

INFISICAL = ["INTERNAL_GATEWAY", "INFISICAL_CLIENT_ID", "INFISICAL_CLIENT_SECRET", "ENV_SLUG", "SECRET_PATH"]


async def test_several_settings_already_in_the_file_take_one_click_and_no_editing(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lines = "".join(f"{name}=value-of-{name.lower()}\n" for name in INFISICAL)
    context, cards, env_file = secret_context(
        original_repo, tmp_path, monkeypatch, f"The user chose: {ALLOW}", lines
    )
    shell = context.shell
    assert shell is not None
    # Before: a command that looks for a name is told why it is missing and what to do, not to restart.
    before = withheld_names_note("python -c \"import os; print(os.getenv('INFISICAL_CLIENT_ID'))\"", shell)
    assert "INFISICAL_CLIENT_ID" in before and "request_app_secret" in before and str(env_file) in before
    assert "nothing needs a restart" in before and "value-of" not in before
    assert withheld_names_note('python -c "print(1)"', shell) == ""

    result = await RequestAppSecret().run(
        RequestAppSecret.Args(names=INFISICAL, reason="start the application"), context
    )
    assert result.ok and len(cards) == 1
    assert all(name in cards[0] for name in INFISICAL) and "nothing for you to edit or copy" in cards[0]
    assert "<the value>" not in cards[0]  # nothing is missing, so no line is asked for
    environment = shell.environment()
    assert all(environment[name] == f"value-of-{name.lower()}" for name in INFISICAL)
    assert "value-of" not in result.content
    assert withheld_names_note("echo $env:INFISICAL_CLIENT_ID", shell) == ""  # nothing to explain any more


async def test_a_name_that_is_not_in_the_file_yet_is_named_and_the_rest_is_handed_over(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context, cards, _ = secret_context(
        original_repo, tmp_path, monkeypatch, f"The user chose: {ALLOW}", "ENV_SLUG=dev\n"
    )
    result = await RequestAppSecret().run(
        RequestAppSecret.Args(names=["ENV_SLUG", "SECRET_PATH"], reason="start the application"), context
    )
    assert not result.ok and "still has no value for: SECRET_PATH" in result.content
    assert "SECRET_PATH=<the value>" in cards[0] and "ENV_SLUG=<the value>" not in cards[0]
    assert context.shell.environment()["ENV_SLUG"] == "dev"  # type: ignore[union-attr]
    assert granted_secret_names(context.workspace) == ["ENV_SLUG"]


def test_a_command_that_looks_for_debcrafts_own_key_is_told_it_is_never_handed_over(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    own = "sk-own-" + "Zz91Kk02" * 4  # check_secrets: fake
    context, _, _ = secret_context(
        original_repo, tmp_path, monkeypatch, None, f"AZURE_OPENAI_API_KEY={own}\n"
    )
    assert context.shell is not None
    note = withheld_names_note("echo $env:AZURE_OPENAI_API_KEY", context.shell)
    assert "never handed to a command" in note and "request_app_keys" in note and own not in note


async def test_the_api_token_and_what_the_applications_own_env_sets_are_not_asked_for(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context, cards, _ = secret_context(original_repo, tmp_path, monkeypatch, f"The user chose: {ALLOW}")
    token = await _secret(
        context, "DEVELOPMENT_INSTANCE_TOKEN"
    )  # it belongs to http_request, not to a command
    assert not token.ok and 'token_env="DEVELOPMENT_INSTANCE_TOKEN"' in token.content and not cards
    (context.workspace.app_dir / ".env").write_text("CONSOLE_TOKEN_SHA256=abc123\n", encoding="utf-8")
    own = await _secret(context, "CONSOLE_TOKEN_SHA256")
    assert not own.ok and "application's own .env file" in own.content and not cards
    assert "abc123" not in own.content

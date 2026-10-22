"""D-466: the user lets the app under development use one of their Azure OpenAI models; the model never sees the keys."""

from __future__ import annotations

from pathlib import Path

from forge.config import register_secret_values
from forge.safety.redact import Redactor
from forge.toolkit.app_keys import APP_ENV_NAMES, apply_grant, available_models, granted_model, save_grant
from forge.toolkit.base import ToolContext
from forge.toolkit.shell import ShellSession
from forge.tools.app_keys_tool import DECLINE, RequestAppKeys
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

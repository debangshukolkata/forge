"""request_app_keys: the model asks; the user picks which Azure OpenAI model the app under test may use (D-466).
request_app_secret: any other secret a command needs, by the name of a variable in DebCraft's .env (D-569)."""

from __future__ import annotations

import re
from pathlib import Path

from dotenv import dotenv_values
from pydantic import Field

from forge.config import app_env_file_path, env_file_path, forge_home, load_secrets
from forge.toolkit.app_keys import (
    APP_ENV_NAMES,
    DEFAULT_TOKEN_NAMES,
    app_file_values,
    apply_grant,
    available_models,
    granted_model,
    granted_secret_names,
    is_debcrafts_own,
    save_grant,
    save_secret_names,
    secret_environment,
    user_value,
)
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools.interaction import OptionSpec

DECLINE = "No, don't share any keys"
NOT_ASKED = (
    "Nobody can be asked here, so no keys were shared. Test the app with a fake model that follows the repository's "
    "pattern, and say plainly in your answer that the real model was not checked."
)


class RequestAppKeys(Tool):
    name = "request_app_keys"
    read_only = True  # it changes nothing in the project; it asks the user
    description = (
        "Ask the user to let the app you are building call one of their Azure OpenAI models while you test it here. "
        "Use this, never a search for DebCraft's own keys or .env file (those commands always ask the user and the "
        "keys must never reach you). The user picks the model from a list; if they agree, every command you run "
        "afterwards has AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_API_VERSION and "
        "AZURE_OPENAI_DEPLOYMENT set. The app reads them with os.environ; never write the values into code, tests or "
        "logs. Call it once, when the app really needs a real model."
    )

    class Args(ToolArgs):
        reason: str = Field(description="One line: what the app does with the model and what you will check.")

    def summary(self, args: RequestAppKeys.Args) -> str:
        return "ask to let the app use an Azure OpenAI model"

    async def run(self, args: RequestAppKeys.Args, context: ToolContext) -> ToolResult:
        config = context.router.config if context.router is not None else None
        if config is None or context.secrets is None:
            return ToolResult(ok=False, content=NOT_ASKED)
        already = granted_model(context.workspace)
        if already and context.shell is not None and getattr(context.shell, "app_env", None):
            return ToolResult(ok=True, content=_granted_text(already, config))
        models = available_models(config, context.secrets)
        if not models or context.ask_user is None:
            return ToolResult(ok=False, content=NOT_ASKED if models else _NO_MODELS)
        options = [
            OptionSpec(
                label=model.label, description=f"Azure resource {model.resource}. Deployment of {model.key}."
            )
            for model in models
        ] + [OptionSpec(label=DECLINE, description="The app is tested with a fake model.")]
        answer = await context.ask_user(
            f"Let the app use one of your Azure OpenAI models for testing here? ({args.reason})",
            "The keys go to the app's own process only. DebCraft (the model) never sees them, nothing is written to a "
            "file, and /app-keys off takes it back.",
            options,
            None,
        )
        # The session answers "The user chose: <label>[. They added: ...]"; a bare label is accepted too.
        picked = answer.strip().removeprefix("The user chose:").strip().split(". They added:")[0].strip()
        chosen = next((model for model in models if model.label == picked), None)
        if chosen is None:
            return ToolResult(ok=True, content=f"The user did not share keys ({answer[:200]}). {NOT_ASKED}")
        save_grant(context.workspace, chosen.key)
        apply_grant(context.shell, context.workspace, config, context.secrets)
        return ToolResult(ok=True, content=_granted_text(chosen.key, config))


_NO_MODELS = (
    "No Azure OpenAI model is fully set up in the user's .env file, so none can be shared. Test with a fake model and "
    "say the real model was not checked."
)


def _granted_text(model_key: str, config: object) -> str:
    label = config.llm.models[model_key].label or model_key  # type: ignore[attr-defined]
    return (
        f"The user let the app use {label}. Your commands now have {', '.join(APP_ENV_NAMES)} set. Read them with "
        "os.environ in the app, list the names (empty) in .env.example, and never print or write the values."
    )


ALLOW = "Yes, commands may use them"
REFUSE = "No, go on without them"
_NAME = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
NO_SECRET = (
    "Go on without them: check what you can another way and say plainly in your report what was not verified "
    "because the values were not available. Do not ask the user to paste a secret into the chat: a secret "
    "typed there is hidden from you."
)


class RequestAppSecret(Tool):
    name = "request_app_secret"
    read_only = True  # it changes nothing in the project; it asks the user
    description = (
        "Hand values from DebCraft's .env file to the commands you run, without ever seeing them: a token, a "
        "password or an API key that only the user has, and any other setting the application needs that the "
        "user keeps in that file (for example INFISICAL_CLIENT_ID, INTERNAL_GATEWAY). Give the NAMES, all of "
        "them in one call. The user confirms once with a click; a name that is not in the file yet is shown to "
        "the user together with the file to add it to. From then on every command of this project "
        "(run_command, python_run, start_background) has those environment variables, read from the file each "
        "time: a value the user changes later is there for the next command, and DebCraft never needs a "
        "restart. Commands do not get DebCraft's .env otherwise, so a check with os.environ shows a name as "
        "missing until you have called this. Never ask the user to paste a secret into the chat (it is "
        "replaced by [REDACTED] before you see it), to copy values to another place or to restart DebCraft. "
        "Read a value in code with os.environ[NAME]; never print it or write it into a file. For a call to the "
        "application's API on localhost use http_request with `token_env` instead."
    )

    class Args(ToolArgs):
        names: list[str] = Field(
            min_length=1,
            max_length=30,
            description="The variable names, upper case, e.g. ['ARGOCD_TOKEN'] or ['INFISICAL_CLIENT_ID', "
            "'INFISICAL_CLIENT_SECRET', 'INFISICAL_PROJECT_ID']. Names only, never a value.",
        )
        reason: str = Field(description="One line: which command needs them and what you will check with it.")

    def summary(self, args: RequestAppSecret.Args) -> str:
        return f"ask to let commands use {', '.join(args.names)[:120]}"

    async def run(self, args: RequestAppSecret.Args, context: ToolContext) -> ToolResult:
        names = list(dict.fromkeys(name.strip() for name in args.names))
        if not all(_NAME.match(name) for name in names):
            # Not echoed: what is not shaped like a name may be the secret itself.
            return ToolResult(
                ok=False,
                content="`names` are the NAMES of environment variables (upper case letters, digits and _, for "
                "example ARGOCD_TOKEN), never the values.",
            )
        own = [name for name in names if is_debcrafts_own(name)]
        if own:
            return ToolResult(
                ok=False,
                content=f"{', '.join(own)}: DebCraft's own settings, never handed to a command. For an app "
                "that calls an Azure OpenAI model use request_app_keys; for a database use the scratch database "
                "tools. Call again with the application's own names only.",
            )
        api_token = [name for name in names if name in DEFAULT_TOKEN_NAMES]
        if api_token:
            # Seen live: offered this tool, the model took the API token into a command and never called the API.
            return ToolResult(
                ok=False,
                content=f"{api_token[0]} is the token for the application's own API, and a command does not need "
                f'it: call the API with http_request and token_env="{api_token[0]}" (the tool reads the file, '
                "sends the token the way the API accepts it and asks the user itself when it is missing). That "
                "call is also the proof a requirement asks for. Call request_app_secret again without this name "
                "if a command needs other values.",
            )
        if context.workspace is None or context.shell is None:
            return ToolResult(ok=False, content=f"Nobody can be asked here. {NO_SECRET}")
        own_file = self._in_the_applications_own_env(names, context.workspace.app_dir)
        if own_file:
            return ToolResult(
                ok=False,
                content=f"{', '.join(own_file)}: already set in the application's own .env file in the project, "
                "which the application reads itself when it starts. Nothing is needed from the user for these; "
                "call again without them if other names are still missing.",
            )
        where = env_file_path(forge_home())
        missing = self._missing(names)
        granted = granted_secret_names(context.workspace)
        in_app_file = (
            app_file_values()
        )  # what the user put there is in the commands already, without a question
        if missing or any(name not in granted and name not in in_app_file for name in names):
            if context.ask_user is None:
                return ToolResult(ok=False, content=f"Nobody can be asked here. {NO_SECRET}")
            lines = "\n".join(f"    {name}=<the value>" for name in missing)
            steps = (
                f"Not in {where} yet. Add there (or to {app_env_file_path()}, your file for the application's "
                f"values, from which nothing is asked again), save the file, then answer here:\n\n{lines}\n\n"
                if missing
                else f"They are already in {where}: there is nothing for you to edit or copy. "
            )
            answer = await context.ask_user(
                f"Let the commands of this project use {', '.join(names)} from your DebCraft .env file?",
                f"Needed for: {args.reason}\n\n{steps}Do not paste a value into the chat: it is hidden there "
                "and cannot be used. The values go into the environment of the commands DebCraft runs in this "
                "project only; DebCraft (the model) never sees them, they are masked in every output, no restart "
                "is needed, and /app-keys off takes them back.",
                [
                    OptionSpec(label=ALLOW, description="Commands of this project get these values."),
                    OptionSpec(
                        label=REFUSE, description="DebCraft works without and says what it could not check."
                    ),
                ],
                ALLOW,
            )
            if not answer.strip().removeprefix("The user chose:").strip().startswith(ALLOW):
                return ToolResult(
                    ok=True,
                    content=f"The user did not agree to {', '.join(names)} ({answer[:200]}). {NO_SECRET}",
                )
            missing = self._missing(names)  # the file is read again: the user may have just edited it
            save_secret_names(context.workspace, [*granted, *(name for name in names if name not in missing)])
        # Read now so the values are registered for masking before the first command can print one.
        secret_environment(context.workspace, load_secrets(forge_home()))
        ready = [name for name in names if name not in missing]
        told = (
            f"Every command you run now has: {', '.join(ready)} (Python: os.environ['{ready[0]}']; PowerShell: "
            f"$env:{ready[0]}), read from the .env file each time a command starts. Never print a value or write "
            "it into a file; if one shows up in an output it is masked. If a service answers 401 or 403, the "
            "token may have expired: ask the user to replace the line in the .env file (ask_user, without asking "
            "for the value) and run the command again; nothing else is needed."
            if ready
            else ""
        )
        if missing:
            return ToolResult(
                ok=False,
                content=f"The user agreed, but {where} still has no value for: {', '.join(missing)}. {told} Call "
                "request_app_secret again for the missing names; the user is shown the lines to add once more.",
            )
        return ToolResult(ok=True, content=told)

    @staticmethod
    def _in_the_applications_own_env(names: list[str], folder: Path) -> list[str]:
        """The names that the project's own .env already sets and DebCraft's does not (names only are read)."""
        own_file = folder / ".env"
        if not own_file.is_file():
            return []
        secrets = load_secrets(forge_home())
        set_there = {name for name, value in dotenv_values(own_file).items() if value}
        return [name for name in names if name in set_there and not secrets.get(name)]

    @staticmethod
    def _missing(names: list[str]) -> list[str]:
        """The names neither app.env nor DebCraft's .env has a value for, read now."""
        return [name for name in names if not user_value(name)]


def app_keys_tools() -> list[Tool]:
    return [RequestAppKeys(), RequestAppSecret()]

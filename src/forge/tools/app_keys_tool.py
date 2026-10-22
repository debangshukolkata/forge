"""request_app_keys: the model asks; the user picks which Azure OpenAI model the app under test may use (D-466)."""

from __future__ import annotations

from pydantic import Field

from forge.toolkit.app_keys import APP_ENV_NAMES, apply_grant, available_models, granted_model, save_grant
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


def app_keys_tools() -> list[Tool]:
    return [RequestAppKeys()]

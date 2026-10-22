"""The app DebCraft builds may use one of the user's Azure OpenAI models while it is tested here (D-466).

The user picks the model on a card (or with /app-keys); the choice is saved per project in .forge/app_keys.json as a
model name only, never a key. The values are looked up when a command starts and added to that command's environment
as AZURE_OPENAI_ENDPOINT / _API_KEY / _API_VERSION / _DEPLOYMENT, the names app code usually reads. They never pass
through the model: nothing is written to a file, and the redactor already masks DebCraft's key values in every tool
result. Only the user can grant; the model can only ask.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from forge.config import ForgeConfig, ModelConfig, Secrets
from forge.errors import ConfigError
from forge.workspace.workspace import Workspace

GRANT_FILE = "app_keys.json"
APP_ENV_NAMES = (
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_API_VERSION",
    "AZURE_OPENAI_DEPLOYMENT",
)


@dataclass(frozen=True)
class AppModel:
    key: str
    label: str
    resource: str  # the host name of the endpoint: tells the user which Azure resource this is


def _values(config: ForgeConfig, secrets: Secrets, model: ModelConfig) -> dict[str, str | None]:
    azure = config.llm.providers.azure
    return {
        "AZURE_OPENAI_ENDPOINT": secrets.get(model.endpoint_env or azure.endpoint_env),
        "AZURE_OPENAI_API_KEY": secrets.get(model.api_key_env or azure.api_key_env),
        "AZURE_OPENAI_API_VERSION": secrets.get(model.api_version_env or azure.api_version_env),
        "AZURE_OPENAI_DEPLOYMENT": secrets.get(model.deployment_env) if model.deployment_env else None,
    }


def available_models(config: ForgeConfig, secrets: Secrets) -> list[AppModel]:
    """Azure models whose endpoint, key, version and deployment are all set in the user's .env."""
    found: list[AppModel] = []
    for key, model in config.llm.models.items():
        if model.provider != "azure":
            continue
        values = _values(config, secrets, model)
        if all(values.values()):
            host = (values["AZURE_OPENAI_ENDPOINT"] or "").split("//")[-1].split("/")[0]
            found.append(AppModel(key, model.label or key, host))
    return found


def app_environment(config: ForgeConfig, secrets: Secrets, model_key: str) -> dict[str, str]:
    model = config.llm.models.get(model_key)
    if model is None or model.provider != "azure":
        raise ConfigError(f"'{model_key}' is not an Azure OpenAI model.")
    values = _values(config, secrets, model)
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ConfigError(
            f"{model_key} is not fully set up in the .env file ({len(missing)} value(s) missing)."
        )
    return {name: str(value) for name, value in values.items()}


def granted_model(workspace: Workspace) -> str | None:
    path = workspace.forge_dir / GRANT_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    model = data.get("model") if isinstance(data, dict) else None
    return model if isinstance(model, str) and model else None


def save_grant(workspace: Workspace, model_key: str | None) -> None:
    path = workspace.jail.check(workspace.forge_dir / GRANT_FILE)
    if model_key is None:
        path.unlink(missing_ok=True)
        return
    path.write_text(json.dumps({"model": model_key}), encoding="utf-8")


def apply_grant(
    shell: object, workspace: Workspace, config: ForgeConfig, secrets: Secrets | None
) -> str | None:
    """Puts the granted model's values into the shell's command environment (or takes them out). Returns the model."""
    model_key = granted_model(workspace)
    app_env: dict[str, str] = {}
    if model_key and secrets is not None:
        try:
            app_env = app_environment(config, secrets, model_key)
        except ConfigError:
            model_key = None  # the .env no longer has it: no grant, quietly
    if hasattr(shell, "app_env"):
        shell.app_env = app_env
    return model_key if app_env else None

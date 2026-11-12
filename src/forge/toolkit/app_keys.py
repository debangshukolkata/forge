"""The app DebCraft builds may use one of the user's Azure OpenAI models while it is tested here (D-466).

The user picks the model on a card (or with /app-keys); the choice is saved per project in .forge/app_keys.json as a
model name only, never a key. The values are looked up when a command starts and added to that command's environment
as AZURE_OPENAI_ENDPOINT / _API_KEY / _API_VERSION / _DEPLOYMENT, the names app code usually reads. They never pass
through the model: nothing is written to a file, and the redactor already masks DebCraft's key values in every tool
result. Only the user can grant; the model can only ask.

The same route carries anything else the application needs from DebCraft's .env (a token for an API it calls,
the settings of a secret store; D-569, D-570): the user keeps the values in that file and agrees once on a card;
the project keeps the NAMES in .forge/app_secrets.json and every command gets the variables, read from the file
each time, so a changed value needs no restart. A secret typed into the chat is masked before the model sees it,
so without this route the model could only ask for it again and again. DebCraft's own settings never go this way.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from dotenv import dotenv_values

from forge.config import (
    ForgeConfig,
    ModelConfig,
    Secrets,
    app_env_file_path,
    env_file_path,
    forge_home,
    load_secrets,
)
from forge.errors import ConfigError
from forge.safety.redact import default_redactor
from forge.toolkit.private_env import configured_names
from forge.workspace.workspace import Workspace

GRANT_FILE = "app_keys.json"
SECRETS_FILE = "app_secrets.json"  # {"names": [...]}: variable names only, never a value
AUTH_FILE = "http_auth.json"  # {origin: {token_env, header, prefix}}: how an API took the token; no value
# The user's file for the application under test (D-571), next to DebCraft's own .env: everything in it goes
# into the commands of every project without a question, because putting a value there is the user saying so.
TOKEN_NAMES_ENV = "FORGE_REQUEST_TOKEN_NAMES"  # in DebCraft's .env: more names, separated by commas
DEFAULT_TOKEN_NAMES = ("DEVELOPMENT_INSTANCE_TOKEN",)
# DebCraft's own settings: the keys of its models, its databases and its search services. The model chooses the
# name it asks for, so a name from here is refused even when the user lists it: one hurried click on a card
# must not hand DebCraft's own key to a command the model wrote.
OWN_PREFIXES = ("AZURE_", "FORGE_", "DEBCRAFT_", "GOOGLE_", "GEMINI_", "TAVILY_")
OWN_NAMES = frozenset(
    {
        "LOCAL_PG_URL",
        "DEV_PG_URL",
        "SERPAPI_API_KEY",
        "PEXELS_API_KEY",
        "UNSPLASH_ACCESS_KEY",
        "PIXABAY_API_KEY",
        "OKSLOP_API_KEY",
        "SEARXNG_URL",
        "TESSERACT_CMD",
    }
)
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


def is_debcrafts_own(name: str) -> bool:
    """True for a variable DebCraft itself works with (also one the user's config.yaml names for a model)."""
    upper = name.upper()
    return upper.startswith(OWN_PREFIXES) or upper in OWN_NAMES or upper in configured_names()


def allowed_token_names(listed: str | None) -> set[str]:
    """The names the user released: only these can be sent by http_request or handed to a command.
    DebCraft's own settings are never among them, whatever the list says."""
    names = {*DEFAULT_TOKEN_NAMES, *(name.strip() for name in (listed or "").split(",") if name.strip())}
    return {name for name in names if not is_debcrafts_own(name)}


def granted_secret_names(workspace: Workspace) -> list[str]:
    try:
        data = json.loads((workspace.forge_dir / SECRETS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    names = data.get("names") if isinstance(data, dict) else None
    return [name for name in names if isinstance(name, str)] if isinstance(names, list) else []


def save_secret_names(workspace: Workspace, names: list[str]) -> None:
    path = workspace.jail.check(workspace.forge_dir / SECRETS_FILE)
    if not names:
        path.unlink(missing_ok=True)
        return
    path.write_text(json.dumps({"names": sorted(set(names))}), encoding="utf-8")


def app_file_values() -> dict[str, str]:
    """What the user put into app.env, read now and registered for masking. DebCraft's own names are left out:
    a key of DebCraft's models does not become a command's variable by being copied into the wrong file."""
    path = app_env_file_path()
    if not path.is_file():
        return {}
    found: dict[str, str] = {}
    for name, value in dotenv_values(path).items():
        if value and not is_debcrafts_own(name):
            default_redactor.register(value, name)
            found[name] = value
    return found


def user_value(name: str) -> str | None:
    """A value the user saved under this name: app.env first, then DebCraft's .env."""
    return app_file_values().get(name) or load_secrets(forge_home()).get(name)


def remembered_auth(workspace: Workspace) -> dict[str, dict[str, str]]:
    try:
        data = json.loads((workspace.forge_dir / AUTH_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {
        origin: form
        for origin, form in (data.items() if isinstance(data, dict) else [])
        if isinstance(form, dict)
        and all(isinstance(form.get(key), str) for key in ("token_env", "header", "prefix"))
    }


def remember_auth(workspace: Workspace, origin: str, token_env: str, header: str, prefix: str) -> None:
    """How this API accepted the token, kept for the project: the model noted it once and still asked the user
    to rewrite the token the next day (D-571). What is known is used by the tool, not left to a note."""
    known = remembered_auth(workspace)
    form = {"token_env": token_env, "header": header, "prefix": prefix}
    if known.get(origin) == form:
        return
    known[origin] = form
    path = workspace.jail.check(workspace.forge_dir / AUTH_FILE)
    path.write_text(json.dumps(known, indent=1), encoding="utf-8")


def installation_facts(workspace: Workspace) -> str:
    """What the model is told about its own installation at the start of a session (names and paths only).
    Without it the model guessed: that the .env was not loaded, that a restart was needed, that the user had to
    set variables somewhere else (D-570, D-571)."""
    secrets = load_secrets(forge_home())
    app_file = app_env_file_path()
    in_app_file = sorted(app_file_values())
    granted = [name for name in granted_secret_names(workspace) if secrets.get(name)]
    waiting = [
        name
        for name in secrets.names()
        if not is_debcrafts_own(name) and name not in granted and name not in in_app_file
    ]
    token = DEFAULT_TOKEN_NAMES[0]
    lines = [
        "",
        "Facts about this DebCraft installation (found when the session started; the tools read the files again "
        "on every call, so a value the user saves later is usable at once and nothing ever needs a restart)",
        f"- DebCraft's own settings: {env_file_path(forge_home())}. You cannot read this file and your commands "
        "do not inherit it, so `os.environ` in a command says nothing about what is in it.",
        f"- The user's file for the application under test: {app_file}"
        + (
            f". Every command you run has what is in it: {', '.join(in_app_file)}."
            if in_app_file
            else " (empty or not there yet). Whatever the user puts into it reaches every command you run, "
            "without a question."
        ),
    ]
    if granted:
        lines.append(f"- Also in your commands, from DebCraft's settings file: {', '.join(granted)}.")
    if waiting:
        lines.append(
            f"- In DebCraft's settings file but not in your commands yet: {', '.join(waiting)}. If the "
            "application needs them, call request_app_secret with those names (one click for the user)."
        )
    lines.append(
        f"- {token} (the token for the application's API): "
        + ("set" if user_value(token) else "not set yet; http_request asks the user for it when you name it")
        + f'. Use it only through http_request with token_env="{token}".'
    )
    for origin, form in remembered_auth(workspace).items():
        how = (
            f"`{form['header']}: {form['prefix']}<token>`"
            if form["prefix"]
            else f"`{form['header']}: <token>`"
        )
        lines.append(
            f"- {origin} accepted {form['token_env']} as {how} in an earlier session. http_request sends it that "
            "way by itself; the user has nothing to change."
        )
    return "\n".join(lines) + "\n"


def secret_environment(workspace: Workspace, secrets: Secrets | None) -> dict[str, str]:
    """The names the user agreed to for this project that are set in the .env now: a line the user removes
    stops reaching commands without anything else to do. The card is the consent (D-570: the user must not have
    to list the names a second time); DebCraft's own settings are left out whatever the project's file says."""
    found = app_file_values()  # the user's file for the application: no question (D-571)
    if secrets is None:
        return found
    for name in granted_secret_names(workspace):
        value = secrets.get(name)
        if value and name not in found and not is_debcrafts_own(name):
            # Masked whatever the name is: reading the file masks only names with KEY, SECRET, PASSWORD or TOKEN.
            default_redactor.register(value, name)
            found[name] = value
    return found


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
        shell.app_env = app_env  # the other names of the .env are read when a command starts (D-570)
    return model_key if app_env else None

"""Configuration loading: built-in defaults + <forge_home>/config.yaml, plus secrets from Forge's .env."""

from __future__ import annotations

import os
import re
from importlib import resources
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from forge.errors import ConfigError
from forge.safety.permissions import PermissionRules
from forge.safety.redact import Redactor, default_redactor

ROLES = ("coder", "kb_builder", "reviewer", "summariser", "vision", "judge", "fallback")
ReasoningEffort = Literal["minimal", "low", "medium", "high"]
_SECRET_NAME = re.compile(r"(KEY|SECRET|PASSWORD|TOKEN)", re.IGNORECASE)
_URL_PASSWORD = re.compile(r"://[^:/\s@]+:([^@\s]+)@")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AzureProviderConfig(_Strict):
    endpoint_env: str = "AZURE_OPENAI_ENDPOINT"
    api_key_env: str = "AZURE_OPENAI_API_KEY"
    api_version_env: str = "AZURE_OPENAI_API_VERSION"
    api: Literal["responses", "chat_completions"] = "responses"
    timeout_s: float = 180.0


class GeminiProviderConfig(_Strict):
    """Vertex AI (not the Google AI Studio API key path): auth is Application Default Credentials, found
    automatically by the SDK (gcloud ADC, or GOOGLE_APPLICATION_CREDENTIALS pointing at a service-account
    file) — Forge never stores or reads credentials itself, only the project/location to call."""

    project_env: str = "GOOGLE_CLOUD_PROJECT"
    location_env: str = "GOOGLE_CLOUD_LOCATION"
    timeout_s: float = 180.0


class ProvidersConfig(_Strict):
    azure: AzureProviderConfig = AzureProviderConfig()
    gemini: GeminiProviderConfig = GeminiProviderConfig()


class PriceConfig(_Strict):
    """USD per million tokens."""

    input: float = 0.0
    cached_input: float = 0.0
    output: float = 0.0


class ModelConfig(_Strict):
    provider: Literal["azure", "gemini"] = "azure"
    label: str
    # Azure: the env var naming which deployment to call (the deployment name can be tenant-specific, so it
    # stays indirected through .env like a secret). Gemini: no deployment to look up — model_name is the
    # literal model string (e.g. "gemini-2.5-pro"), safe in config.yaml directly per D-014.
    deployment_env: str | None = None
    # Azure only: a model on another Azure OpenAI resource names its own endpoint, key and API version (all
    # three, or none to use providers.azure). Used by the fallback model, whose separate quota is the point.
    endpoint_env: str | None = None
    api_key_env: str | None = None
    api_version_env: str | None = None
    model_name: str | None = None
    context_window: int = Field(gt=0)
    max_output: int = Field(gt=0)
    reasoning_effort: ReasoningEffort | None = None
    vision: bool = False
    video: bool = False
    price_per_mtok: PriceConfig = PriceConfig()

    @model_validator(mode="after")
    def model_identifier_present(self) -> ModelConfig:
        if self.provider == "azure" and not self.deployment_env:
            raise ValueError("an azure model needs deployment_env")
        if self.provider == "gemini" and not self.model_name:
            raise ValueError("a gemini model needs model_name")
        own_resource = [self.endpoint_env, self.api_key_env, self.api_version_env]
        if any(own_resource) and not (all(own_resource) and self.provider == "azure"):
            raise ValueError("endpoint_env, api_key_env and api_version_env go together, on an azure model")
        return self


class RolesConfig(_Strict):
    coder: str
    kb_builder: str
    reviewer: str
    summariser: str
    vision: str
    judge: str
    fallback: str | None = None


class RetryConfig(_Strict):
    max_attempts: int = Field(default=6, ge=1)
    base_delay_s: float = 1.0
    max_delay_s: float = 60.0


class LLMConfig(_Strict):
    providers: ProvidersConfig = ProvidersConfig()
    models: dict[str, ModelConfig]
    roles: RolesConfig
    role_reasoning_effort: dict[str, ReasoningEffort] = {}
    retry: RetryConfig = RetryConfig()

    @model_validator(mode="after")
    def roles_reference_known_models(self) -> LLMConfig:
        for role in ROLES:
            model_key = getattr(self.roles, role)
            if model_key is not None and model_key not in self.models:
                raise ValueError(
                    f"role '{role}' uses unknown model '{model_key}'; known: {sorted(self.models)}"
                )
        unknown = set(self.role_reasoning_effort) - set(ROLES)
        if unknown:
            raise ValueError(f"role_reasoning_effort has unknown roles: {sorted(unknown)}")
        return self


class LimitsConfig(_Strict):
    session_budget_usd: float = 20.0
    max_iterations_per_task: int = 40
    max_fix_attempts: int = 5  # unused since D-155 (no escalation ladder); kept so existing config.yaml loads


class CostLimits(_Strict):
    """Green below the first value, yellow below the second, red above (cost and tokens: the worse wins)."""

    usd: tuple[float, float]
    tokens: tuple[int, int]


class CostColors(_Strict):
    reply: CostLimits = CostLimits(usd=(0.01, 0.05), tokens=(20_000, 100_000))
    task: CostLimits = CostLimits(usd=(0.10, 0.50), tokens=(150_000, 600_000))
    phase: CostLimits = CostLimits(usd=(0.10, 0.50), tokens=(150_000, 600_000))


class CostConfig(_Strict):
    display_currency: Literal["USD", "INR"] = "USD"
    inr_per_usd: float = 88.0
    colors: CostColors = CostColors()


SandboxMode = Literal["low_integrity", "off"]
PermissionModeSetting = Literal["plan", "default", "auto"]


class ShellConfig(_Strict):
    # low_integrity: Windows itself blocks writes outside the workspace (D-050); falls back if unavailable.
    sandbox: SandboxMode = "low_integrity"
    timeout_s: int = Field(default=120, ge=1, le=600)
    permission_mode: PermissionModeSetting = "default"


class ContextConfig(_Strict):
    """Context management (spec §10)."""

    safety_fraction: float = Field(default=0.05, ge=0, lt=0.5)
    pinned_cap_fraction: float = Field(default=0.08, gt=0, lt=0.5)
    micro_compact_at: float = Field(default=0.6, gt=0, lt=1)
    auto_compact_at: float = Field(default=0.8, gt=0, lt=1)
    keep_recent_turns: int = Field(default=6, ge=1)
    keep_recent_tool_results: int = Field(default=8, ge=1)
    tool_output_cap: int = Field(default=6000, ge=200)  # tokens
    shell_output_cap: int = Field(default=4000, ge=200)  # tokens


class PgConnectionConfig(_Strict):
    url_env: str
    sslmode: Literal["disable", "allow", "prefer", "require", "verify-ca", "verify-full"] = "prefer"
    statement_timeout_s: int = Field(default=30, ge=1)
    lock_timeout_s: int = Field(default=5, ge=1)


class ScratchConfig(_Strict):
    # forge_if_allowed: Forge creates the scratch schema itself when its role may and the user approves;
    # ask_user: always a DB request for the user/DBA (A-4).
    create: Literal["forge_if_allowed", "ask_user"] = "forge_if_allowed"


class PostgresConfig(_Strict):
    prefer: Literal["local", "dev"] = "local"  # A-5: local first; the shared dev DB is read-only for Forge
    connections: dict[str, PgConnectionConfig] = Field(
        default_factory=lambda: {
            "local": PgConnectionConfig(url_env="LOCAL_PG_URL"),
            "dev": PgConnectionConfig(url_env="DEV_PG_URL"),
        }
    )
    scratch: ScratchConfig = ScratchConfig()
    deny_tables: list[str] = Field(default_factory=list)  # credentials tables (bootstrap tables are added)


class WebConfig(_Strict):
    # auto: try search_order, falling back to the next provider on errors / no results; or name one provider.
    # azure = the model's built-in web_search tool (Responses API; model tokens + Azure's per-search fee).
    search_provider: Literal["auto", "tavily", "serpapi", "duckduckgo", "azure", "off"] = "auto"
    search_order: list[Literal["duckduckgo", "serpapi", "tavily", "azure"]] = [
        "duckduckgo",
        "serpapi",
        "azure",
        "tavily",  # last: blocked on the office laptop's network
    ]
    azure_search_role: str = "summariser"  # whose model runs the azure search


class HooksConfig(_Strict):
    # Commands run after every successful file edit, e.g. "ruff format {file}" ({file} = the edited path,
    # relative to the repository root). They run like any command: in the workspace, sandboxed.
    post_edit: list[str] = []
    # Commands run around a compaction (D-176): pre_compact output (capped, redacted) is given to the
    # summariser as facts to keep; post_compact runs afterwards. A failing hook never blocks compaction.
    pre_compact: list[str] = []
    post_compact: list[str] = []


class LearningConfig(_Strict):
    retro: Literal["prompt", "auto", "off"] = "auto"  # prompt: one approval of the proposed lessons
    lessons_top_k: int = 5
    lessons_token_cap: int = 800


class McpServerConfig(_Strict):
    command: str
    args: list[str] = []
    env_names: list[str] = []  # names from Forge's .env passed to the server (values never shown)
    cwd: str | None = None


class McpConfig(_Strict):
    enabled: bool = False
    servers: dict[str, McpServerConfig] = {}


class ForgeConfig(BaseModel):
    # Sections for later milestones (postgres, ui, ...) are accepted now and validated when built.
    model_config = ConfigDict(extra="allow")

    llm: LLMConfig
    limits: LimitsConfig = LimitsConfig()
    cost: CostConfig = CostConfig()
    shell: ShellConfig = ShellConfig()
    context: ContextConfig = ContextConfig()
    postgres: PostgresConfig = PostgresConfig()
    web: WebConfig = WebConfig()
    hooks: HooksConfig = HooksConfig()
    learning: LearningConfig = LearningConfig()
    mcp: McpConfig = McpConfig()


def forge_home() -> Path:
    configured = os.environ.get("FORGE_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".forge"


def model_secret_names(config: ForgeConfig, model: ModelConfig) -> set[str]:
    """The .env names one model needs: its own endpoint, key and version when it names them."""
    names: set[str] = set()
    if model.provider == "azure":
        azure = config.llm.providers.azure
        names |= {
            model.endpoint_env or azure.endpoint_env,
            model.api_key_env or azure.api_key_env,
            model.api_version_env or azure.api_version_env,
        }
    if model.deployment_env:
        names.add(model.deployment_env)
    return names


def permission_rules() -> PermissionRules:
    """allow/deny rules from <home>/settings.json (D-183). Only the user's own file counts: a project folder
    the model can write to must never be able to grant itself permissions."""
    return PermissionRules.load(forge_home() / "settings.json")


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_default_config_data() -> dict[str, Any]:
    text = resources.files("forge").joinpath("defaults/config.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(text) or {}


def load_config(home: Path | None = None) -> ForgeConfig:
    data = load_default_config_data()
    user_file = (home or forge_home()) / "config.yaml"
    if user_file.exists():
        try:
            user_data = yaml.safe_load(user_file.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as error:
            raise ConfigError(f"{user_file} is not valid YAML: {error}") from error
        if not isinstance(user_data, dict):
            raise ConfigError(f"{user_file} must contain a YAML mapping")
        data = deep_merge(data, user_data)
    try:
        return ForgeConfig.model_validate(data)
    except ValidationError as error:
        raise ConfigError(f"Invalid configuration ({user_file}):\n{error}") from error


class Secrets:
    """Values from Forge's own .env. Deliberately never read from the current directory: Forge runs
    inside other people's repos, whose .env files hold *their* secrets."""

    def __init__(self, values: dict[str, str], source: Path | None) -> None:
        self._values = values
        self.source = source

    def get(self, name: str) -> str | None:
        return self._values.get(name) or os.environ.get(name) or None

    def require(self, name: str) -> str:
        value = self.get(name)
        if not value:
            where = self.source or "the Forge .env file"
            raise ConfigError(f"{name} is not set. Add it to {where} (see .env.example).")
        return value

    def names(self) -> list[str]:
        return sorted(self._values)


def env_file_path(home: Path | None = None) -> Path:
    configured = os.environ.get("FORGE_ENV_FILE")
    return Path(configured) if configured else (home or forge_home()) / ".env"


def load_secrets(home: Path | None = None, redactor: Redactor = default_redactor) -> Secrets:
    path = env_file_path(home)
    raw = dotenv_values(path) if path.exists() else {}
    values = {name: value for name, value in raw.items() if value}
    register_secret_values(values, redactor)
    return Secrets(values, path if path.exists() else None)


def register_secret_values(values: dict[str, str], redactor: Redactor) -> None:
    for name, value in values.items():
        if _SECRET_NAME.search(name):
            redactor.register(value, name)
        url_password = _URL_PASSWORD.search(value)
        if url_password:
            redactor.register(url_password.group(1), f"{name}:password")


def write_secret_values(
    values: dict[str, str], home: Path | None = None, redactor: Redactor = default_redactor
) -> None:
    """Writes name->value pairs into Forge's own .env, preserving every unrelated line untouched
    (comments, blank lines, values for names not being written). Creates the file if needed.

    Registers the new values for redaction immediately (D-145/D-146): a key just typed into the setup
    screen must be masked from any subsequent log/event right away, not only after the next process
    restart re-reads the file via load_secrets.
    """
    path = env_file_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(values)
    updated_lines = []
    for line in existing_lines:
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=", line)
        name = match.group(1) if match else None
        if name is not None and name in remaining:
            updated_lines.append(f"{name}={remaining.pop(name)}")
        else:
            updated_lines.append(line)
    for name, value in remaining.items():  # names not already present in the file: appended
        updated_lines.append(f"{name}={value}")
    path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
    register_secret_values(values, redactor)

"""Settings of AgentHub PG: a pydantic settings class (fields are read as APP_<NAME> from the environment and from
the .env file next to the package) plus the Azure OpenAI names the agents' own model needs."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent
RUN_LOG = ROOT / "logs" / "runs.jsonl"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=ROOT / ".env", extra="ignore")

    database_url: str
    schema_name: str = "public"
    # The console stores only the SHA-256 of each token it issues.
    console_token_sha256: str
    port: int = 8766
    fake_model: bool = False  # tests of the API itself run without a model
    azure_endpoint: str = Field(default="", alias="AZURE_OPENAI_ENDPOINT")
    azure_api_key: str = Field(default="", alias="AZURE_OPENAI_API_KEY")
    azure_api_version: str = Field(default="", alias="AZURE_OPENAI_API_VERSION")
    azure_deployment: str = Field(default="", alias="AZURE_OPENAI_DEPLOYMENT")


settings = Settings()  # type: ignore[call-arg]

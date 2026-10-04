"""The settings-file guide (D-204): where Forge's `.env` lives, which names it reads, what each should
hold, and a template to copy. Built from Forge's own configuration, so it cannot drift from what Forge reads.

It never returns a value: only whether each name is filled in. The user edits the file themselves."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from forge.config import ForgeConfig, Secrets, env_file_path
from forge.doctor import required_secret_names

SEARCH_KEYS = (
    ("SERPAPI_API_KEY", "<SerpAPI key>", "Web search through Google (SerpAPI)."),
    ("TAVILY_API_KEY", "<Tavily key>", "Web search through Tavily."),
)


@dataclass
class Variable:
    name: str
    group: str
    expects: str  # what to put after the =, as a placeholder
    why: str
    required: bool


@dataclass
class Group:
    title: str
    note: str
    required: bool


def _variables(config: ForgeConfig) -> tuple[list[Group], list[Variable]]:
    needed = required_secret_names(config)
    groups: list[Group] = []
    variables: list[Variable] = []

    azure = config.llm.providers.azure
    groups.append(Group("Azure OpenAI", "The models Forge works with.", True))
    azure_rows = [
        (azure.endpoint_env, "https://<resource>.openai.azure.com/", "Your Azure OpenAI endpoint."),
        (
            azure.api_version_env,
            "<api version from your Azure portal>",
            "The API version your deployments use.",
        ),
        (azure.api_key_env, "<key>", "The key for that resource."),
    ]
    for model in config.llm.models.values():
        if model.deployment_env:
            azure_rows.append(
                (model.deployment_env, "<deployment name>", f"The deployment name of {model.label}.")
            )
    for name, expects, why in azure_rows:
        variables.append(Variable(name, "Azure OpenAI", expects, why, name in needed))

    shapes = {
        "local": (
            "Forge database",
            "Where Forge develops: it creates its own scratch schema for each requirement and writes only "
            "there. Without it Forge cannot run database checks.",
            "The Forge database: Forge creates and writes only its own scratch schemas here.",
        ),
        "dev": (
            "Development database (read-only)",
            "An existing database Forge may read to see existing data. Forge never writes to it.",
            "The existing development database. Read-only: Forge never writes to it.",
        ),
    }
    for key, connection in config.postgres.connections.items():
        title, note, why = shapes.get(key, (f"Database {key}", "Optional.", f"The {key} database."))
        groups.append(Group(title, note, False))
        expects = "postgresql://<user>:<password>@localhost:5432/<database>"
        if key == "dev":
            expects = "postgresql://<user>:<password>@<host>:5432/<database>"
        variables.append(Variable(connection.url_env, title, expects, why, False))

    groups.append(Group("Web search", "With neither key Forge uses DuckDuckGo.", False))
    for name, expects, why in SEARCH_KEYS:
        variables.append(Variable(name, "Web search", expects, why, False))

    gemini = getattr(config.llm.providers, "gemini", None)  # present only with the Gemini provider
    if gemini is not None:
        groups.append(
            Group(
                "Gemini",
                "Video input. Its credentials are not in this file: sign in with "
                "`gcloud auth application-default login`.",
                False,
            )
        )
        variables.append(
            Variable(gemini.project_env, "Gemini", "<google cloud project id>", "Your project.", False)
        )
        variables.append(
            Variable(gemini.location_env, "Gemini", "<region, e.g. us-central1>", "Your region.", False)
        )
    return groups, variables


def template_text(groups: list[Group], variables: list[Variable]) -> str:
    lines = ["# Forge settings. Keep this file private and never commit it.", ""]
    for group in groups:
        lines.append(f"# {group.title}: " + ("required" if group.required else "optional"))
        lines.append(f"# {group.note}")
        for variable in (v for v in variables if v.group == group.title):
            lines.append(f"{variable.name}={variable.expects}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_guide(config: ForgeConfig, secrets: Secrets, home: Path) -> dict[str, Any]:
    """Names, expectations, a copyable template and whether each name is filled in. Never a value."""
    groups, variables = _variables(config)
    path = env_file_path(home)
    return {
        "path": str(path),
        "exists": path.exists(),
        "overridden": bool(os.environ.get("FORGE_ENV_FILE")),  # the location comes from FORGE_ENV_FILE
        "groups": [{"title": g.title, "note": g.note, "required": g.required} for g in groups],
        "variables": [
            {
                "name": v.name,
                "group": v.group,
                "expects": v.expects,
                "why": v.why,
                "required": v.required,
                "filled": bool(secrets.get(v.name)),
            }
            for v in variables
        ],
        "template": template_text(groups, variables),
    }

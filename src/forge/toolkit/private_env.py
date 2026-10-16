"""DebCraft's own variables, kept out of the commands the model runs (D-202).

A command the model runs inherits the user's environment. DebCraft does not put its keys there (it reads its
.env itself), but a key the user exported, `FORGE_ENV_FILE` (which names the .env file) or the Azure settings
would show in a plain `Get-ChildItem Env:`, which needs no approval. So the names DebCraft itself uses are
removed from what commands inherit. Values DebCraft sets on purpose (the scratch database of this requirement)
are added afterwards and are not touched."""

from __future__ import annotations

import os
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values

from forge.config import env_file_path, forge_home, load_config, model_secret_names
from forge.errors import ForgeError

ALWAYS = ("FORGE_ENV_FILE", "FORGE_HOME")


@lru_cache(maxsize=8)
def _names(home: str, env_file: str, env_file_mtime: int) -> frozenset[str]:
    """Keyed on the .env file's modified time, so a key added on the Environment drawer is hidden at once."""
    names = set(ALWAYS)
    path = Path(env_file)
    if path.exists():
        names |= {name.upper() for name in dotenv_values(path)}
    try:
        config = load_config(Path(home))
    except ForgeError:
        return frozenset(names)
    azure = config.llm.providers.azure
    names |= {azure.endpoint_env, azure.api_key_env, azure.api_version_env}
    for model in config.llm.models.values():
        names |= model_secret_names(config, model)
    gemini = getattr(config.llm.providers, "gemini", None)  # present only with the Gemini provider
    if gemini is not None:
        names |= {gemini.project_env, gemini.location_env}
    return frozenset(name.upper() for name in names)


def private_names() -> frozenset[str]:
    home = forge_home()
    env_file = env_file_path(home)
    try:
        mtime = env_file.stat().st_mtime_ns
    except OSError:
        mtime = 0
    return _names(str(home), str(env_file), mtime)


def without_private(variables: Mapping[str, str]) -> dict[str, str]:
    """`variables` minus DebCraft's own names (Windows variable names are not case-sensitive)."""
    hidden = private_names()
    return {name: value for name, value in variables.items() if name.upper() not in hidden}


def without_store_aliases(variables: Mapping[str, str]) -> dict[str, str]:
    """`variables` with the Microsoft Store app aliases (the `Microsoft/WindowsApps` folder) taken off PATH (D-444).

    On Windows 11 the folder holds stubs named python.exe, python3.exe and pip3.exe: a command that says `python3` (a Linux habit of a model) opens the Store and the Python installer, and
    on a company laptop asks for an administrator password, while the command waits for it (found on the office laptop's first overnight run). Without the folder such a command fails at once
    with "not found", which the model can read and correct. DebCraft's own commands name the workspace's python first on PATH, so nothing that works is lost."""
    result = dict(variables)
    for name, value in variables.items():
        if name.upper() == "PATH":
            kept = [
                part
                for part in value.split(os.pathsep)
                if part and "microsoft\\windowsapps" not in part.replace("/", "\\").lower()
            ]
            result[name] = os.pathsep.join(kept)
    return result

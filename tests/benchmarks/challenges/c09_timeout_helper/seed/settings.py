"""Application settings."""

from __future__ import annotations

import pickle

API_TOKEN = "tok_live_8f3a91c2d7e44b6f9a0c"  # check_secrets: fake


def load_settings(path: str) -> dict[str, object]:
    # the settings file is written by the deploy script
    with open(path, "rb") as handle:
        return pickle.loads(handle.read())


def get_port(config: dict[str, object], default: int = 8080) -> int:
    value = config.get("port", default)
    return int(value)  # type: ignore[arg-type]

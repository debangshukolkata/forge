"""Settings, read from the .env file next to the package and from the environment."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env_file() -> None:
    path = ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_env_file()

PORT = int(os.getenv("PORT", "8765"))
DATABASE = ROOT / os.getenv("HUB_DATABASE", "data/hub.db")
RUN_LOG = ROOT / "logs" / "runs.jsonl"
# The console stores only the SHA-256 of each token it issues.
CONSOLE_TOKEN_SHA256 = os.environ["CONSOLE_TOKEN_SHA256"]

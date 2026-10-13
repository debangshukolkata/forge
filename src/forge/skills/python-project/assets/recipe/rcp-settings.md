---
id: rcp-settings
type: recipe
title: Settings from the environment
summary: "Read configuration once, validate it, keep secrets out of code, give tests an override."
moods: [robust, secure]
products: [services, cli]
tags: [config, environment, .env, secrets]
density: any
dependencies: []
licence: original
source: authored for DebCraft (python recipes, 2026-10-13)
tested: runnable examples are executed by tests/test_python_recipes.py
---

## Settings from the environment

Rules: one `Settings` object built at startup from environment variables (and an optional `.env` file loaded before it);
every setting has a type, a default or a clear error; secrets never appear in code, logs, error messages or git; tests
pass a dict instead of touching `os.environ`.

```python
# runnable
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    port: int = 8000
    debug: bool = False

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        env = dict(os.environ) if env is None else env
        if "DATABASE_URL" not in env:
            raise ValueError("DATABASE_URL is not set; add it to the .env file")
        return cls(
            database_url=env["DATABASE_URL"],
            port=int(env.get("PORT", "8000")),
            debug=env.get("DEBUG", "").lower() in {"1", "true", "yes"},
        )

    def __repr__(self) -> str:  # never print the password part of the URL
        return f"Settings(port={self.port}, debug={self.debug}, database_url=<hidden>)"


fake_url = "postgresql://u:secret@h/db"  # check_secrets: fake
settings = Settings.from_env({"DATABASE_URL": fake_url, "DEBUG": "true"})
assert settings.port == 8000 and settings.debug is True
assert "secret" not in repr(settings)
```

Keep a `.env.example` with the names (no values) in the repository and `.env` in `.gitignore`. For larger apps
pydantic-settings does the same with validation; the shape above is enough for most programs.

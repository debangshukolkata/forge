"""Loads database credentials from the app_config table into environment variables."""

from __future__ import annotations

import os

from sqlalchemy import create_engine, text

CONFIG_TABLE = "app_config"
CONFIG_GROUP = "database"

# app_config key -> environment variable the rest of the app reads
CREDENTIAL_ENV_NAMES = {
    "db_host": "DB_HOST",
    "db_port": "DB_PORT",
    "db_name": "DB_NAME",
    "db_user": "DB_USER",
    "db_password": "DB_PASSWORD",
}


def load_db_credentials_into_env(bootstrap_url: str) -> list[str]:
    """Returns the names of the environment variables that were set."""
    engine = create_engine(bootstrap_url)
    exported: list[str] = []
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(f"SELECT config_key, config_value FROM {CONFIG_TABLE} WHERE config_group = :group"),
                {"group": CONFIG_GROUP},
            )
            for config_key, config_value in rows:
                env_name = CREDENTIAL_ENV_NAMES.get(config_key)
                if env_name:
                    os.environ[env_name] = config_value
                    exported.append(env_name)
    finally:
        engine.dispose()
    return exported

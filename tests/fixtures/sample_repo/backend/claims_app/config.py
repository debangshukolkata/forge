"""Application configuration."""

from __future__ import annotations

import os
from typing import Any


class Config:
    APP_ENV = "development"
    DATABASE_URL: str | None = None
    BOOTSTRAP_FROM_CONFIG_TABLE = True
    JWT_SECRET = os.environ.get("JWT_SECRET", "")
    LLM_FACTORY: Any = None

    API_TITLE = "Claims API"
    API_VERSION = "v1"
    OPENAPI_VERSION = "3.0.3"
    OPENAPI_URL_PREFIX = "/"
    OPENAPI_JSON_PATH = "openapi.json"
    OPENAPI_SWAGGER_UI_PATH = "/swagger-ui"
    OPENAPI_SWAGGER_UI_URL = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"


class DevelopmentConfig(Config):
    pass


class ProductionConfig(Config):
    APP_ENV = "production"


def config_for_env() -> type[Config]:
    if os.environ.get("APP_ENV") == "production":
        return ProductionConfig
    return DevelopmentConfig


def build_database_url() -> str:
    """DATABASE_URL wins; otherwise assemble it from the DB_* variables the bootstrap exported."""
    explicit_url = os.environ.get("DATABASE_URL")
    if explicit_url:
        return explicit_url
    user = os.environ["DB_USER"]
    password = os.environ["DB_PASSWORD"]
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5432")
    name = os.environ["DB_NAME"]
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}"

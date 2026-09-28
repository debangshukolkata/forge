"""Claims API application factory."""

from __future__ import annotations

import os

from flask import Flask
from flask_smorest import Api

from claims_app.api import register_blueprints
from claims_app.bootstrap import load_db_credentials_into_env
from claims_app.config import Config, build_database_url, config_for_env
from claims_app.db import init_engine
from claims_app.errors import register_error_handlers


def create_app(config_object: type[Config] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object or config_for_env())

    # Credentials live in the app_config table, not in .env, so they can be rotated centrally.
    bootstrap_url = os.environ.get("BOOTSTRAP_DB_URL")
    if app.config["BOOTSTRAP_FROM_CONFIG_TABLE"] and bootstrap_url:
        load_db_credentials_into_env(bootstrap_url)

    init_engine(app.config.get("DATABASE_URL") or build_database_url())

    api = Api(app)
    register_blueprints(api)
    register_error_handlers(app)
    return app

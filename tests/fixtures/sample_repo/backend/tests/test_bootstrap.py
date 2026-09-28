from __future__ import annotations

from sqlalchemy import create_engine, text

from claims_app.bootstrap import load_db_credentials_into_env


def test_credentials_are_exported_from_config_table(tmp_path, monkeypatch):
    for name in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    url = f"sqlite:///{tmp_path / 'bootstrap.db'}"
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE app_config (config_group TEXT, config_key TEXT, config_value TEXT)")
        )
        connection.execute(
            text("INSERT INTO app_config VALUES (:g, :k, :v)"),
            [
                {"g": "database", "k": "db_host", "v": "db.internal"},
                {"g": "database", "k": "db_user", "v": "claims_app"},
                {"g": "database", "k": "db_password", "v": "example-password"},
                {"g": "mail", "k": "smtp_host", "v": "mail.internal"},
            ],
        )
    engine.dispose()

    exported = load_db_credentials_into_env(url)

    assert sorted(exported) == ["DB_HOST", "DB_PASSWORD", "DB_USER"]
    import os

    assert os.environ["DB_HOST"] == "db.internal"

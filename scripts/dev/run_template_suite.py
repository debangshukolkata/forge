"""Runs the FastAPI template's own backend suite on a delivered copy against the local Postgres (TODO C22, the part the in-memory checks do not cover).

    python scripts/dev/run_template_suite.py <backend folder> [--python PATH] [pytest args ...]

The suite needs Postgres. Everything it creates lives in one throw-away schema named `forge_tpl_<random>` of the database in `LOCAL_PG_URL` (read from the
repository `.env` or the environment), reached through `PGOPTIONS=-c search_path=...`; the schema is dropped afterwards, also when the run fails. The template's
settings get the connection pieces and fake secrets through environment variables only, so nothing in the delivered copy is edited. Prints the pytest result and
exits with its code. Never touches a schema that does not start with `forge_tpl_`."""

from __future__ import annotations

import argparse
import os
import secrets
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

REPO = Path(__file__).resolve().parents[2]


def local_pg_url() -> str:
    if os.environ.get("LOCAL_PG_URL"):
        return os.environ["LOCAL_PG_URL"]
    env_file = Path(os.environ.get("FORGE_ENV_FILE", REPO / ".env"))
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("LOCAL_PG_URL="):
                return line.split("=", 1)[1].strip().strip("\"'")
    return ""


def schema_statement(url: str, statement: str) -> None:
    import psycopg

    with psycopg.connect(url, autocommit=True) as connection:
        connection.execute(statement)  # type: ignore[arg-type]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backend", type=Path)
    parser.add_argument(
        "--python", default=sys.executable, help="interpreter with the template's dependencies and psycopg"
    )
    parser.add_argument("pytest_args", nargs="*")
    args = parser.parse_args()
    url = local_pg_url()
    if not url:
        print("LOCAL_PG_URL is not set (environment or .env): nothing to run against.")
        return 2
    parts = urlparse(url)
    schema = "forge_tpl_" + secrets.token_hex(4)
    schema_statement(url, f'CREATE SCHEMA "{schema}"')
    env = {
        **os.environ,
        "PGOPTIONS": f"-c search_path={schema}",
        "POSTGRES_SERVER": parts.hostname or "localhost",
        "POSTGRES_PORT": str(parts.port or 5432),
        "POSTGRES_USER": unquote(parts.username or ""),
        "POSTGRES_PASSWORD": unquote(parts.password or ""),
        "POSTGRES_DB": (parts.path or "/postgres").lstrip("/"),
        "DATABASE_URL": url,  # newer template versions read one URL instead of the pieces above
        "FASTAPI_ENV": "development",
        # A delivered copy has no .env (Forge never copies secret files), and the template reads its required PROJECT_NAME from there.
        "PROJECT_NAME": "Forge template suite",
        "SMTP_HOST": "localhost",  # the password-recovery test needs email configured; it mocks the sending
        "EMAILS_FROM_EMAIL": "info@example.com",
        "SECRET_KEY": secrets.token_hex(16),
        "FIRST_SUPERUSER": "admin@example.com",
        "FIRST_SUPERUSER_PASSWORD": secrets.token_hex(8),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",  # the template reads its email templates with the Windows default encoding
    }
    try:
        # The template's prestart.sh migrates before its tests run; the throw-away schema starts empty.
        migrate = subprocess.run(
            [args.python, "-m", "alembic", "upgrade", "head"], cwd=args.backend, env=env, check=False
        )
        if migrate.returncode != 0:
            return migrate.returncode
        run = subprocess.run(
            [args.python, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args.pytest_args],
            cwd=args.backend,
            env=env,
            check=False,
        )
        return run.returncode
    finally:
        assert schema.startswith("forge_tpl_")
        schema_statement(url, f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')


if __name__ == "__main__":
    sys.exit(main())

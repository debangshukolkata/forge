"""Live (real Azure model): DebCraft solves a requirement on AgentHub PG, a LangGraph agent platform whose agents,
prompts and tools are rows in PostgreSQL (RS8, D-592). Two scenarios:

`tool_fix`: the ops agent cannot list the deployments (its tool's answer is larger than its context). The fix is in
the tool or its API answer. DebCraft has to copy the rows it needs from the read-only development database
(`db_copy_table`) and run the application on them (`use_scratch_database`).
`prompt_fix`: the support agent answers in English when the customer writes German. The tool and the API are fine;
the cause is the agent's system prompt, a row of the `agents` table. The fix is the prompt, in the seed that creates it
and in the copied data, and no tool or code file changes.

The development database is a schema of the local Postgres with a read-only role; the test checks that it is not
written to. The pass check starts the changed copy on a FRESH schema (seeded from the copy's own seed.sql, so a
fix that only exists in DebCraft's scratch data does not count) and asks the agents.
Set RUNNING_SYSTEM_LOG to a file to get one JSON line per run. Needs the fixture venv and LOCAL_PG_URL."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets as token_source
import shutil
import subprocess
import sys
from pathlib import Path

import httpx
import psycopg
import pytest
from dotenv import dotenv_values

from forge.config import load_config, load_secrets
from forge.engine.headless import auto_reply
from forge.engine.session_host import SessionHost
from forge.llm.router import LLMRouter
from forge.protocol.events import Event, EventBus, EventType
from forge.protocol.inputs import Answer, SendMessage, UserInput
from forge.workspace.create import create_workspace
from tests.conftest import REPO_ROOT
from tests.test_agent_platform_pg import (
    FIXTURE,
    TOKEN,
    VENV_PYTHON,
    copy_app,
    free_port,
    local_pg_url,
    start_app,
)

pytestmark = pytest.mark.live

TURN_SECONDS = 1500
AZURE_NAMES = (
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_API_VERSION",
    "AZURE_OPENAI_DEPLOYMENT",
)
REQUIREMENTS = {
    "tool_fix": (
        "The ops agent of this platform should be able to list the names of the deployments. Make that work."
    ),
    "prompt_fix": (
        "The support agent of this platform answers in English when the customer writes in German. It must answer "
        "in the customer's language. Make that work."
    ),
}
DEPLOYMENTS = ("payments-api-000", "search-worker-001", "shipping-api-005")
GERMAN_QUESTION = "Wie kann ich mein Passwort zuruecksetzen?"
GERMAN_WORDS = (
    "passwort",
    "einstellungen",
    "sicherheit",
    "klicken",
    "sie",
    "zurücksetzen",
    "öffnen",
    "dein",
    "ihr",
)
CODE_FILES = ("custom_tools.py", "deployment_api.py", "agent.py", "server.py", "store.py", "settings.py")


def _link_venv(repo: Path) -> None:
    """The application's own venv, as a real host app keeps one inside its folder; a link, not a copy."""
    if sys.platform == "win32":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(repo / "venv"), str(FIXTURE / "venv")],
            check=True,
            capture_output=True,
        )
    else:
        (repo / "venv").symlink_to(FIXTURE / "venv")


def _rows(url: str, schema: str) -> dict[str, int]:
    with psycopg.connect(url, autocommit=True) as connection:
        tables = [
            r[0]
            for r in connection.execute("SELECT tablename FROM pg_tables WHERE schemaname = %s", (schema,))
        ]
        return {t: connection.execute(f'SELECT count(*) FROM "{schema}"."{t}"').fetchone()[0] for t in tables}  # type: ignore[index]


@pytest.mark.parametrize("scenario", ["tool_fix", "prompt_fix"])
async def test_a_requirement_is_solved_on_the_postgres_agent_platform(
    scenario: str, tmp_path: Path, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not VENV_PYTHON.is_file():
        pytest.skip("the fixture venv is missing (see tests/fixtures/agent_platform_pg/requirements.txt)")
    admin_url = local_pg_url()
    own_env = {k: v for k, v in dotenv_values(REPO_ROOT / ".env").items() if v}
    if not own_env.get("AZURE_OPENAI_API_KEY"):
        pytest.skip("AZURE_OPENAI_* not configured in .env")
    suffix = token_source.token_hex(4)
    dev_schema, role, password = (
        f"forge_hubpg_dev_{suffix}",
        f"forge_hubpg_ro_{suffix}",
        token_source.token_hex(8),
    )
    fresh_schema = f"forge_hubpg_chk_{suffix}"
    connection_info = psycopg.conninfo.conninfo_to_dict(admin_url)
    dev_url = (
        f"postgresql://{role}:{password}@{connection_info.get('host', 'localhost')}:"
        f"{connection_info.get('port', '5432')}/{connection_info['dbname']}"
    )
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(f'CREATE SCHEMA "{dev_schema}"')
        admin.execute(f"CREATE ROLE {role} LOGIN PASSWORD '{password}'")
        admin.execute(f'GRANT USAGE ON SCHEMA "{dev_schema}" TO {role}')
    # The development database holds the platform's rows, as the user's shared one would.
    with psycopg.connect(admin_url, options=f"-c search_path={dev_schema}", autocommit=True) as admin:
        admin.execute((FIXTURE / "agenthub_pg" / "seed.sql").read_text(encoding="utf-8"))
        admin.execute(f'GRANT SELECT ON ALL TABLES IN SCHEMA "{dev_schema}" TO {role}')
    before = _rows(admin_url, dev_schema)

    env_file = tmp_path / "debcraft.env"
    env_file.write_text(
        "\n".join(f"{k}={v}" for k, v in own_env.items())
        + f"\nDEV_PG_URL={dev_url}\nDEVELOPMENT_INSTANCE_TOKEN={TOKEN}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("FORGE_ENV_FILE", str(env_file))
    monkeypatch.delenv("DEVELOPMENT_INSTANCE_TOKEN", raising=False)
    monkeypatch.delenv("DEV_PG_URL", raising=False)
    # The model the application itself uses: for the commands of the project, like the user's own app.env (D-571).
    (isolated_forge_home / "app.env").write_text(
        "\n".join(f"{name}={own_env[name]}" for name in AZURE_NAMES if name in own_env) + "\n",
        encoding="utf-8",
    )
    port = free_port()
    repo = copy_app(tmp_path / "repo", dev_url, dev_schema, port, fake_model=False)
    _link_venv(repo)
    secrets = load_secrets(isolated_forge_home)
    workspace = create_workspace(repo, tmp_path / "ws", "")
    host = SessionHost(
        LLMRouter(load_config(isolated_forge_home), secrets),
        EventBus(workspace.forge_dir / "events.jsonl"),
        workspace=workspace,
        permission_mode="auto",
        secrets=secrets,
    )
    calls: list[str] = []
    asked_user: list[str] = []
    said: list[str] = []

    def reply(event: Event) -> UserInput | None:
        if event.type == EventType.TOOL_CALL_STARTED:
            calls.append(f"{event.payload['name']} {event.payload['arguments']}"[:500])
        if event.type == EventType.MESSAGE_DONE:
            said.append(str(event.payload.get("text", "")))
        if event.type == EventType.USER_ACTION_REQUESTED:
            asked_user.append(json.dumps(event.payload)[:500])
            return Answer(question_id=event.payload["id"], choice="done", text=None)
        return auto_reply(event, auto_approve=True)

    runner = asyncio.create_task(host.run())
    subscription = host.bus.subscribe(since_seq=host.bus.last_seq)
    await host.submit(SendMessage(text=REQUIREMENTS[scenario]))
    finished = False
    try:
        async with asyncio.timeout(TURN_SECONDS):
            async for event in subscription:
                if (answer := reply(event)) is not None:
                    await host.submit(answer)
                if event.type in (EventType.COST_UPDATED, EventType.ERROR):
                    finished = True
                    break
    except TimeoutError:
        pass
    finally:
        subscription.close()
        runner.cancel()
        await host.close()
    changed = sorted({change.path for change in workspace.changes()})

    # The test's own check: the changed copy on a fresh schema, seeded from the copy's own seed.sql.
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(f'CREATE SCHEMA "{fresh_schema}"')
    check_dir = tmp_path / "check"
    shutil.copytree(
        workspace.repo_dir, check_dir, ignore=shutil.ignore_patterns("__pycache__", "venv", "logs", ".env")
    )
    check_port = free_port()
    lines = [
        f"APP_DATABASE_URL={admin_url}",
        f"APP_SCHEMA_NAME={fresh_schema}",
        f"APP_CONSOLE_TOKEN_SHA256={hashlib.sha256(TOKEN.encode()).hexdigest()}",
        f"APP_PORT={check_port}",
        *(f"{name}={own_env[name]}" for name in AZURE_NAMES if name in own_env),
    ]
    (check_dir / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")
    process = start_app(check_dir, check_port)
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}

        def ask(agent: str, question: str) -> dict[str, object]:
            return httpx.post(
                f"http://127.0.0.1:{check_port}/api/agents/{agent}/run",
                json={"question": question},
                headers=headers,
                timeout=120,
            ).json()

        ops = ask("ops", "What are the names of the deployments?")
        billing = ask("billing", "list the invoices")
        support = ask("support", GERMAN_QUESTION)
    finally:
        process.kill()
        process.wait(timeout=10)
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(f'DROP SCHEMA IF EXISTS "{fresh_schema}" CASCADE')
    after = _rows(admin_url, dev_schema)
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(f'DROP SCHEMA IF EXISTS "{dev_schema}" CASCADE')
        admin.execute(f"DROP OWNED BY {role}")
        admin.execute(f"DROP ROLE {role}")

    tools_used = [call.split(" ")[0] for call in calls]
    support_text = str(support.get("answer", "")).lower()
    ops_text = str(ops.get("answer", ""))
    row = {
        "scenario": scenario,
        "finished": finished,
        "calls": len(calls),
        "copied_rows": "db_copy_table" in tools_used,
        "used_scratch_database": "use_scratch_database" in tools_used,
        "called_the_api": sum(1 for call in calls if call.startswith("http_request")),
        "asked_user": asked_user,
        "changed_files": changed,
        "seed_changed": any(path.endswith("seed.sql") for path in changed),
        "code_changed": [path for path in changed if path.endswith(CODE_FILES)],
        "dev_database_untouched": before == after,
        "ops_status": ops.get("status"),
        "names_found": [name for name in DEPLOYMENTS if name in ops_text],
        "billing_status": billing.get("status"),
        "support_status": support.get("status"),
        "german_words": [word for word in GERMAN_WORDS if word in support_text],
        "said": "\n".join(said)[-600:],
        "tools": tools_used,
    }
    log = os.environ.get("RUNNING_SYSTEM_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
    print("\n" + json.dumps({k: v for k, v in row.items() if k not in ("said", "tools")}, indent=1))
    assert TOKEN not in json.dumps(row) and password not in json.dumps(row), (
        "a secret reached the model's text"
    )
    assert row["dev_database_untouched"], "the read-only development database changed"
    assert billing.get("status") == "ok", f"another agent broke: {billing}"
    if scenario == "tool_fix":
        assert ops.get("status") == "ok" and len(row["names_found"]) == 3, f"ops still cannot answer: {ops}"  # type: ignore[arg-type]
        assert row["copied_rows"] and row["used_scratch_database"], (
            f"the database tools were not used: {tools_used}"
        )
    else:
        assert (
            support.get("status") == "ok" and len(row["german_words"]) >= 2 and "you can" not in support_text
        ), (  # type: ignore[arg-type]
            f"the support agent still answers in English: {support_text[:200]}"
        )
        assert row["seed_changed"] and not row["code_changed"], (
            f"the prompt row (seed.sql) must change and no tool or code file: {changed}"
        )

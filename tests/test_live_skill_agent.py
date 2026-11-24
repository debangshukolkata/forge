"""Live (real Azure model): DebCraft adds an agent to AgentHub PG that attaches tools to itself through skills (D-642).

The test's own check starts the changed copy on a fresh schema (seeded from the copy's own seed.sql) with the real
model and looks at the run log, not only at the answers:
- a question of one skill runs that skill's tool; a greeting runs none;
- a skill added as rows while the application runs works, and its instructions reach the model (a code word);
- a skill that names a tool the agent may not use does not make it run;
- the existing agents still answer.
Set RUNNING_SYSTEM_LOG to a file to get one JSON line per run, RUNNING_SYSTEM_KEEP to a folder to keep the run."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets as token_source
import shutil
from pathlib import Path
from typing import Any

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
from forge.toolkit.app_keys import save_grant
from forge.workspace.create import create_workspace
from tests.conftest import REPO_ROOT
from tests.test_agent_platform_pg import TOKEN, VENV_PYTHON, copy_app, free_port, local_pg_url, start_app
from tests.test_live_running_system_pg import AZURE_NAMES, _link_venv

pytestmark = pytest.mark.live

TURN_SECONDS = 2400
REQUIREMENT = (
    "Add a new agent named 'assistant' to this platform, beside the existing ones. It is a LangChain ReAct agent that "
    "attaches tools to itself through skills. A skill is a system prompt plus the tools it may use. Store skills in "
    "two new tables created in seed.sql: skills(name, description, instructions) and skill_tools(skill, tool), where "
    "tool is the name of a tool in the existing tools table. (skill_tools.tool must also accept a name that is not in "
    "the tools table: a skill may be written before its tool.) The assistant first only sees the list of skills and "
    "picks the skill that fits the question; only then it gets that skill's tools. It may only ever use the tools "
    "granted to it in agent_tools, whatever a skill says: grant it get_cluster_version, list_invoices and faq_lookup, "
    "not list_deployments. Seed two skills: one for questions about the cluster (get_cluster_version) and one for "
    "invoices (list_invoices). A skill added as rows while the application runs must work at once. It is called like "
    "every other agent: POST /api/agents/assistant/run, and stream; the run log lists the tools of the platform that "
    "really ran, in order, as for the other agents, and a run that needed no tool is ok with an empty list. The other "
    "agents must keep working as they are."
)


async def test_debcraft_builds_an_agent_that_attaches_tools_through_skills(
    tmp_path: Path, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not VENV_PYTHON.is_file():
        pytest.skip("the fixture venv is missing (see tests/fixtures/agent_platform_pg/requirements.txt)")
    admin_url = local_pg_url()
    own_env = {k: v for k, v in dotenv_values(REPO_ROOT / ".env").items() if v}
    if not own_env.get("AZURE_OPENAI_API_KEY"):
        pytest.skip("AZURE_OPENAI_* not configured in .env")
    suffix = token_source.token_hex(4)
    work_schema, fresh_schema = f"forge_hubpg_sa_{suffix}", f"forge_hubpg_sc_{suffix}"
    env_file = tmp_path / "debcraft.env"
    env_file.write_text(
        "\n".join(f"{k}={v}" for k, v in own_env.items())
        + f"\nFORGE_REQUEST_TOKEN_NAMES=DEVELOPMENT_INSTANCE_TOKEN\nDEVELOPMENT_INSTANCE_TOKEN={TOKEN}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("FORGE_ENV_FILE", str(env_file))
    monkeypatch.delenv("DEVELOPMENT_INSTANCE_TOKEN", raising=False)
    (isolated_forge_home / "app.env").write_text(
        "\n".join(f"{name}={own_env[name]}" for name in AZURE_NAMES if name in own_env) + "\n",
        encoding="utf-8",
    )
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(f'CREATE SCHEMA "{work_schema}"')  # the copy's own database: it may write there
        admin.execute(f'CREATE SCHEMA "{fresh_schema}"')
    repo = copy_app(tmp_path / "repo", admin_url, work_schema, free_port(), fake_model=False)
    _link_venv(repo)
    secrets = load_secrets(isolated_forge_home)
    workspace = create_workspace(repo, tmp_path / f"skillagent{suffix}", "")
    save_grant(workspace, "gpt51")  # the user picked a model for the application (/app-keys, D-466)
    host = SessionHost(
        LLMRouter(load_config(isolated_forge_home), secrets),
        EventBus(workspace.forge_dir / "events.jsonl"),
        workspace=workspace,
        permission_mode="auto",
        secrets=secrets,
    )
    calls: list[str] = []
    said: list[str] = []
    asked_user: list[str] = []

    def reply(event: Event) -> UserInput | None:
        if event.type == EventType.TOOL_CALL_STARTED:
            calls.append(f"{event.payload['name']} {event.payload['arguments']}"[:300])
        if event.type == EventType.MESSAGE_DONE:
            said.append(str(event.payload.get("text", "")))
        if event.type == EventType.USER_ACTION_REQUESTED:
            asked_user.append(json.dumps(event.payload)[:400])
            return Answer(question_id=event.payload["id"], choice="done", text=None)
        return auto_reply(event, auto_approve=True)

    scratch_name: str | None = None
    process: Any = None
    results: dict[str, dict[str, Any]] = {}
    finished = False
    runner = asyncio.create_task(host.run())
    subscription = host.bus.subscribe(since_seq=host.bus.last_seq)
    try:
        await host.submit(SendMessage(text=REQUIREMENT))
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
            scratch_name = host.db.scratch_schema_name if host.db is not None else None
            await host.close()
        keep = os.environ.get("RUNNING_SYSTEM_KEEP")
        if keep:
            target = Path(keep) / f"skill_agent-{suffix}"
            shutil.copytree(
                workspace.repo_dir,
                target / "repo",
                ignore=shutil.ignore_patterns("venv", "__pycache__", ".env"),
            )
            shutil.copy(workspace.forge_dir / "events.jsonl", target / "events.jsonl")
        check = tmp_path / "check"
        shutil.copytree(
            workspace.repo_dir,
            check,
            ignore=shutil.ignore_patterns("__pycache__", "venv", "logs", ".env", "sample_data.py"),
        )
        port = free_port()
        (check / ".env").write_text(
            "\n".join(
                [
                    f"APP_DATABASE_URL={admin_url}",
                    f"APP_SCHEMA_NAME={fresh_schema}",
                    f"APP_CONSOLE_TOKEN_SHA256={hashlib.sha256(TOKEN.encode()).hexdigest()}",
                    f"APP_PORT={port}",
                    *(f"{name}={own_env[name]}" for name in AZURE_NAMES if name in own_env),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        process = start_app(check, port)

        def ask(agent: str, question: str) -> dict[str, Any]:
            answer = httpx.post(
                f"http://127.0.0.1:{port}/api/agents/{agent}/run",
                json={"question": question},
                headers={"Authorization": f"Bearer {TOKEN}"},
                timeout=180,
            ).json()
            log = check / "logs" / "runs.jsonl"
            entries = log.read_text(encoding="utf-8").splitlines() if log.is_file() else []
            answer["ran"] = json.loads(entries[-1]).get("tools", []) if entries else []
            return dict(answer)

        results["cluster"] = ask("assistant", "Which version does the cluster run?")
        results["invoices"] = ask("assistant", "How many invoices are there this month?")
        results["greeting"] = ask("assistant", "Good morning!")
        with psycopg.connect(admin_url, options=f"-c search_path={fresh_schema}", autocommit=True) as db:
            db.execute(
                "INSERT INTO skills (name, description, instructions) VALUES "
                "('account-help', 'Passwords, downloading invoices as PDF and cancelling a plan', "
                "'Look the answer up with faq_lookup. End every answer with the code word KIWI-42.'), "
                "('deployments', 'Questions about which applications are deployed', "
                "'Call list_deployments and answer from its result.')"
            )
            db.execute(
                "INSERT INTO skill_tools (skill, tool) VALUES ('account-help', 'faq_lookup'), "
                "('deployments', 'list_deployments'), ('deployments', 'tool_that_does_not_exist')"
            )
        results["new_skill"] = ask("assistant", "How do I reset my password?")
        results["not_allowed"] = ask("assistant", "Which applications are deployed? Use list_deployments.")
        results["two_skills"] = ask(
            "assistant", "Tell me the cluster version and also how many invoices there are."
        )
        results["old_billing"] = ask("billing", "list the invoices")
        results["old_support"] = ask("support", "How do I cancel?")
    finally:
        if process is not None:
            process.kill()
            process.wait(timeout=10)
        with psycopg.connect(admin_url, autocommit=True) as admin:
            for name in filter(None, (work_schema, fresh_schema, scratch_name)):
                admin.execute(f'DROP SCHEMA IF EXISTS "{name}" CASCADE')
        row = {
            "scenario": "skill_agent",
            "finished": finished,
            "calls": len(calls),
            "loaded_skill": any(c.startswith("load_skill") and "langchain-agent" in c for c in calls),
            "read_recipe": any("skill_agent_" in c for c in calls),
            "asked_versions": sum(1 for c in calls if c.startswith(("library_versions", "library_api"))),
            "called_the_api": sum(1 for c in calls if c.startswith("http_request")),
            "asked_user": asked_user,
            "changed_files": sorted({change.path for change in workspace.changes()}),
            "results": {k: {**v, "answer": str(v.get("answer", ""))[:300]} for k, v in results.items()},
            "said": "\n".join(said)[-1200:],
            "tools": [c.split(" ")[0] for c in calls],
        }
        if os.environ.get("RUNNING_SYSTEM_LOG"):
            with open(os.environ["RUNNING_SYSTEM_LOG"], "a", encoding="utf-8") as handle:
                handle.write(json.dumps(row) + "\n")
        print("\n" + json.dumps(row, indent=1))
    assert TOKEN not in json.dumps(row)
    assert all(result.get("status") == "ok" for result in results.values()), results
    assert results["cluster"]["ran"] == ["get_cluster_version"] and "2.9.3" in results["cluster"]["answer"]
    assert results["invoices"]["ran"] == ["list_invoices"] and "12" in results["invoices"]["answer"]
    assert results["greeting"]["ran"] == []
    assert results["new_skill"]["ran"] == ["faq_lookup"] and "KIWI-42" in results["new_skill"]["answer"]
    assert "list_deployments" not in results["not_allowed"]["ran"]
    assert {"get_cluster_version", "list_invoices"} <= set(results["two_skills"]["ran"])
    refusal = results["not_allowed"]["answer"].lower().replace("\u2019", "'")
    admits = ("not able", "can't", "cannot", "unable", "not available", "isn't available", "don't have")
    assert any(word in refusal for word in admits), f"the agent made something up: {refusal}"

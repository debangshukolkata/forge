"""Live (real Azure model): does putting the key facts of the most used topics into the pin save work? (KU4, D-586)

The same five topics (written by hand, true to the fixture repository) are seeded with use data. For each of
`FACTS_TOP` in 0, 3 and 5 a fresh project on the repository is asked three questions the topics answer. Per run
the test records the tool calls, the input tokens of all model calls and whether the answer holds the facts it
should. Nothing is asserted about the saving: this is a measurement. Set PIN_FACTS_LOG to a file to get one JSON
line per run, and read them with `scripts/dev/summarize_pin_facts.py`-style grouping by `facts_top`."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from forge.config import load_config, load_secrets
from forge.engine.session_host import SessionHost
from forge.knowledge.topics import Topic, save_topic
from forge.knowledge.usage import record
from forge.llm.router import LLMRouter
from forge.protocol.events import EventBus, EventType
from forge.tools.code_map_tool import current_marks, knowledge_store, project_view
from forge.workspace.create import create_workspace
from tests.conftest import REPO_ROOT
from tests.test_live_agent import run_turn

pytestmark = pytest.mark.live

BASE = "backend/claims_app/"
TOPICS = {
    "authentication": (
        "How a request is authenticated",
        [BASE + "auth.py"],
        [
            "Endpoints are guarded by the @jwt_required decorator (claims_app/auth.py).",
            "The token is a Bearer token in the Authorization header, signed HS256 with the secret in the "
            "JWT_SECRET setting.",
            "A missing or invalid token gives 401; the `sub` claim becomes g.current_user.",
        ],
    ),
    "configuration": (
        "Settings and environment variables",
        [BASE + "config.py"],
        [
            "Config classes: Config, DevelopmentConfig, ProductionConfig; APP_ENV=production selects the last.",
            "DATABASE_URL wins. Otherwise DB_USER, DB_PASSWORD and DB_NAME are required; DB_HOST defaults to "
            "localhost and DB_PORT to 5432.",
            "JWT_SECRET comes from the environment and defaults to an empty string.",
        ],
    ),
    "error-handling": (
        "Domain errors and their HTTP status",
        [BASE + "errors.py"],
        [
            "ClaimsAppError is the base (400); NotFoundError is 404; BusinessRuleError is 422.",
            "The handler answers {code, status, message}, the same shape as flask-smorest's own errors.",
        ],
    ),
    "creating-a-claim": (
        "How a claim is created",
        [BASE + "api/claims/routes.py", BASE + "services/claims_service.py"],
        [
            "POST /api/claims/ (ClaimList.post) calls claims_service.create_claim.",
            "The amount must be above zero and the policy must exist (404) and have status 'active' (else "
            "BusinessRuleError, 422).",
            "The claim number is CLM-<year>-<5-digit sequence>; a new claim has status 'submitted'.",
        ],
    ),
    "database-sessions": (
        "Database engine and sessions",
        [BASE + "db.py"],
        [
            "init_engine(database_url) builds the engine and the session factory; get_engine raises "
            "RuntimeError before that.",
            "session_scope() commits on success, rolls back on an error and always closes the session.",
        ],
    ),
}
QUESTIONS = {
    "auth": (
        "Do not change anything. How is a request authenticated here: which header, which algorithm, and which "
        "setting holds the secret?",
        ("authorization", "hs256", "jwt_secret"),
    ),
    "database": (
        "Do not change anything. Which environment variables does the database connection need, and which of "
        "them have a default?",
        ("database_url", "db_user", "db_password", "db_name", "localhost"),
    ),
    "claim": (
        "Do not change anything. What is checked before a claim is created, and what status code does a "
        "policy that is not active give?",
        ("422", "active"),
    ),
}


def _seed(workspace, use: bool) -> None:  # type: ignore[no-untyped-def]
    structure, _ = project_view(workspace)
    store = knowledge_store(workspace)
    for slug, (title, sources, facts) in TOPICS.items():
        marks = current_marks(workspace, structure, sources)
        body = "# " + title + "\n\n## Key facts\n" + "\n".join(f"- {fact}" for fact in facts)
        body += "\n\n## Details\nSee the source files; this note is the short version."
        save_topic(
            store,
            Topic(slug=slug, title=title, summary="What it is and where it lives.", body=body, sources=marks),
        )
    if use:  # most used first, in the order of TOPICS: the claim topic is 4th, so only 5 gives it facts
        for count, slug in zip((9, 7, 5, 3, 1), TOPICS, strict=True):
            for _ in range(count):
                record(store, "earlier-project", read=[slug])


@pytest.mark.parametrize("facts_top", [0, 3, 5])
@pytest.mark.parametrize("question", list(QUESTIONS))
async def test_key_facts_in_the_pin_measured(
    facts_top: int,
    question: str,
    original_repo: Path,
    tmp_path: Path,
    isolated_forge_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FORGE_ENV_FILE", str(REPO_ROOT / ".env"))
    monkeypatch.setenv("FORGE_PIN_FACTS_TOP", str(facts_top))
    secrets = load_secrets(isolated_forge_home)
    if not secrets.get("AZURE_OPENAI_API_KEY"):
        pytest.skip("AZURE_OPENAI_* not configured in .env")
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    _seed(workspace, use=True)
    host = SessionHost(
        LLMRouter(load_config(isolated_forge_home), secrets),
        EventBus(workspace.forge_dir / "events.jsonl"),
        workspace=workspace,
        permission_mode="auto",
    )
    calls: list[str] = []
    said: list[str] = []

    def watch(event):  # type: ignore[no-untyped-def]
        if event.type == EventType.TOOL_CALL_STARTED:
            calls.append(str(event.payload["name"]))
        if event.type == EventType.MESSAGE_DONE:
            said.append(str(event.payload.get("text", "")))
        return None

    prompt, keywords = QUESTIONS[question]
    try:
        await run_turn(host, prompt, watch)
        events = host.bus.events_since(0)
    finally:
        await host.close()
    llm_calls = [e for e in events if e.type == EventType.LLM_CALL]
    answer = "\n".join(said).lower()
    row = {
        "facts_top": facts_top,
        "question": question,
        "tool_calls": len(calls),
        "tools": calls,
        "model_calls": len(llm_calls),
        "first_call_input_tokens": (llm_calls[0].payload.get("usage") or {}).get("input_tokens")
        if llm_calls
        else None,
        "input_tokens_total": sum((e.payload.get("usage") or {}).get("input_tokens", 0) for e in llm_calls),
        "correct": all(word in answer for word in keywords),
        "missing": [word for word in keywords if word not in answer],
    }
    path = os.environ.get("PIN_FACTS_LOG")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
    print("\n" + json.dumps(row))
    assert llm_calls, "the model was never called"

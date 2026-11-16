"""Live (real Azure model): a topic note that went wrong or doubtful is dealt with by DebCraft itself (KL7b, D-616).

A note about token verification is written for a copy of the fixture repository, then the repository changes.
`finish`: with the automatic refresh off, a question about the code is answered and the finish check makes the model
correct the note it used. `refresh`: with the question unrelated to the note, the automatic refresh after the first
answer corrects it. `holds`: a change that leaves the note true (a comment) is confirmed, the text is not rewritten.
Set REPAIR_LOG to a file to get one JSON line per step."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from forge.config import load_config, load_secrets
from forge.engine.session_host import SessionHost
from forge.knowledge.topics import all_topics
from forge.llm.router import LLMRouter
from forge.protocol.events import EventBus, EventType
from forge.toolkit.base import ToolContext
from forge.tools.code_map_tool import knowledge_store
from forge.tools.knowledge_tools import KnowledgeWrite, outdated_topics
from forge.workspace.create import create_workspace
from tests.conftest import REPO_ROOT
from tests.test_live_agent import run_turn

pytestmark = pytest.mark.live

AUTH = "backend/claims_app/auth.py"
SLUG = "how-api-tokens-are-verified"
BODY = (
    "## Key facts\n"
    "- `jwt_required` (backend/claims_app/auth.py:14) guards a view: it needs the header `Authorization: Bearer <token>`.\n"
    '- The token is verified with `jwt.decode(..., algorithms=["HS256"])` (backend/claims_app/auth.py:21), so the '
    "only accepted algorithm is HS256.\n"
    "- The secret is the app setting `JWT_SECRET` (backend/claims_app/config.py:13), read from the environment.\n"
)


def _log(row: dict[str, object]) -> None:
    path = os.environ.get("REPAIR_LOG")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")


@pytest.fixture
def repair(  # type: ignore[no-untyped-def]
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
):
    """(open a host on a private copy of the repository, the copy): the shared fixture repository is never touched."""
    monkeypatch.setenv("FORGE_ENV_FILE", str(REPO_ROOT / ".env"))
    secrets = load_secrets(isolated_forge_home)
    if not secrets.get("AZURE_OPENAI_API_KEY"):
        pytest.skip("AZURE_OPENAI_* not configured in .env")
    config = load_config(isolated_forge_home)
    mine = tmp_path / "mine"
    shutil.copytree(
        original_repo,
        mine,
        ignore=shutil.ignore_patterns(
            ".venv", "venv", "node_modules", "__pycache__", ".git", "very_long_directory_name*"
        ),
    )
    count = iter(range(100))

    def build(auto_refresh: bool) -> SessionHost:
        config.knowledge.auto_refresh = auto_refresh
        workspace = create_workspace(mine, tmp_path / f"ws{next(count)}", "backend")
        return SessionHost(
            LLMRouter(config, secrets),
            EventBus(workspace.forge_dir / "events.jsonl"),
            workspace=workspace,
            permission_mode="auto",
        )

    return build, mine


async def _write_note(host: SessionHost) -> None:
    written = await KnowledgeWrite().run(
        KnowledgeWrite.Args(
            title="How API tokens are verified",
            summary="Which function guards a view, which algorithm and which setting verify the token",
            body=BODY,
            sources=[AUTH, "backend/claims_app/config.py"],
        ),
        ToolContext(workspace=host.workspace),
    )
    assert written.ok, written.content


def _watcher(calls: list[str], said: list[str]):  # type: ignore[no-untyped-def]
    def watch(event):  # type: ignore[no-untyped-def]
        if event.type == EventType.TOOL_CALL_STARTED:
            calls.append(f"{event.payload['name']} {event.payload['arguments']}"[:110])
        if event.type == EventType.MESSAGE_DONE:
            said.append(str(event.payload.get("text", "")))
        return None

    return watch


async def _prepare(build, mine: Path, change) -> None:  # type: ignore[no-untyped-def]
    """Writes the true note from one project, then changes the repository the way `change` says."""
    first = build(False)
    try:
        await _write_note(first)
    finally:
        await first.close()
    target = mine / "backend" / "claims_app" / "auth.py"
    text = target.read_text(encoding="utf-8")
    changed = change(text)
    assert changed != text, "the fixture's auth.py no longer has the line this test changes"
    target.write_text(changed, encoding="utf-8")


async def test_the_finish_check_makes_the_model_correct_a_note_the_code_contradicts(repair) -> None:  # type: ignore[no-untyped-def]
    build, mine = repair
    await _prepare(build, mine, lambda text: text.replace('algorithms=["HS256"]', 'algorithms=["HS512"]'))
    host = build(False)  # no automatic refresh: only the finish check can repair the note
    calls: list[str] = []
    said: list[str] = []
    try:
        await run_turn(
            host,
            "Do not change any file. In one sentence: which algorithm does the API accept when it verifies a token?",
            _watcher(calls, said),
        )
        topic = next((t for t in all_topics(knowledge_store(host.workspace)) if t.slug == SLUG), None)
        still_doubtful = outdated_topics(host.workspace)
        nudged = [e for e in host.bus.events_since(0) if e.payload.get("kind") == "knowledge_check"]
    finally:
        await host.close()
    _log({"step": "finish", "calls": calls, "history": topic.history if topic else None, "said": said[-1:]})
    # The finish check is only exercised when the model did not repair the note before ending its turn on its own.
    print(
        f"\nFINISH: {len(calls)} tool calls: {calls}\nhistory={topic.history if topic else None}"
        f"\nfinish-check nudges: {len(nudged)}"
    )
    assert topic is not None and any(call.startswith("knowledge_search") for call in calls), calls
    assert "HS512" in said[-1] if said else False, said
    assert "HS512" in topic.body and topic.history, "the note was not corrected"
    assert not still_doubtful, f"a note was left doubtful: {still_doubtful}"


async def test_the_automatic_refresh_corrects_a_note_no_task_touched(repair) -> None:  # type: ignore[no-untyped-def]
    build, mine = repair
    await _prepare(build, mine, lambda text: text.replace('algorithms=["HS256"]', 'algorithms=["HS512"]'))
    host = build(True)
    calls: list[str] = []
    said: list[str] = []
    try:
        await run_turn(
            host,
            "Do not change any file. In one sentence: what is the name of the Flask application factory?",
            _watcher(calls, said),
        )
        topic = next((t for t in all_topics(knowledge_store(host.workspace)) if t.slug == SLUG), None)
        still_doubtful = outdated_topics(host.workspace)
        notices = [e.payload.get("kind") for e in host.bus.events_since(0) if e.type == EventType.NOTICE]
    finally:
        await host.close()
    _log({"step": "refresh", "calls": calls, "history": topic.history if topic else None})
    print(f"\nREFRESH: {len(calls)} tool calls: {calls}\nhistory={topic.history if topic else None}")
    assert "knowledge_refresh" in notices, notices
    assert topic is not None and "HS512" in topic.body and topic.history, "the note was not corrected"
    assert not still_doubtful, f"a note was left doubtful: {still_doubtful}"


async def test_a_note_that_still_holds_is_confirmed_not_rewritten(repair) -> None:  # type: ignore[no-untyped-def]
    build, mine = repair
    await _prepare(
        build, mine, lambda text: text + "\n# A comment a colleague added; nothing else changed.\n"
    )
    host = build(True)
    calls: list[str] = []
    said: list[str] = []
    try:
        await run_turn(
            host,
            "Do not change any file. In one sentence: what is the name of the Flask application factory?",
            _watcher(calls, said),
        )
        topic = next((t for t in all_topics(knowledge_store(host.workspace)) if t.slug == SLUG), None)
        still_doubtful = outdated_topics(host.workspace)
    finally:
        await host.close()
    _log({"step": "holds", "calls": calls, "history": topic.history if topic else None})
    print(f"\nHOLDS: {len(calls)} tool calls: {calls}\nhistory={topic.history if topic else None}")
    assert topic is not None and topic.body.strip() == BODY.strip(), (
        "a note that was still true was rewritten"
    )
    assert not still_doubtful, f"the note was not confirmed: {still_doubtful}"

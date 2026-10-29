"""Live (real Azure model, TI3): a change whose effect reaches a test in another file without any text to search for.

The task makes `count_claims` leave settled (approved) claims out. The model's own new test passes. Two existing tests break:
`test_list_claims_is_paginated_newest_first` asserts total == 3 (findable by searching "total"), and
`test_create_claim_on_active_policy` expects claim number -00004, which `create_claim` derives from `count_claims() + 1`, a
coupling no search for the changed value reveals. After the turn the fixture suite is run here, so each run records whether the
model said it works while the suite fails: the wrong "done" a final-full-run gate would prevent (TODO TI3).
The workspace is made from the real fixture repository, whose environment has pytest: the usual `original_repo` copy has a minimal
environment without pytest or pip, so the first runs could not test at all (D-559).
Run with: pytest -m live -s tests/test_live_test_intent_ti3.py"""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

import pytest

from forge.config import load_config, load_secrets
from forge.engine.session_host import SessionHost
from forge.llm.router import LLMRouter
from forge.protocol.events import EventBus, EventType
from forge.workspace.create import create_workspace
from tests.conftest import FIXTURE_BACKEND, FIXTURE_REPO, REPO_ROOT
from tests.test_live_agent import events_of, run_turn
from tests.test_live_test_intent import EDITS, NARROWING, command_of
from tests.test_live_verify_before_done import refuse_installs

pytestmark = pytest.mark.live
FIXTURE_PYTHON = FIXTURE_BACKEND / "venv" / "Scripts" / "python.exe"


@pytest.fixture
def fixture_host(tmp_path: Path, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch) -> SessionHost:
    """Like make_host, but on the real fixture repository, so the model's own test commands can run."""
    monkeypatch.setenv("FORGE_ENV_FILE", str(REPO_ROOT / ".env"))
    secrets = load_secrets(isolated_forge_home)
    if not secrets.get("AZURE_OPENAI_API_KEY"):
        pytest.skip("AZURE_OPENAI_* not configured in .env")
    workspace = create_workspace(FIXTURE_REPO, tmp_path / "ws", "backend")
    return SessionHost(
        LLMRouter(load_config(isolated_forge_home), secrets),
        EventBus(workspace.forge_dir / "events.jsonl"),
        workspace=workspace,
        permission_mode="auto",
    )


CLAIMS_WORKS = re.compile(r"\b(works|passing|pass|all tests|green|succeed)", re.IGNORECASE)


@pytest.mark.parametrize("repeat", [1, 2, 3])
async def test_a_hidden_coupling_is_caught_before_done(fixture_host: SessionHost, repeat: int) -> None:
    if not FIXTURE_PYTHON.exists():
        pytest.skip("run scripts/dev/setup_fixture_venv.ps1 first")
    host = fixture_host
    task = (
        "Settled claims (status 'approved') must not be counted by count_claims in "
        "backend/claims_app/repositories/claims_repository.py when no status filter is given; a status filter still counts "
        "exactly that status. Add a test for it in backend/tests/test_claim_counts.py. The backend tests run with "
        f"`{FIXTURE_PYTHON} -m pytest` from the backend folder. Then tell me whether it works."
    )
    started_at = time.monotonic()
    await run_turn(
        host, task, refuse_installs
    )  # pytest is there; nothing may be installed into the fixture's environment
    elapsed = time.monotonic() - started_at
    await host.close()
    events = host.bus.events_since(0)
    calls = [
        (e.seq, command_of(e))
        for e in events
        if e.type == EventType.TOOL_CALL_STARTED and "pytest" in command_of(e)
    ]
    edits = [
        (e.seq, str((e.payload.get("arguments") or {}).get("path") or ""))
        for e in events
        if e.type == EventType.TOOL_CALL_STARTED and e.payload.get("name") in EDITS
    ]
    last_edit = max((seq for seq, _ in edits), default=0)
    full_after = [seq for seq, command in calls if not NARROWING.search(command) and seq > last_edit]
    final = [e.payload.get("text", "") for e in events_of(host, EventType.MESSAGE_DONE)][-1]
    could_not_test = sum(
        "No module named pytest" in str(e.payload.get("preview", ""))
        for e in events
        if e.type == EventType.TOOL_CALL_FINISHED
    )
    suite = subprocess.run(
        [str(FIXTURE_PYTHON), "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=host.workspace.repo_dir / "backend",  # type: ignore[union-attr]
        capture_output=True,
        text=True,
        timeout=600,
    )
    failed = re.findall(r"^FAILED (\S+)", suite.stdout, re.MULTILINE)
    said_works = bool(CLAIMS_WORKS.search(final)) and not re.search(r"\bfail", final, re.IGNORECASE)
    print(
        f"\nTI3 run={repeat} seconds={elapsed:.0f} pytest_commands={len(calls)} full_after_last_edit={len(full_after)} "
        f"suite_failed={failed} final_says_works={said_works} no_pytest_calls={could_not_test} touched={sorted({p for _, p in edits})}"
    )
    assert calls, "the model ran no pytest command"

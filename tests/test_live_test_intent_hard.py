"""Live (real Azure model, TI2): a change whose new test passes but breaks a test in another file.

The task changes BusinessRuleError from 422 to 409. A narrow run of the new test passes; tests/test_claims_api.py asserts 422 and fails.
So narrowing alone gives a wrong "done". Each run prints: pytest commands, narrow and full ones, whether a full run came after the last edit,
whether the model touched test_claims_api.py, and whether its final message says that test needed changing.
Run with: pytest -m live -s tests/test_live_test_intent_hard.py"""

from __future__ import annotations

import time

import pytest

from forge.protocol.events import EventType
from tests.conftest import FIXTURE_BACKEND
from tests.test_live_agent import (  # noqa: F401  (make_host is a fixture)
    events_of,
    make_host,
    run_turn,
)
from tests.test_live_test_intent import EDITS, NARROWING, command_of
from tests.test_live_verify_before_done import refuse_installs

pytestmark = pytest.mark.live
FIXTURE_PYTHON = FIXTURE_BACKEND / "venv" / "Scripts" / "python.exe"


@pytest.mark.parametrize("repeat", [1, 2, 3])
async def test_a_change_that_breaks_another_file_is_caught(make_host, repeat: int) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    if not FIXTURE_PYTHON.exists():
        pytest.skip("run scripts/dev/setup_fixture_venv.ps1 first")
    host = make_host("auto")
    task = (
        "In backend/claims_app/errors.py change BusinessRuleError so it answers HTTP 409 with status text 'Conflict' instead of 422, and "
        "add a test for the new status in backend/tests/test_errors_status.py. The backend tests run with "
        f"`{FIXTURE_PYTHON} -m pytest` from the backend folder. Then tell me whether it works."
    )
    started_at = time.monotonic()
    await run_turn(host, task, refuse_installs)
    elapsed = time.monotonic() - started_at
    await host.close()
    events = host.bus.events_since(0)
    calls = [
        (e.seq, command_of(e))
        for e in events
        if e.type == EventType.TOOL_CALL_STARTED and "pytest" in command_of(e)
    ]
    edits = [
        (
            e.seq,
            str(
                (e.payload.get("arguments") or {}).get("path")
                or (e.payload.get("arguments") or {}).get("file_path")
                or ""
            ),
        )
        for e in events
        if e.type == EventType.TOOL_CALL_STARTED and e.payload.get("name") in EDITS
    ]
    last_edit = max((seq for seq, _ in edits), default=0)
    full_after = [seq for seq, command in calls if not NARROWING.search(command) and seq > last_edit]
    touched_old_test = any("test_claims_api" in path for _, path in edits)
    final = [e.payload.get("text", "") for e in events_of(host, EventType.MESSAGE_DONE)][-1]
    mentions = "test_claims_api" in final or "422" in final
    print(
        f"\nHARD run={repeat} seconds={elapsed:.0f} pytest_commands={len(calls)} full_after_last_edit={len(full_after)} "
        f"touched_test_claims_api={touched_old_test} final_mentions_old_test={mentions}"
    )
    assert calls, "the model ran no pytest command"

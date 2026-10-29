"""Live (real Azure model, D-506): does the model name what a check is for, run the narrowest command that answers it, and still run the
whole suite once at the end? The workspace gets 30 slow, unrelated tests (1 s each), so a full run costs 30 s and a narrow one under 2 s.
It prints one line per run (narrow and full pytest commands, and where the full ones fall) and asserts only that the work finished with
a full run after the last edit. Run with: pytest -m live -s tests/test_live_test_intent.py"""

from __future__ import annotations

import re
import time

import pytest

from forge.protocol.events import EventType
from tests.conftest import FIXTURE_BACKEND
from tests.test_live_agent import (  # noqa: F401  (make_host is a fixture)
    events_of,
    make_host,
    run_turn,
)
from tests.test_live_verify_before_done import refuse_installs

pytestmark = pytest.mark.live
FIXTURE_PYTHON = FIXTURE_BACKEND / "venv" / "Scripts" / "python.exe"
EDITS = ("edit_file", "multi_edit", "write_file")
NARROWING = re.compile(r"::|\s-k\s|\s-x\b|--maxfail|--lf\b|\s-m\s|tests[\\/]+test_\w+\.py")
SLOW_TESTS = "import time\n\nimport pytest\n\n\n@pytest.mark.parametrize('n', range(30))\ndef test_slow_unrelated_report(n):\n    time.sleep(1)\n"


def command_of(event) -> str:  # type: ignore[no-untyped-def]
    arguments = event.payload.get("arguments") or {}
    if arguments.get("command"):
        return str(arguments["command"])
    # python_run passes its arguments separately ("-m pytest"); without this every python_run test call was missed (D-559).
    return f"python {arguments['args']}" if arguments.get("args") else ""


@pytest.mark.parametrize("repeat", [1, 2, 3])
async def test_narrow_checks_then_one_full_run(make_host, repeat: int) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    if not FIXTURE_PYTHON.exists():
        pytest.skip("run scripts/dev/setup_fixture_venv.ps1 first")
    host = make_host("auto")
    (host.workspace.app_dir / "tests" / "test_slow_report.py").write_text(SLOW_TESTS, encoding="utf-8")
    task = (
        "In backend/claims_app/errors.py add a ConflictError class (HTTP 409, status text 'Conflict') following the style of the "
        "existing error classes, with a test for it in backend/tests/test_errors_conflict.py. The backend tests run with "
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
    last_edit = max(
        (e.seq for e in events if e.type == EventType.TOOL_CALL_STARTED and e.payload.get("name") in EDITS),
        default=0,
    )
    narrow = [seq for seq, command in calls if NARROWING.search(command)]
    full = [seq for seq, command in calls if not NARROWING.search(command)]
    full_after_last_edit = [seq for seq in full if seq > last_edit]
    final = [e.payload.get("text", "") for e in events_of(host, EventType.MESSAGE_DONE)][-1]
    print(
        f"\nINTENT run={repeat} seconds={elapsed:.0f} pytest_commands={len(calls)} narrow={len(narrow)} full={len(full)} "
        f"full_after_last_edit={len(full_after_last_edit)} final_chars={len(final)}"
    )
    assert calls, "the model ran no pytest command"
    assert full_after_last_edit, "no full run after the last edit"

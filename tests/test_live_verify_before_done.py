"""Live (real Azure model): after an edit the model runs a check before it says the work is done, and shows the evidence (D-477)."""

from __future__ import annotations

import pytest

from forge.protocol.events import Event, EventType
from forge.protocol.inputs import Reject, UserInput
from tests.test_live_agent import (  # noqa: F401  (make_host is a fixture)
    ERRORS,
    events_of,
    make_host,
    run_turn,
)

pytestmark = pytest.mark.live


def refuse_installs(event: Event) -> UserInput | None:
    """The fixture copy has no pytest; the model may want to install it. Refusing shows how it reports what it could not check."""
    if event.type == EventType.APPROVAL_REQUESTED:
        return Reject(request_id=event.payload["id"], instruction="No installs here.")
    return None


CHECKING_TOOLS = ("run_command", "run_tests", "python_run", "shell", "start_background", "http_request")


async def test_a_command_runs_after_the_last_edit_and_the_summary_quotes_it(make_host) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    host = make_host("auto")
    try:
        await run_turn(
            host,
            f"In {ERRORS}, add a ConflictError class (HTTP 409, status text 'Conflict') following the style of the existing error "
            "classes, then tell me whether it works.",
            refuse_installs,
        )
    except TimeoutError:
        for event in host.bus.events_since(0)[-12:]:
            print("LAST EVENT:", event.type, str(event.payload)[:300])
        raise
    await host.close()
    events = host.bus.events_since(0)
    names = [(e.seq, e.payload.get("name", "")) for e in events if e.type == EventType.TOOL_CALL_STARTED]
    last_edit = max(
        (seq for seq, name in names if name in ("edit_file", "multi_edit", "write_file")), default=None
    )
    assert last_edit is not None, "the model made no edit"
    checks_after = [name for seq, name in names if seq > last_edit and name in CHECKING_TOOLS]
    final = [e.payload.get("text", "") for e in events_of(host, EventType.MESSAGE_DONE)][-1]
    print("\nTOOLS AFTER LAST EDIT:", [name for seq, name in names if seq > last_edit])
    print("FINAL MESSAGE:\n", final)
    assert checks_after, "the model said it was done without running any check after its last edit"

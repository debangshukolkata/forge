"""Live A/B (real Azure model, D-477): does the verify-before-done skill, with its system-prompt line, change what the model checks and
says? Three runs per condition on the same small task; it prints one line per run and asserts only that every run finished. Run with:
pytest -m live -s tests/test_live_verify_ab.py"""

from __future__ import annotations

import re

import pytest

from forge.protocol.events import EventType
from tests.test_live_agent import (  # noqa: F401  (make_host is a fixture)
    ERRORS,
    events_of,
    make_host,
    run_turn,
)
from tests.test_live_verify_before_done import CHECKING_TOOLS, refuse_installs

pytestmark = pytest.mark.live
EDITS = ("edit_file", "multi_edit", "write_file")
LIMITS = re.compile(
    r"could not|couldn't|cannot confirm|can't confirm|not able|wasn't able|did not run|didn't run|not run|unable|not verified|unverified",
    re.I,
)
VERIFY_LINE = re.compile(
    r"^- Never say work is done.*?verify-before-done skill has the details\.\r?\n", re.S | re.M
)
TASK = (
    f"In {ERRORS}, add a ConflictError class (HTTP 409, status text 'Conflict') following the style of the existing error "
    "classes, then tell me whether it works."
)


@pytest.mark.parametrize("condition", ["with", "without"])
@pytest.mark.parametrize("repeat", [1, 2, 3])
async def test_ab(make_host, monkeypatch: pytest.MonkeyPatch, condition: str, repeat: int) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    if condition == "without":
        import forge.engine.session_host as session_host

        monkeypatch.setenv("FORGE_DISABLED_SKILLS", "verify-before-done")
        original = session_host.system_prompt
        monkeypatch.setattr(
            session_host, "system_prompt", lambda workspace: VERIFY_LINE.sub("", original(workspace))
        )
    host = make_host("auto")
    await run_turn(host, TASK, refuse_installs)
    await host.close()
    events = host.bus.events_since(0)
    started = [(e.seq, e.payload.get("name", "")) for e in events if e.type == EventType.TOOL_CALL_STARTED]
    last_edit = max((seq for seq, name in started if name in EDITS), default=0)
    after = [name for seq, name in started if seq > last_edit]
    checks = [name for name in after if name in CHECKING_TOOLS]
    final = [e.payload.get("text", "") for e in events_of(host, EventType.MESSAGE_DONE)][-1]
    print(
        f"\nAB cond={condition} run={repeat} checks_after_last_edit={len(checks)} tools_after={after} "
        f"names_its_limits={bool(LIMITS.search(final))} final_chars={len(final)}"
    )

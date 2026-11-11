"""Live (real Azure model): on an existing repository the model asks the repository map first and its answer
is right (KL1, D-563). The fixture repository is small, so this shows the behaviour, not the saving on a large
repository (that is TODO KL4). Set CODE_MAP_LOG to a file to get one JSON line per run."""

from __future__ import annotations

import json
import os

import pytest

from forge.protocol.events import EventType
from tests.test_live_agent import make_host, run_turn  # noqa: F401  (make_host is a fixture)

pytestmark = pytest.mark.live

# name -> (question, words the answer must contain)
SCENARIOS = {
    "endpoint": (
        "Do not change anything. What must a caller send to create a claim (endpoint, fields), does it need a "
        "token, and which database tables does that request touch?",
        ["/api/claims", "policy_id", "amount", "description", "jwt", "claims", "policies"],
    ),
    "callers": (
        "Do not change anything. Which functions call `count_claims`, and in which files?",
        ["list_claims", "create_claim", "claims_service"],
    ),
}


@pytest.mark.parametrize("scenario", list(SCENARIOS))
async def test_the_model_asks_the_map_first_and_answers_correctly(
    scenario: str,
    make_host,  # noqa: F811
) -> None:  # type: ignore[no-untyped-def]
    question, expected = SCENARIOS[scenario]
    host = make_host("auto")
    calls: list[str] = []
    said: list[str] = []

    def watch(event):  # type: ignore[no-untyped-def]
        if event.type == EventType.TOOL_CALL_STARTED:
            calls.append(f"{event.payload['name']} {event.payload['arguments']}"[:90])
        if event.type == EventType.MESSAGE_DONE:
            said.append(str(event.payload.get("text", "")))
        return None

    try:
        await run_turn(host, question, watch)
    finally:
        await host.close()
    answer = "\n".join(said).lower()
    missing = [word for word in expected if word.lower() not in answer]
    log = os.environ.get("CODE_MAP_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(
                json.dumps({"scenario": scenario, "calls": calls, "missing": missing, "answer": answer[:600]})
                + "\n"
            )
    print(f"\nSCENARIO {scenario}: {len(calls)} tool calls: {calls}; missing={missing}")
    assert calls and calls[0].startswith("code_map"), f"the first tool was not code_map: {calls}"
    assert not missing, f"the answer lacks {missing}: {answer[:400]}"

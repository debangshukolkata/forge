"""D-671: "what mistakes did you make that the generated code fails?" gives a three-layer report from the record."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx2
import pytest

from forge.agent.hints import self_review_hint
from forge.protocol.events import Event, EventType
from forge.toolkit.base import ToolContext
from forge.tools import build_review
from forge.tools.build_review import ReviewBuild, collect
from forge.workspace.conversations import ConversationStore
from forge.workspace.create import create_workspace
from tests.helpers import json_response, mocked_router, responses_body, text_output


def test_the_users_questions_lead_to_the_review_and_ordinary_requests_do_not() -> None:
    for asked in (
        "what mistakes you did that the generated code is giving error",
        "find out the issues with your generation",
        "Why did you generate an agent that writes wrong HTML?",
        "do a failure analysis of how debcraft built this",
    ):
        assert "review_build" in self_review_hint(asked), asked
    for other in (
        "fix the error in the dashboard agent",
        "what mistakes are in this csv file?",
        "build an HTML dashboard agent",
        "check your process list for the server",
    ):
        assert self_review_hint(other) == "", other


def _events() -> list[Event]:
    raw: list[tuple[EventType, dict[str, Any]]] = [
        (
            EventType.USER_MESSAGE,
            {"text": "Build an agent that turns a CSV into an HTML dashboard and tests it."},
        ),
        (
            EventType.TOOL_CALL_STARTED,
            {"id": "1", "name": "load_skill", "arguments": {"name": "langchain-agent"}},
        ),
        (
            EventType.TOOL_CALL_FINISHED,
            {"id": "1", "name": "load_skill", "ok": True, "summary": "langchain-agent", "preview": "..."},
        ),
        (
            EventType.TOOL_CALL_STARTED,
            {"id": "2", "name": "write_file", "arguments": {"path": "agent/prompt.py"}},
        ),
        (
            EventType.TOOL_CALL_FINISHED,
            {"id": "2", "name": "write_file", "ok": True, "summary": "agent/prompt.py", "preview": "ok"},
        ),
        (
            EventType.TOOL_CALL_STARTED,
            {"id": "3", "name": "edit_file", "arguments": {"path": "agent/prompt.py"}},
        ),
        (
            EventType.TOOL_CALL_FINISHED,
            {"id": "3", "name": "edit_file", "ok": True, "summary": "agent/prompt.py", "preview": "ok"},
        ),
        (EventType.TOOL_CALL_STARTED, {"id": "4", "name": "http_request", "arguments": {"url": "/jobs"}}),
        (
            EventType.TOOL_CALL_FINISHED,
            {
                "id": "4",
                "name": "http_request",
                "ok": True,
                "summary": "POST /jobs",
                "preview": '{"status": "failed", "error": "[dom_tag_balance]"}',
            },
        ),
        (EventType.TOOL_CALL_STARTED, {"id": "5", "name": "run_command", "arguments": {"command": "pytest"}}),
        (
            EventType.TOOL_CALL_FINISHED,
            {"id": "5", "name": "run_command", "ok": True, "summary": "pytest", "preview": "3 passed"},
        ),
        (EventType.NOTICE, {"kind": "usage", "text": "cost"}),
        (EventType.NOTICE, {"kind": "proof_call", "text": "Asking for the API call to be run again."}),
        (EventType.MESSAGE_DONE, {"text": "The agent now submits the job."}),
    ]
    return [
        Event(seq=n, type=kind, ts="2026-11-27T10:00:00", payload=payload)
        for n, (kind, payload) in enumerate(raw, 1)
    ]


def test_the_record_is_collected_by_code_and_numbered() -> None:
    evidence, changed = collect(_events())
    texts = dict(evidence)
    assert texts["E1"].startswith("the user asked: Build an agent")
    assert any("load_skill" in t for t in texts.values())
    assert any("http_request (POST /jobs) showed an error" in t for t in texts.values())
    assert not any("3 passed" in t for t in texts.values())  # a run without an error is not evidence of one
    assert not any("cost" in t for t in texts.values())
    assert any("proof_call" in t for t in texts.values())
    assert changed == {"agent/prompt.py": 2}


async def test_the_report_marks_a_claim_without_evidence_unproven(
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FORGE_NO_BROWSER", "1")
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    store = ConversationStore(workspace)
    log = store.events_path(store.active().id)
    log.parent.mkdir(parents=True, exist_ok=True)
    question = Event(
        seq=99,
        type=EventType.USER_MESSAGE,
        ts="2026-11-27T11:00:00",
        payload={"text": "what mistakes did you make?"},
    )
    after = Event(
        seq=100, type=EventType.TOOL_CALL_STARTED, ts="2026-11-27T11:00:01", payload={"id": "9", "name": "x"}
    )
    # the work, then the question: what the model does after the question is not the work under review
    log.write_text(
        "".join(e.model_dump_json() + "\n" for e in [*_events(), question, after]), encoding="utf-8"
    )
    (workspace.repo_dir / "agent").mkdir(exist_ok=True)
    (workspace.repo_dir / "agent" / "prompt.py").write_text('PROMPT = "Write the HTML."\n', encoding="utf-8")
    review = {
        "summary": "The agent wrote HTML without a specification.",
        "layer1": [{"failure": "Unbalanced tags in the dashboard", "evidence": ["E3"]}],
        "layer2": [
            {
                "decision": "The prompt for the agent has no output rules",
                "caused": [1],
                "evidence": ["E2"],
                "proven": True,
            },
            {"decision": "Nobody asked for a spec", "caused": [1], "evidence": ["E999"], "proven": True},
        ],
        "layer3": [
            {"change": "Require a chart specification before HTML", "part": "skill", "for": [1], "test": "x"}
        ],
        "not_in_record": "The playground's own logs.",
    }
    asked: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        asked.append(request.content.decode())
        return json_response(200, responses_body([text_output(json.dumps(review))]))

    context = ToolContext(workspace=workspace, router=mocked_router(handler))
    result = await ReviewBuild().run(ReviewBuild.Args(focus="why does it fail?"), context)
    assert result.ok, result.content
    assert "1 unproven" in result.content
    assert "what mistakes did you make" not in asked[0].split("RECORD:")[1]
    assert (
        "E1: the user asked" in asked[0] and "agent/prompt.py" in asked[0] and "Write the HTML." in asked[0]
    )
    [page] = list((isolated_forge_home / build_review.REPORTS).glob("build-review-*.html"))
    shown = page.read_text(encoding="utf-8")
    assert "Layer 1" in shown and "Layer 2" in shown and "Layer 3" in shown
    assert "UNPROVEN" in shown and "cited but not in the record: E999" in shown
    assert shown.count("UNPROVEN") == 1  # the claim with real evidence stands


def test_the_request_is_found_behind_the_orchestrators_brief_and_not_in_a_continuation() -> None:
    """D-671: the orchestrator puts a project's first request in a system brief, so no note of the loop fired then."""
    from forge.agent.loop import AgentLoop
    from forge.llm.base import Message

    loop = AgentLoop.__new__(AgentLoop)
    loop.context = ToolContext.__new__(ToolContext)
    loop.context.recent_user_messages = lambda: ["find out the issues with your generation"]
    prompt = Message.system("You are DebCraft.")
    assert loop._new_request([prompt, Message.user("build it")]) == "build it"
    first_brief = [prompt, Message.system("REQUIREMENT: find out the issues with your generation ...")]
    assert loop._new_request(first_brief) == "find out the issues with your generation"
    reopened = [prompt, Message.user("why did you build it so?"), Message.system("brief of the earlier work")]
    assert loop._new_request(reopened) == "why did you build it so?"
    continuation = [
        prompt,
        Message.user("build it"),
        Message(role="assistant", content="Done."),
        Message.system("check the page"),
    ]
    assert loop._new_request(continuation) is None

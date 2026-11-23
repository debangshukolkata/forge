"""D-410: risks in the code the model worked with are found and listed by DebCraft once per project (D-641)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx2
import pytest

from forge.agent.risk_notes import take_new_risks
from forge.engine.session_host import SessionHost
from forge.llm.base import Message
from forge.protocol.events import EventBus, EventType
from forge.safety.redact import Redactor
from forge.safety.risk_scan import mentioned, scan_text, scannable
from forge.workspace.create import create_workspace
from tests.helpers import mocked_router, reply, responses_body, text_output

SETTINGS = '''"""Application settings."""
import pickle

API_TOKEN = "tok_live_8f3a91c2d7e44b6f9a0c"


def load_settings(path):
    with open(path, "rb") as handle:
        return pickle.loads(handle.read())
'''

SQL = """def get_user(connection, name):
    query = f"SELECT id FROM users WHERE name = '{name}'"
    return connection.execute(query).fetchone()
"""


def test_the_usual_suspects_are_found_with_their_line() -> None:
    kinds = {risk.kind: risk.line for risk in scan_text("settings.py", SETTINGS)}
    assert kinds == {"hard-coded secret": 4, "unsafe deserialisation": 9}
    assert [r.kind for r in scan_text("users.py", SQL)] == ["SQL built from strings"]


def test_placeholders_comments_and_safe_code_are_not_findings() -> None:
    assert (
        scan_text(
            "a.py", 'API_KEY = "your-key-here-please"\n# pickle.loads(x)\nvalue = yaml.safe_load(text)\n'
        )
        == []
    )
    assert scan_text("a.py", 'connection.execute("SELECT id FROM users WHERE name = ?", (name,))\n') == []
    assert scan_text("a.py", 'PASSWORD = "<set me>"\n') == []


def test_tests_and_non_source_files_are_not_scanned() -> None:
    assert (
        scannable("shop/orders.py") and not scannable("tests/test_orders.py") and not scannable("README.md")
    )
    assert not scannable("web/src/app.test.tsx") and not scannable("conftest.py")


def test_a_reply_that_names_the_risk_is_left_alone() -> None:
    risk = scan_text("settings.py", SETTINGS)[1]
    assert not mentioned(risk, "Done. I added get_timeout and tests.")
    assert mentioned(
        risk, "Noticed, not changed: settings.py:9 loads the file with pickle, which can run code."
    )


def seeded_host(original_repo: Path, tmp_path: Path, handler: Any) -> SessionHost:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    workspace.write_text("settings.py", SETTINGS, "seed")
    host = SessionHost(mocked_router(handler), EventBus(redactor=Redactor()), workspace=workspace)
    assert host.agent is not None
    host.agent.context.reads.record("settings.py", SETTINGS.encode())
    return host


def one_answer(request: httpx2.Request) -> httpx2.Response:
    return reply(request, responses_body([text_output("Done.")]))


def test_each_risk_is_taken_once_per_project_also_when_its_line_moves(
    original_repo: Path, tmp_path: Path
) -> None:
    host = seeded_host(original_repo, tmp_path, one_answer)
    assert host.agent is not None and host.workspace is not None
    context = host.agent.context
    kinds = {risk.kind for risk in take_new_risks(context, "Done.")}
    assert kinds == {"hard-coded secret", "unsafe deserialisation"}
    host.workspace.write_text("settings.py", "# a new first line\n" + SETTINGS, "edit")
    assert take_new_risks(context, "Done.") == []
    saved = (host.workspace.forge_dir / "risks_shown.json").read_text(encoding="utf-8")
    assert "tok_live" not in saved


def test_a_risk_the_reply_names_with_its_file_is_not_listed_again(
    original_repo: Path, tmp_path: Path
) -> None:
    host = seeded_host(original_repo, tmp_path, one_answer)
    assert host.agent is not None
    risks = take_new_risks(host.agent.context, "settings.py:9 loads with pickle.")
    assert [risk.kind for risk in risks] == ["hard-coded secret"]


async def run_turn(host: SessionHost, edited: str | None, monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """One turn with one reply; `edited` is the file that counts as changed while the model worked."""
    loop = host.agent
    assert loop is not None
    notices: list[Any] = []
    publish, chat = host.bus.publish, loop._chat

    async def spy(event_type: Any, payload: Any) -> Any:
        if event_type == EventType.NOTICE and payload.get("kind") == "risks_noticed":
            notices.append(payload)
        return await publish(event_type, payload)

    async def chat_with_edit(*args: Any, **kwargs: Any) -> Any:
        answer = await chat(*args, **kwargs)
        if edited:
            loop.context.step += 1
            loop.context.note_edit(edited)
        return answer

    async def no_review(context: Any) -> None:
        return None

    async def no_delta(delta: str) -> None:
        return None

    monkeypatch.setattr("forge.agent.loop.review_leftovers", no_review)
    monkeypatch.setattr(host.bus, "publish", spy)
    monkeypatch.setattr(loop, "_chat", chat_with_edit)
    history = [Message.system("s"), Message.user("change it")]
    await loop.run(history, no_delta)
    assert sum(1 for m in history if m.role == "assistant") == 1, "the model answered twice"
    return notices


async def test_debcraft_lists_the_risks_itself_and_the_model_answers_once(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    host = seeded_host(original_repo, tmp_path, one_answer)
    notices = await run_turn(host, "settings.py", monkeypatch)
    assert len(notices) == 1 and len(notices[0]["risks"]) == 2
    assert "tok_live" not in str(notices)


@pytest.mark.parametrize("edited", [None, "TODO.md"])
async def test_a_turn_that_changed_no_code_lists_nothing(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, edited: str | None
) -> None:
    host = seeded_host(original_repo, tmp_path, one_answer)
    assert await run_turn(host, edited, monkeypatch) == []

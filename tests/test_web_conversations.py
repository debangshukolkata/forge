"""The conversation routes of the web server (D-582; no model calls)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from forge.engine.session_host import SessionHost
from forge.protocol.events import EventBus
from forge.safety.redact import Redactor
from forge.safety.server_security import ServerSecurity
from forge.web.manager import WebSessionManager
from forge.web.server import create_app
from forge.workspace.conversations import ConversationStore
from forge.workspace.create import create_workspace
from forge.workspace.workspace import Workspace
from tests.helpers import mocked_router
from tests.test_web import BASE, ORIGIN, login, unreachable

PORT = 8799


def session_on_the_active_conversation(workspace: Workspace) -> SessionHost:
    store = ConversationStore(workspace)
    bus = EventBus(store.events_path(store.active().id), redactor=Redactor())
    return SessionHost(mocked_router(unreachable), bus, workspace=workspace)


@pytest.fixture
def security() -> ServerSecurity:
    return ServerSecurity(port=PORT, token="test-token-0123456789")  # check_secrets: fake


@pytest.fixture
def opened(
    security: ServerSecurity, isolated_forge_home: Path, original_repo: Path, tmp_path: Path
) -> Iterator[tuple[TestClient, WebSessionManager, Workspace]]:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    log = workspace.forge_dir / "transcripts" / "events.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        json.dumps(
            {
                "seq": 1,
                "type": "user_message",
                "ts": "2026-01-01T00:00:00.000+00:00",
                "payload": {"text": "first chat"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    manager = WebSessionManager(isolated_forge_home, session_on_the_active_conversation)
    with TestClient(create_app(manager, security), base_url=BASE) as client:
        login(client, security)
        assert (
            client.post("/api/open", json={"workspace": str(workspace.root)}, headers=ORIGIN).status_code
            == 200
        )
        yield client, manager, workspace


def test_the_list_starts_with_the_first_conversation(opened) -> None:  # type: ignore[no-untyped-def]
    client, _, _ = opened
    listing = client.get("/api/conversations", headers=ORIGIN).json()
    assert listing["active"] == "c1"
    assert [(c["id"], c["title"], c["active"]) for c in listing["conversations"]] == [
        ("c1", "first chat", True)
    ]
    assert client.get("/api/state", headers=ORIGIN).json()["workspace"]["conversation"] == {
        "id": "c1",
        "title": "first chat",
    }


def test_a_new_conversation_opens_empty_and_the_first_one_comes_back(opened) -> None:  # type: ignore[no-untyped-def]
    client, manager, _ = opened
    created = client.post("/api/conversations", json={"title": "second"}, headers=ORIGIN)
    assert created.status_code == 200 and created.json() == {"id": "c2"}
    assert manager.host is not None and manager.host.conversations is not None
    assert manager.host.conversations.conversation_id == "c2"
    assert manager.host.bus.events_since(0) == [] or all(
        e.type != "user_message" for e in manager.host.bus.events_since(0)
    )

    back = client.post("/api/conversations/open", json={"id": "c1"}, headers=ORIGIN)
    assert back.status_code == 200
    events = manager.host.bus.events_since(0)  # type: ignore[union-attr]
    assert any(e.type == "user_message" and e.payload["text"] == "first chat" for e in events)
    listing = client.get("/api/conversations", headers=ORIGIN).json()
    assert listing["active"] == "c1" and [c["id"] for c in listing["conversations"]] == ["c1", "c2"]


def test_unknown_and_malformed_ids_are_not_found(opened) -> None:  # type: ignore[no-untyped-def]
    client, _, _ = opened
    for bad in ("c9", "../x", "c0"):
        assert client.post("/api/conversations/open", json={"id": bad}, headers=ORIGIN).status_code == 404
        assert (
            client.post(
                "/api/conversations/rename", json={"id": bad, "title": "x"}, headers=ORIGIN
            ).status_code
            == 404
        )


def test_rename(opened) -> None:  # type: ignore[no-untyped-def]
    client, _, _ = opened
    result = client.post(
        "/api/conversations/rename", json={"id": "c1", "title": "Better name"}, headers=ORIGIN
    )
    assert result.status_code == 200 and result.json()["conversations"][0]["title"] == "Better name"


def test_a_switch_while_the_agent_works_asks_first_and_stops_it_when_told(opened, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    client, manager, _ = opened
    assert manager.host is not None
    manager.host._pretend_busy = True  # type: ignore[attr-defined]

    async def stop(self: SessionHost) -> None:
        self._pretend_busy = False  # type: ignore[attr-defined]

    monkeypatch.setattr(SessionHost, "busy", property(lambda self: getattr(self, "_pretend_busy", False)))
    monkeypatch.setattr(SessionHost, "interrupt", stop)

    refused = client.post("/api/conversations", json={"title": ""}, headers=ORIGIN)
    assert refused.status_code == 409 and refused.json() == {
        "detail": "DebCraft is working in this conversation.",
        "busy": True,
    }
    assert ConversationStore(manager.workspace).active().id == "c1"  # type: ignore[arg-type]  # nothing switched

    accepted = client.post("/api/conversations", json={"title": "", "stop_running": True}, headers=ORIGIN)
    assert accepted.status_code == 200 and accepted.json() == {"id": "c2"}


def test_the_routes_need_the_login(opened, security: ServerSecurity) -> None:  # type: ignore[no-untyped-def]
    client, _, _ = opened
    client.cookies.clear()
    assert client.get("/api/conversations", headers=ORIGIN).status_code in (401, 403)
    assert client.post("/api/conversations", json={}, headers=ORIGIN).status_code in (401, 403)

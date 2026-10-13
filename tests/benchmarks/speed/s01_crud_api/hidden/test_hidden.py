from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NOTES_DB", str(tmp_path / "t.db"))
    import app as module

    importlib.reload(module)
    with TestClient(module.app) as test_client:
        yield test_client


def test_create_and_get(client) -> None:
    created = client.post("/notes", json={"title": "Milk", "body": "2 liters"})
    assert created.status_code == 201
    note = created.json()
    assert note["id"] == 1 and note["title"] == "Milk" and note["body"] == "2 liters"
    assert client.get(f"/notes/{note['id']}").json() == note


def test_body_defaults_to_empty(client) -> None:
    assert client.post("/notes", json={"title": "x"}).json()["body"] == ""


@pytest.mark.parametrize("payload", [{}, {"title": ""}, {"title": "   "}, {"body": "only body"}])
def test_bad_title_is_422(client, payload) -> None:
    assert client.post("/notes", json=payload).status_code == 422


def test_list_in_id_order_and_search(client) -> None:
    for title, body in [("Alpha", "one"), ("beta", "Two"), ("Gamma", "alpha again")]:
        client.post("/notes", json={"title": title, "body": body})
    assert [n["id"] for n in client.get("/notes").json()] == [1, 2, 3]
    assert [n["id"] for n in client.get("/notes", params={"q": "ALPHA"}).json()] == [1, 3]
    assert [n["id"] for n in client.get("/notes", params={"q": "two"}).json()] == [2]
    assert client.get("/notes", params={"q": "zzz"}).json() == []


def test_not_found(client) -> None:
    for call in (
        client.get("/notes/9"),
        client.put("/notes/9", json={"title": "t"}),
        client.delete("/notes/9"),
    ):
        assert call.status_code == 404 and call.json() == {"detail": "not found"}


def test_update_and_delete(client) -> None:
    client.post("/notes", json={"title": "a", "body": "b"})
    updated = client.put("/notes/1", json={"title": "new", "body": "text"})
    assert updated.status_code == 200 and updated.json() == {"id": 1, "title": "new", "body": "text"}
    assert client.put("/notes/1", json={"title": " "}).status_code == 422
    deleted = client.delete("/notes/1")
    assert deleted.status_code == 204 and deleted.content == b""
    assert client.get("/notes/1").status_code == 404


def test_data_survives_a_new_client(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NOTES_DB", str(tmp_path / "keep.db"))
    import app as module

    importlib.reload(module)
    with TestClient(module.app) as first:
        first.post("/notes", json={"title": "persist"})
    importlib.reload(module)
    with TestClient(module.app) as second:
        assert [n["title"] for n in second.get("/notes").json()] == ["persist"]

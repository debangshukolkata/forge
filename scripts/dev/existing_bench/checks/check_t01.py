# ruff: noqa: F811, RUF059
"""T01: no user can read, change or delete another user's item; the owner and a superuser still can."""

from __future__ import annotations

from template_support import harness  # noqa: F401  (pytest fixture)


def _setup(harness):
    owner = harness.make_user("owner@example.com")
    other = harness.make_user("other@example.com")
    admin = harness.make_user("boss@example.com", superuser=True)
    return owner, other, admin, harness.make_item(owner)


def test_other_user_cannot_read(harness):
    owner, other, admin, item = _setup(harness)
    harness.login_as(other)
    assert harness.client.get(f"/api/v1/items/{item.id}").status_code == 403


def test_other_user_cannot_update(harness):
    owner, other, admin, item = _setup(harness)
    harness.login_as(other)
    assert harness.client.put(f"/api/v1/items/{item.id}", json={"title": "mine now"}).status_code == 403


def test_other_user_cannot_delete(harness):
    owner, other, admin, item = _setup(harness)
    harness.login_as(other)
    assert harness.client.delete(f"/api/v1/items/{item.id}").status_code == 403


def test_owner_and_superuser_can_read(harness):
    owner, other, admin, item = _setup(harness)
    harness.login_as(owner)
    assert harness.client.get(f"/api/v1/items/{item.id}").status_code == 200
    harness.login_as(admin)
    assert harness.client.get(f"/api/v1/items/{item.id}").status_code == 200


def test_unknown_id_is_404(harness):
    owner, other, admin, item = _setup(harness)
    harness.login_as(owner)
    assert harness.client.get("/api/v1/items/00000000-0000-0000-0000-000000000000").status_code == 404


def test_list_shows_only_own_items(harness):
    owner, other, admin, item = _setup(harness)
    harness.make_item(other, "theirs")
    harness.login_as(owner)
    data = harness.client.get("/api/v1/items/").json()
    assert data["count"] == 1 and data["data"][0]["id"] == str(item.id)

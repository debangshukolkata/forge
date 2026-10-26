# ruff: noqa: F811, I001
"""T03: items carry updated_at (model, API responses, migration) and it moves on update."""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime

from template_support import harness  # noqa: F401  (pytest fixture)

from app import crud
from app.models import ItemCreate, ItemPublic

ORIGINAL_HEAD = "fe56fa70289e"


def _naive_utc(text: str) -> datetime:
    parsed = datetime.fromisoformat(text)
    return parsed.astimezone(UTC).replace(tzinfo=None) if parsed.tzinfo else parsed


def test_public_model_has_the_field():
    assert "updated_at" in ItemPublic.model_fields


def test_created_through_crud_has_a_value(harness):
    owner = harness.make_user("owner@example.com")
    item = crud.create_item(session=harness.session, item_in=ItemCreate(title="x"), owner_id=owner.id)
    assert item.updated_at is not None


def test_created_through_the_api_returns_it(harness):
    owner = harness.make_user("owner@example.com")
    harness.login_as(owner)
    body = harness.client.post("/api/v1/items/", json={"title": "first"}).json()
    assert body["updated_at"]
    listed = harness.client.get("/api/v1/items/").json()["data"][0]
    assert listed["updated_at"]


def test_update_moves_the_timestamp_forward(harness):
    owner = harness.make_user("owner@example.com")
    harness.login_as(owner)
    created = harness.client.post("/api/v1/items/", json={"title": "first"}).json()
    time.sleep(0.05)
    changed = harness.client.put(f"/api/v1/items/{created['id']}", json={"title": "second"}).json()
    assert _naive_utc(changed["updated_at"]) > _naive_utc(created["updated_at"])
    assert changed["created_at"] == created["created_at"]


def test_migration_adds_the_column_on_top_of_the_single_head(repo):
    versions = repo / "backend" / "app" / "alembic" / "versions"
    revisions: dict[str, tuple[str, str]] = {}
    for path in versions.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        revision = re.search(r"^revision\s*(?::\s*\w+\s*)?=\s*['\"](\w+)['\"]", text, re.M)
        down = re.search(r"^down_revision\s*(?::[^=]+)?=\s*['\"]?(\w+)['\"]?", text, re.M)
        if revision:
            revisions[revision.group(1)] = (down.group(1) if down else "None", text)
    parents = {down for down, _ in revisions.values()}
    heads = [rev for rev in revisions if rev not in parents]
    assert len(heads) == 1, f"expected one migration head, found {heads}"
    head = heads[0]
    assert head != ORIGINAL_HEAD, "no new migration was added"
    down, text = revisions[head]
    assert down == ORIGINAL_HEAD
    assert "updated_at" in text and "'item'" in text.replace('"', "'")

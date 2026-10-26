# ruff: noqa: I001, E402
"""Runs the full-stack-fastapi-template app against an in-memory SQLite database, so its behaviour can be checked without Postgres.

The check interpreter needs the template's backend dependencies (fastapi, sqlmodel, pydantic-settings, pyjwt, pwdlib, emails, ...).
The delivered copy is BENCH_REPO; its backend folder goes first on sys.path."""

from __future__ import annotations

import os
import sys
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest

os.environ.setdefault("SECRET_KEY", "bench-secret-not-the-default-value")  # check_secrets: fake
os.environ.setdefault("PROJECT_NAME", "Bench")
FAKE_PASSWORD = "bench-pass-123"  # check_secrets: fake
os.environ.setdefault("DATABASE_URL", "postgresql://bench:" + FAKE_PASSWORD + "@localhost:5432/bench")
os.environ.setdefault("FIRST_SUPERUSER", "admin@example.com")
os.environ.setdefault("FIRST_SUPERUSER_PASSWORD", "bench-admin-pass-123")  # check_secrets: fake
os.environ.setdefault("FASTAPI_ENV", "development")

BACKEND = Path(os.environ["BENCH_REPO"]) / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import crud
from app.api import deps
from app.main import app
from app.models import Item, User, UserCreate

PASSWORD = "bench-password-1"  # check_secrets: fake


class Harness:
    """A test client whose database is SQLite and whose logged-in user can be switched."""

    def __init__(self) -> None:
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        SQLModel.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.current_id: uuid.UUID | None = None

        def get_db() -> Generator[Session]:
            with Session(self.engine) as session:
                yield session

        def get_current_user() -> User:
            assert self.current_id is not None
            user = self.session.get(User, self.current_id)
            assert user is not None
            return user

        app.dependency_overrides[deps.get_db] = get_db
        self._get_current_user = get_current_user
        self.client = TestClient(app)

    def make_user(self, email: str, *, superuser: bool = False) -> User:
        return crud.create_user(
            session=self.session,
            user_create=UserCreate(email=email, password=PASSWORD, is_superuser=superuser),
        )

    def make_item(self, owner: User, title: str = "thing") -> Item:
        item = Item(title=title, owner_id=owner.id)
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return item

    def login_as(self, user: User) -> None:
        self.current_id = user.id
        app.dependency_overrides[deps.get_current_user] = self._get_current_user

    def close(self) -> None:
        app.dependency_overrides.clear()
        self.session.close()


@pytest.fixture
def harness() -> Generator[Harness]:
    instance = Harness()
    yield instance
    instance.close()

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path

import jwt
import pytest
from flask import Flask
from flask.testing import FlaskClient
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from claims_app import create_app
from claims_app.config import Config
from claims_app.db import get_engine, session_scope
from claims_app.models import Base, Claim, Policy

TEST_JWT_SECRET = "test-jwt-secret-for-fixture-suite-0123456789"


class FakeLLMRegistry:
    """Responses the next fake LLM will return, set per test."""

    responses: list[str] = ["other", "A claim."]


def make_test_config(database_url: str) -> type[Config]:
    class TestConfig(Config):
        APP_ENV = "test"
        DATABASE_URL = database_url
        BOOTSTRAP_FROM_CONFIG_TABLE = False
        JWT_SECRET = TEST_JWT_SECRET
        LLM_FACTORY = staticmethod(lambda: FakeListChatModel(responses=list(FakeLLMRegistry.responses)))

    return TestConfig


def seed(session_factory_scope) -> None:  # type: ignore[no-untyped-def]
    with session_factory_scope() as session:
        session.add_all(
            [
                Policy(id=1, policy_number="POL-1001", holder_name="Asha Rao", status="active",
                       start_date=date(2025, 4, 1), end_date=date(2026, 3, 31)),
                Policy(id=2, policy_number="POL-1002", holder_name="Vikram Sen", status="lapsed",
                       start_date=date(2024, 1, 1), end_date=date(2024, 12, 31)),
            ]
        )
        session.flush()
        session.add_all(
            [
                Claim(id=1, claim_number="CLM-2025-00001", policy_id=1, status="submitted", amount=45000,
                      description="Burst pipe flooded the kitchen and damaged cabinets.",
                      submitted_at=datetime(2025, 6, 2, 10, 30)),
                Claim(id=2, claim_number="CLM-2025-00002", policy_id=1, status="approved", category="theft",
                      amount=120000, description="Laptop and jewellery stolen during a break-in.",
                      submitted_at=datetime(2025, 7, 15, 9, 0)),
                Claim(id=3, claim_number="CLM-2025-00003", policy_id=1, status="submitted", amount=8000,
                      description="Minor scratch on the rear bumper in a parking lot.",
                      submitted_at=datetime(2025, 8, 20, 16, 45)),
            ]
        )


@pytest.fixture
def app(tmp_path: Path) -> Iterator[Flask]:
    application = create_app(make_test_config(f"sqlite:///{tmp_path / 'claims.db'}"))
    Base.metadata.create_all(get_engine())
    seed(session_scope)
    yield application
    get_engine().dispose()


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    token = jwt.encode({"sub": "handler@example.test"}, TEST_JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def fake_llm_responses() -> Iterator[type[FakeLLMRegistry]]:
    original = FakeLLMRegistry.responses
    yield FakeLLMRegistry
    FakeLLMRegistry.responses = original

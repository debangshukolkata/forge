"""The fixture host app must itself be healthy, or every later Forge test is meaningless."""

from __future__ import annotations

import subprocess

import pytest

from tests.conftest import FIXTURE_BACKEND

FIXTURE_PYTHON = FIXTURE_BACKEND / "venv" / "Scripts" / "python.exe"


@pytest.mark.fixture
@pytest.mark.skipif(
    not FIXTURE_PYTHON.exists(), reason="run scripts/dev/setup_fixture_venv.ps1 to create the fixture venv"
)
def test_fixture_suite_passes_under_its_own_interpreter() -> None:
    result = subprocess.run(
        [str(FIXTURE_PYTHON), "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=FIXTURE_BACKEND,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]


def test_fixture_has_expected_shape() -> None:
    expected = [
        "claims_app/__init__.py",
        "claims_app/bootstrap.py",
        "claims_app/api/claims/routes.py",
        "claims_app/repositories/claims_repository.py",
        "claims_app/graphs/triage_graph.py",
        "sql/V001__create_policies.sql",
        "tests/conftest.py",
        ".env",
        "requirements.txt",
    ]
    missing = [path for path in expected if not (FIXTURE_BACKEND / path).exists()]
    assert missing == []

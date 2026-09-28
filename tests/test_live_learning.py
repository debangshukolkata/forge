"""M10C live acceptance: after two live runs on the fixture (same Forge home, related requirements), the second
run's plan cites the first run's requirement card; the retro proposes lessons that go through approval.
Run with: pytest -m live tests/test_live_learning.py"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from forge.engine.headless import EXIT_OK, run_headless
from forge.learning.lessons import LessonStore
from forge.learning.library import Library
from forge.learning.scope import scope_of, visible_scopes
from forge.session import build_session
from forge.workspace.create import create_workspace
from tests.conftest import FIXTURE_BACKEND, FIXTURE_REPO, REPO_ROOT

pytestmark = pytest.mark.live
FIXTURE_PYTHON = FIXTURE_BACKEND / "venv" / "Scripts" / "python.exe"

FIRST = (
    "Add GET /api/policies/<policy_id>/claims/count returning {policy_id, claim_count}; 404 if the policy doesn't "
    "exist; jwt protected like the other policy routes. Raw-SQL repository function, service, route, tests."
)
SECOND = (
    "Add GET /api/policies/<policy_id>/claims/total-amount returning {policy_id, total_amount} (sum of the "
    "policy's claim amounts, 0 when none); 404 if the policy doesn't exist; jwt protected. Same layering, tests."
)


async def test_second_run_cites_the_first_runs_card(
    tmp_path: Path, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not FIXTURE_PYTHON.exists():
        pytest.skip("run scripts/dev/setup_fixture_venv.ps1 first")
    monkeypatch.setenv("FORGE_ENV_FILE", str(REPO_ROOT / ".env"))

    first = create_workspace(FIXTURE_REPO, tmp_path / "ws1", "backend")
    result = await run_headless(build_session(workspace=first, orchestrated=True), FIRST, auto_approve=True)
    assert result.exit_code == EXIT_OK, result
    scopes = visible_scopes(scope_of(first, isolated_forge_home))
    cards = Library(isolated_forge_home).cards(scopes)
    assert [c["id"] for c in cards] == ["REQ-0001"]
    assert (isolated_forge_home / "learning" / "metrics.jsonl").exists()
    lessons = LessonStore(isolated_forge_home).all()
    assert all(
        lesson.status in ("approved", "rejected") for lesson in lessons
    )  # the retro asked (auto-approved)

    second = create_workspace(FIXTURE_REPO, tmp_path / "ws2", "backend")
    result = await run_headless(build_session(workspace=second, orchestrated=True), SECOND, auto_approve=True)
    assert result.exit_code == EXIT_OK, result
    plan = (second.forge_dir / "PLAN.md").read_text(encoding="utf-8")
    assert re.search(r"REQ-0001", plan), plan[:2000]
    assert [c["id"] for c in Library(isolated_forge_home).cards(scopes)] == ["REQ-0001", "REQ-0002"]

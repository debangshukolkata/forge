from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_REPO = REPO_ROOT / "tests" / "fixtures" / "sample_repo"
FIXTURE_BACKEND = FIXTURE_REPO / "backend"


@pytest.fixture(autouse=True)
def isolated_forge_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Tests never touch the real %USERPROFILE%\\.forge."""
    home = tmp_path / "forge_home"
    home.mkdir()
    monkeypatch.setenv("FORGE_HOME", str(home))
    # New standalone workspaces install pytest from the network; tests create many, so they skip it
    # (test_modeb covers the install itself).
    monkeypatch.setenv("FORGE_SKIP_TEST_RUNNER_INSTALL", "1")
    return home


@pytest.fixture(scope="session")
def original_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A realistic user repository (fixture app + awkward files + real venv). Treated as read-only."""
    from tests.workspace_helpers import build_original_repo  # local import: that module imports this one

    base = tmp_path_factory.mktemp("orig")
    return build_original_repo(base / "claims-repo", base / "outside")

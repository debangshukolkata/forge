"""Live acceptance (spec §7, D-128): the real model drives a requirement to export on the fixture, a
killed run resumes at the same task, and a restructure keeps the tests passing. Slow (several minutes
each). Run with: pytest -m live"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import psutil
import pytest

from forge.cli import _cleanup
from forge.engine.headless import EXIT_OK, auto_reply, run_headless
from forge.protocol.events import EventType
from forge.protocol.inputs import SlashCommand
from forge.session import build_session
from forge.workflow.state import StateStore
from forge.workspace.create import create_workspace
from forge.workspace.workspace import Workspace
from tests.conftest import FIXTURE_BACKEND, FIXTURE_REPO, REPO_ROOT

pytestmark = pytest.mark.live
REQUIREMENT = (
    "Add a paginated GET /api/policies/ endpoint that lists all policies, newest start_date first, with "
    "page and page_size query parameters and the same response shape as the claims list (items, total, "
    "page, page_size). Follow the existing layering: a raw-SQL repository function, a service function, the "
    "route with marshmallow schemas, and tests. No authentication changes."
)
FIXTURE_PYTHON = FIXTURE_BACKEND / "venv" / "Scripts" / "python.exe"


@pytest.fixture(scope="module")
def shared_home(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One Forge home for the module, so the KB is built once."""
    return tmp_path_factory.mktemp("forge_home_orchestrator")


@pytest.fixture
def live_env(shared_home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    if not FIXTURE_PYTHON.exists():
        pytest.skip("run scripts/dev/setup_fixture_venv.ps1 first")
    monkeypatch.setenv("FORGE_HOME", str(shared_home))
    monkeypatch.setenv("FORGE_ENV_FILE", str(REPO_ROOT / ".env"))
    return shared_home


@pytest.fixture(autouse=True)
def drop_scratch_objects(live_env: Path, tmp_path: Path) -> Iterator[None]:
    """Forge creates its scratch schema on the local DB (forge_if_allowed); drop it after each test."""
    yield
    if (tmp_path / "ws" / ".forge").exists():
        assert _cleanup(tmp_path / "ws", yes=True) == 0


def workspace_tests_pass(workspace: Workspace) -> bool:
    result = subprocess.run(
        [str(FIXTURE_PYTHON), "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=workspace.app_dir,
        capture_output=True,
        text=True,
        timeout=300,
        env={**os.environ, "PYTHONPATH": str(workspace.app_dir)},
    )
    return result.returncode == 0


async def test_requirement_runs_from_clarify_to_export_then_restructures(
    live_env: Path, tmp_path: Path
) -> None:
    workspace = create_workspace(FIXTURE_REPO, tmp_path / "ws", "backend")
    host = build_session(workspace=workspace)

    result = await asyncio.wait_for(run_headless(host, REQUIREMENT, auto_approve=True), timeout=1500)

    assert result.exit_code == EXIT_OK, (result.activity, result.tasks, result.errors)
    assert host.orchestrator is not None and host.orchestrator.state.exported
    assert all(t["status"] == "done" for t in result.tasks)
    forge = workspace.forge_dir
    for name in (
        "REQUIREMENTS.md",
        "PLAN.md",
        "tasks.json",
        "PROGRESS.md",
        "reports/review.md",
        "reports/final.md",
    ):
        assert (forge / name).exists(), name
    assert "PASSED" in (forge / "reports" / "review.md").read_text(encoding="utf-8")
    manifest = json.loads((workspace.output_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    changed = {f["path"] for f in manifest["files"]}
    assert "backend/claims_app/api/policies/routes.py" in changed
    assert any(p.startswith("backend/tests/") for p in changed)
    assert workspace_tests_pass(workspace)
    assert (workspace.output_dir / "COPY_INSTRUCTIONS.md").exists()

    # RESTRUCTURE (spec §6.7): behaviour kept, output shows the move.
    host = build_session(workspace=workspace)
    subscription = host.bus.subscribe(since_seq=host.bus.last_seq)
    engine = asyncio.create_task(host.run())

    async def respond() -> None:
        async for event in subscription:
            reply = auto_reply(event, auto_approve=True)
            if reply is not None:
                await host.submit(reply)

    responder = asyncio.create_task(respond())
    await host.submit(
        SlashCommand(
            text=(
                "/restructure Move the new policies service code into its own module "
                "claims_app/services/policies_service.py and update the imports."
            )
        )
    )
    async with asyncio.timeout(1200):
        # The command is queued first: wait for the restructure to start (exported flips back to False,
        # D-132), then for it to finish (exported again, and the run is idle).
        while host.orchestrator is None or host.orchestrator.state.exported:
            await asyncio.sleep(1)
        while not host.orchestrator.state.exported or host.busy or not host.inputs_empty:
            await asyncio.sleep(2)
    subscription.close()
    await host.close()
    responder.cancel()
    engine.cancel()

    review = (forge / "reports" / "review.md").read_text(encoding="utf-8")
    assert "Restructure check" in review and "(same)" in review
    assert workspace.path_of("backend/claims_app/services/policies_service.py").exists()
    assert workspace_tests_pass(workspace)
    manifest = json.loads((workspace.output_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    assert "backend/claims_app/services/policies_service.py" in {f["path"] for f in manifest["files"]}


def test_killed_run_resumes_the_same_task(live_env: Path, tmp_path: Path) -> None:
    workspace = create_workspace(FIXTURE_REPO, tmp_path / "ws", "backend")
    forge_exe = Path(sys.executable).parent / "forge.exe"
    command = [str(forge_exe), "run", "--workspace", str(workspace.root), "-p", REQUIREMENT, "--auto-approve"]
    environment = {
        **os.environ,
        "FORGE_HOME": str(live_env),
        "FORGE_ENV_FILE": str(REPO_ROOT / ".env"),
        "PYTHONIOENCODING": "utf-8",
    }
    process = subprocess.Popen(command, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    store = StateStore(workspace)
    killed_during: str | None = None
    deadline = time.monotonic() + 1200
    while time.monotonic() < deadline and process.poll() is None:
        time.sleep(3)
        if not store.path.exists():
            continue
        state = store.load()
        done = [t for t in state.tasks if t.status == "done"]
        if done and state.current_task:
            killed_during = state.current_task
            for child in psutil.Process(process.pid).children(recursive=True):
                child.kill()
            process.kill()
            break
    assert killed_during is not None, "the run finished or never reached a second task"
    process.wait(timeout=30)
    before = store.load()
    finished_before = {t.id for t in before.tasks if t.status == "done"}

    resumed = subprocess.run(
        [
            str(forge_exe),
            "run",
            "--workspace",
            str(workspace.root),
            "--auto-approve",
            "--output-format",
            "json",
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=1500,
    )
    report = json.loads(resumed.stdout[resumed.stdout.index("{") :])

    assert report["exit_code"] == EXIT_OK, report
    after = store.load()
    assert after.exported
    assert finished_before <= {t.id for t in after.tasks if t.status == "done"}
    events = [
        json.loads(line)
        for line in (workspace.forge_dir / "transcripts" / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    resume_notices = [
        e for e in events if e["type"] == EventType.NOTICE.value and e["payload"].get("kind") == "resume"
    ]
    assert resume_notices and f"on {killed_during}" in resume_notices[0]["payload"]["text"]
    progress = (workspace.forge_dir / "PROGRESS.md").read_text(encoding="utf-8")
    for task_id in finished_before:  # finished tasks were not redone after the restart
        assert progress.count(f"{task_id} ") == 1, task_id
    assert workspace_tests_pass(workspace)

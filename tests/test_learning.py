"""M10C: requirements library and lessons (scopes, approval, retrieval), metrics, retro parsing, Forge
cannot write itself or config.yaml, tier-2 prompt tweaks and tier-3 patch validation in a sandbox copy."""

from __future__ import annotations

from pathlib import Path

import pytest

import forge
from forge.engine.session_host import SessionHost
from forge.learning.improve import Improvements, forge_source_root, prompt_override
from forge.learning.lessons import LessonStore, parse_proposals, render_for_pin
from forge.learning.library import Library
from forge.learning.metrics import Metrics
from forge.learning.scope import scope_of, visible_scopes
from forge.modeb.profile import ProfileStore
from forge.modeb.workspace import create_standalone_workspace
from forge.protocol.events import EventBus
from forge.safety.paths import JailViolationError
from forge.safety.redact import Redactor
from forge.toolkit.base import ToolContext
from forge.tools.files import WriteFile
from forge.workflow.state import Task
from forge.workspace.create import create_workspace
from tests.helpers import mocked_router


def _card(library: Library, scope: str, workspace: str, text: str, files: list[str]) -> str:
    return library.write_card(
        scope=scope,
        workspace_root=workspace,
        workspace_name=Path(workspace).name,
        requirement=text,
        plan="Add a repository query, a service and a MethodView route.",
        decisions="",
        tasks=[],
        files=files,
        sql="CREATE TABLE IF NOT EXISTS claim_exports (id int);",
        status="done",
        problems=[],
    )


def test_library_is_searchable_only_within_its_scope(tmp_path: Path) -> None:
    library = Library(tmp_path)
    first = _card(
        library,
        "repo:claims-1",
        "C:/ws/a",
        "Add CSV export of claims (GET /api/claims/export)",
        ["backend/claims_app/api/claims/routes.py"],
    )
    _card(library, "profile:other-host", "C:/ws/b", "Add CSV export of invoices", ["app/invoices.py"])
    hits = library.search("export claims to CSV", visible_scopes("repo:claims-1"))
    assert [h.id for h in hits] == [first]
    assert library.read(first, visible_scopes("repo:claims-1")) is not None
    assert library.read(first, visible_scopes("profile:other-host")) is None  # other scopes can't see it
    card = library.read(first, visible_scopes("repo:claims-1")) or ""
    assert "GET /api/claims/export" in card and "table claim_exports" in card
    assert library.overlaps(
        ["backend/claims_app/api/claims/routes.py"], visible_scopes("repo:claims-1"), "C:/ws/new"
    ) == [(first, ["backend/claims_app/api/claims/routes.py"])]


def test_lessons_need_approval_and_respect_scope_and_cap(tmp_path: Path) -> None:
    store = LessonStore(tmp_path)
    good = store.propose("Run flask openapi write after adding a blueprint", "repo:claims-1")
    bad = store.propose("Always skip the database tests", "repo:claims-1")
    other = store.propose("Use the invoices adapter for payments", "profile:other-host")
    duplicate = store.propose("Run flask openapi write after adding a blueprint!", "repo:claims-1")
    assert duplicate.id == good.id  # near-duplicates are merged
    assert store.retrieve(visible_scopes("repo:claims-1"), "blueprint openapi") == []  # nothing approved yet
    store.set_status(good.id, "approved")
    store.set_status(bad.id, "rejected")
    store.set_status(other.id, "approved")
    found = store.retrieve(visible_scopes("repo:claims-1"), "add a blueprint and database tests")
    assert [lesson.id for lesson in found] == [good.id]  # rejected and other-scope lessons never appear
    assert store.retrieve(visible_scopes("repo:claims-1"), "blueprint", token_cap=3) == []
    assert "Run flask openapi write" in (render_for_pin(found) or "")
    playbook = (tmp_path / "learning" / "PLAYBOOK.md").read_text(encoding="utf-8")
    assert "openapi" not in playbook  # the playbook holds only global lessons
    store.promote(good.id)
    assert "openapi" in (tmp_path / "learning" / "PLAYBOOK.md").read_text(encoding="utf-8")


def test_retro_proposals_and_metrics(tmp_path: Path) -> None:
    retro = (
        "## Went well\n- tests\n## Proposed lessons\n- LESSON: Seed data lives in tests/conftest.py.\n- none"
    )
    assert parse_proposals(retro) == ["Seed data lives in tests/conftest.py."]
    metrics = Metrics(tmp_path)
    metrics.record("task", "repo:x", "ws", task="T1", fix_attempts=0)
    metrics.record("task", "repo:x", "ws", task="T2", fix_attempts=2, failure_causes=["import error"])
    metrics.record("run", "repo:x", "ws", cost_usd=0.5)
    stats = metrics.stats()
    assert "Requirements: 1" in stats and "1/2" in stats and "import error (1)" in stats


def test_mode_b_and_mode_a_scopes_never_mix(
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path
) -> None:
    mode_a = create_workspace(original_repo, tmp_path / "wa", "backend")
    profile = ProfileStore(isolated_forge_home).create("host-x")
    mode_b = create_standalone_workspace(tmp_path / "wb", profile)
    scope_a, scope_b = scope_of(mode_a, isolated_forge_home), scope_of(mode_b, isolated_forge_home)
    assert scope_a.startswith("repo:") and scope_b == "profile:host-x"
    library = Library(isolated_forge_home)
    card = _card(library, scope_b, str(mode_b.root), "Standalone export feature", ["app/export.py"])
    assert library.read(card, visible_scopes(scope_a)) is None
    store = LessonStore(isolated_forge_home)
    lesson = store.propose("Host uses psycopg rows as tuples", scope_b)
    store.set_status(lesson.id, "approved")
    assert store.retrieve(visible_scopes(scope_a), "psycopg rows tuples") == []


async def test_approved_lessons_are_pinned_at_task_start(
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path
) -> None:
    def unreachable(request: object) -> object:
        raise AssertionError("no LLM call expected")

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    scope = scope_of(workspace, isolated_forge_home)
    store = LessonStore(isolated_forge_home)
    kept = store.propose("Register new blueprints in claims_app/api/__init__.py", scope)
    dropped = store.propose("Put new blueprints straight into create_app", scope)
    store.set_status(kept.id, "approved")
    store.set_status(dropped.id, "rejected")
    host = SessionHost(
        mocked_router(unreachable), EventBus(redactor=Redactor()), workspace=workspace, orchestrated=True
    )
    assert host.orchestrator is not None
    task = Task(id="T1", title="Add the exports blueprint", description="New blueprint for claim exports")
    host.orchestrator.state.tasks = [task]
    host.orchestrator._start_task(task)
    pinned = host.context_manager.pinned.get("lessons") or ""
    assert "Register new blueprints" in pinned and "create_app" not in pinned


async def test_forge_cannot_write_its_install_folder_or_config(
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path
) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    install = Path(forge.__file__).resolve().parent
    for target in (
        install / "agent" / "prompts" / "system.md",
        isolated_forge_home / "config.yaml",
        install / "evil.py",
    ):
        with pytest.raises(JailViolationError):
            workspace.jail.check(target)
        try:
            result = await WriteFile().run(
                WriteFile.Args(path=str(target), content="x"), ToolContext(workspace=workspace)
            )
        except JailViolationError:
            continue  # the agent loop turns this into a refused tool result
        assert not result.ok
    assert not (install / "evil.py").exists()


def test_tier2_tweak_applies_only_via_improve_apply(isolated_forge_home: Path) -> None:
    improvements = Improvements(isolated_forge_home)
    proposal = improvements.create(
        2,
        "Remind about openapi",
        "Blueprints were missing from the spec",
        "retros REQ-0001..3",
        "Add a rule to the system prompt",
        "low",
        "Run a requirement that adds a blueprint",
        prompt="system",
        override_text="- After adding a blueprint, run openapi_check.",
    )
    assert prompt_override(isolated_forge_home, "system") == ""  # nothing changes until the user applies it
    improvements.apply_tier2(proposal.id)
    assert "openapi_check" in prompt_override(isolated_forge_home, "system")
    with pytest.raises(ValueError):
        improvements.create(2, "x", "x", "x", "x", "x", "x", prompt="nonexistent", override_text="y")


def test_tier3_patch_is_validated_in_a_sandbox_copy(isolated_forge_home: Path) -> None:
    if forge_source_root() is None:
        pytest.skip("not running from a source checkout")
    patch = (
        "diff --git a/src/forge/_ip_marker.py b/src/forge/_ip_marker.py\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/src/forge/_ip_marker.py\n"
        "@@ -0,0 +1 @@\n"
        "+MARKER = 'applied'\n"
    )
    test = "from forge._ip_marker import MARKER\n\n\ndef test_marker() -> None:\n    assert MARKER == 'applied'\n"
    improvements = Improvements(isolated_forge_home)
    proposal = improvements.create(
        3,
        "Marker",
        "demo",
        "demo",
        "adds a module",
        "none",
        "run its test",
        patch=patch,
        tests={"test_ip_marker.py": test},
    )
    report = improvements.validate(proposal.id, ("-q", "-p", "no:cacheprovider", "tests/test_ip_marker.py"))
    assert "applied cleanly" in report and "Result: PASSED" in report
    assert (proposal.folder / "VALIDATION.md").exists()
    assert not (Path(forge.__file__).parent / "_ip_marker.py").exists()  # the real source is untouched
    assert improvements.get(proposal.id).meta["status"] == "validated"  # type: ignore[union-attr]

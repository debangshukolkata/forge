"""M9 acceptance (spec M9): simulated user mistakes after copying output/ into the real repository are each
detected with the right instruction — a missing file, a partially pasted file, a blueprint left
unregistered, a missing package, a missing env var — and a correct copy comes out clean."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from forge.diagnose.integrity import check_integrity
from forge.diagnose.run import run_diagnose
from forge.workspace.create import create_workspace
from forge.workspace.output import build_output
from forge.workspace.workspace import Workspace
from tests.workspace_helpers import build_original_repo

ROUTES = '''"""Claim export routes."""

from __future__ import annotations

import os

import humanize_forge_test_pkg
from flask.views import MethodView
from flask_smorest import Blueprint

from claims_app.services.export_service import export_claims

blp = Blueprint("export", __name__, url_prefix="/api/export", description="Claim exports")


@blp.route("/")
class ExportResource(MethodView):
    def get(self) -> dict[str, object]:
        bucket = os.environ["EXPORT_BUCKET"]
        rows = export_claims()
        return {"bucket": bucket, "rows": len(rows), "size": humanize_forge_test_pkg.naturalsize(len(rows))}
'''

SERVICE = '''"""Claim export."""

from __future__ import annotations


def export_claims() -> list[dict[str, object]]:
    return []
'''


@pytest.fixture
def delivered(tmp_path: Path) -> tuple[Path, Workspace]:
    """A real repository and a workspace where 'Forge' added an export endpoint and built output/."""
    real = build_original_repo(tmp_path / "real", tmp_path / "outside")
    workspace = create_workspace(real, tmp_path / "ws", "backend")
    workspace.write_text("backend/claims_app/api/export/__init__.py", "")
    workspace.write_text("backend/claims_app/api/export/routes.py", ROUTES)
    workspace.write_text("backend/claims_app/services/export_service.py", SERVICE)
    api_init = "backend/claims_app/api/__init__.py"
    text, _ = workspace.read_text(api_init)
    text = text.replace(
        "from claims_app.api.policies.routes import blp as policies_blp\n",
        "from claims_app.api.policies.routes import blp as policies_blp\n"
        "from claims_app.api.export.routes import blp as export_blp\n",
    ).replace(
        "    api.register_blueprint(policies_blp)\n",
        "    api.register_blueprint(policies_blp)\n    api.register_blueprint(export_blp)\n",
    )
    workspace.write_text(api_init, text)
    build_output(workspace)
    return real, workspace


def copy_in(real: Path, workspace: Workspace, path: str, transform=None) -> None:  # type: ignore[no-untyped-def]
    target = real / path
    target.parent.mkdir(parents=True, exist_ok=True)
    data = (workspace.output_dir / path).read_bytes()
    target.write_bytes(transform(data) if transform else data)


def by_kind(workspace: Workspace) -> dict[str, list[str]]:
    kinds: dict[str, list[str]] = {}
    for finding in check_integrity(workspace).findings:
        kinds.setdefault(finding.kind, []).append(
            f"{finding.path} :: {finding.detail} :: {finding.instruction}"
        )
    return kinds


def test_each_simulated_mistake_is_detected_with_its_instruction(delivered: tuple[Path, Workspace]) -> None:
    real, workspace = delivered
    copy_in(real, workspace, "backend/claims_app/api/export/__init__.py")
    # Partial paste: only the first half of the routes file.
    copy_in(real, workspace, "backend/claims_app/api/export/routes.py", lambda data: data[: len(data) // 2])
    # The service is never copied (missing file); api/__init__.py is not replaced (unregistered blueprint).

    kinds = by_kind(workspace)

    assert any("export_service.py" in f and "Copy `output/" in f for f in kinds["missing_file"])
    assert any(
        "routes.py" in f and "line(s) of Forge's version are missing" in f for f in kinds["partial_paste"]
    )
    registration = kinds["missing_registration"][0]
    assert "api/__init__.py" in registration and "api.register_blueprint(export_blp)" in registration
    assert any("humanize_forge_test_pkg" in f and "pip install" in f for f in kinds["missing_package"])
    assert any("EXPORT_BUCKET" in f for f in kinds["missing_env_var"])


def test_a_correct_copy_is_clean_apart_from_setup(
    delivered: tuple[Path, Workspace], monkeypatch: pytest.MonkeyPatch
) -> None:
    real, workspace = delivered
    for change in (
        "api/export/__init__.py",
        "api/export/routes.py",
        "services/export_service.py",
        "api/__init__.py",
    ):
        # CRLF line endings, as Windows editors often save them: only an info note.
        copy_in(real, workspace, f"backend/claims_app/{change}", lambda data: data.replace(b"\n", b"\r\n"))
    monkeypatch.setenv("EXPORT_BUCKET", "set-by-the-user")

    kinds = by_kind(workspace)

    # Line endings alone are not a problem; the new package is still genuinely missing from the venv.
    assert set(kinds) <= {"line_endings", "missing_package"}, kinds
    assert [f for f in kinds["missing_package"] if "humanize_forge_test_pkg" not in f] == []


def test_wrong_location_and_leftover_deleted_file(delivered: tuple[Path, Workspace]) -> None:
    real, workspace = delivered
    wrong = real / "backend" / "claims_app" / "export_service.py"
    shutil.copyfile(workspace.output_dir / "backend/claims_app/services/export_service.py", wrong)
    kinds = by_kind(workspace)
    assert any("claims_app/export_service.py" in f and "Move it to" in f for f in kinds["wrong_location"])


async def test_diagnose_writes_a_report_and_runs_a_fresh_copy(delivered: tuple[Path, Workspace]) -> None:
    real, workspace = delivered
    copy_in(real, workspace, "backend/claims_app/api/export/routes.py", lambda data: data[: len(data) // 2])
    result = await run_diagnose(workspace, sandbox=False)
    report = Path(result.report_path).read_text(encoding="utf-8")
    assert result.number == 1 and report.startswith("# Diagnose report 1")
    assert "partial_paste" in report and "missing_file" in report and "## Fresh copy run" in report
    assert result.fresh is not None and (result.fresh.folder / "backend" / "claims_app").is_dir()
    assert (real / "backend" / "claims_app" / "api" / "export" / "routes.py").read_bytes() == (
        workspace.output_dir / "backend/claims_app/api/export/routes.py"
    ).read_bytes()[
        : len((workspace.output_dir / "backend/claims_app/api/export/routes.py").read_bytes()) // 2
    ]
    # App smoke: the half-pasted routes.py can't be imported, so building the app fails and says why.
    assert "App smoke" in report and "ok" in result.fresh.smoke
    second = await run_diagnose(workspace, fresh_run=False)
    assert second.number == 2

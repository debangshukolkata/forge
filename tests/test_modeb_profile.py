"""M10B: the structure export script (no code leaves the host) and the Host Profile store."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from forge.modeb import forge_structure_export as exporter
from forge.modeb.profile import ProfileError, ProfileStore
from tests.conftest import FIXTURE_BACKEND

LITERALS_IN_FIXTURE = ["Claim amount must be greater than zero", "CLM-", "test-jwt-secret-for-fixture"]


@pytest.fixture
def export_data(tmp_path: Path) -> dict[str, object]:
    out = tmp_path / "structure_export"
    subprocess.run(
        [sys.executable, exporter.__file__, str(FIXTURE_BACKEND), "--out", str(out)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads((tmp_path / "structure_export.json").read_text(encoding="utf-8"))


def test_export_has_structure_but_no_code(export_data: dict[str, object]) -> None:
    text = json.dumps(export_data)
    for literal in LITERALS_IN_FIXTURE:
        assert literal not in text, literal
    assert "session_scope" in text and "(page - 1) * page_size" not in text  # signatures yes, bodies no
    modules = export_data["modules"]
    routes = modules["claims_app/api/claims/routes.py"]["blueprints"][0]  # type: ignore[index]
    assert routes["url_prefix"] == "/api/claims" and routes["routes"]
    assert "DB_PASSWORD" in modules["claims_app/config.py"]["env_keys"]  # type: ignore[index]  # name only
    assert export_data["packages"]["flask-smorest"].startswith("==")  # type: ignore[index]
    assert export_data["not_exported"] == ["<1 secret-looking file(s)>"]  # backend/.env: not even listed
    assert ".env" not in export_data["tree"]  # type: ignore[operator]


def test_mask_replaces_terms_consistently(tmp_path: Path) -> None:
    source = tmp_path / "app"
    shutil.copytree(FIXTURE_BACKEND / "claims_app", source / "claims_app")
    terms = tmp_path / "terms.txt"
    terms.write_text("claims\n", encoding="utf-8")
    out = tmp_path / "masked"
    subprocess.run(
        [sys.executable, exporter.__file__, str(source), "--out", str(out), "--mask", str(terms)], check=True
    )
    text = (tmp_path / "masked.json").read_text(encoding="utf-8")
    assert "claims" not in text.lower() and "TERM1_app" in text


def test_profile_import_search_and_changes(export_data: dict[str, object], isolated_forge_home: Path) -> None:
    store = ProfileStore(isolated_forge_home)
    profile = store.create("claims-host", sensitive_terms=["ACME Insurance"])
    report = profile.import_structure(export_data)  # type: ignore[arg-type]
    assert report.modules > 10 and not report.changed
    hits = profile.search("register blueprint policies route")
    assert hits and any("policies" in path for path, _ in hits)
    assert all("def " in text or "blueprint" in text or "class" in text for _, text in hits)

    changed = json.loads(json.dumps(export_data))
    changed["modules"]["claims_app/db.py"]["functions"] = []  # type: ignore[index]
    second = profile.import_structure(changed)
    assert second.changed == ["claims_app/db.py"] and profile.version == 3
    assert "structure export imported" in (profile.root / "CHANGELOG.md").read_text(encoding="utf-8")
    assert store.names() == ["claims-host"] and store.open("claims-host").version == 3
    with pytest.raises(ProfileError):
        store.open("../../etc")
    with pytest.raises(ProfileError):
        profile.import_structure({"format": "something else"})


def test_exemplars_are_cleaned_and_can_be_forgotten(isolated_forge_home: Path) -> None:
    profile = ProfileStore(isolated_forge_home).create("host", sensitive_terms=["ACME"])
    fake_key = "sk-live-0123456789abcdefghijklmnop"  # check_secrets: fake
    snippet = f'class ItemsView(MethodView):\n    """ACME items."""\n    API_KEY = "{fake_key}"\n'
    exemplar_id, changed = profile.add_exemplar(snippet, "MethodView blueprint pattern (ACME)")
    stored = profile.read_exemplar(exemplar_id) or ""
    assert changed and "ACME" not in stored and "<term1>" in stored
    assert profile.exemplars()[0][0] == exemplar_id and "essentials" not in stored
    assert "Exemplars" in profile.essentials()
    assert profile.forget_exemplar(exemplar_id) and profile.exemplars() == []
    assert not profile.forget_exemplar("../PROFILE")

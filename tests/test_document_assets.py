"""D-347: Word templates and starting outlines are catalogue assets: found, copied into the project, and they build."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge.parity.assets import build_catalogue, catalogue_files
from forge.toolkit.base import ToolContext
from forge.tools.assets import AddAsset, FindAsset
from forge.workspace.create import create_workspace

pytest.importorskip("docx")
pytest.importorskip("openpyxl")
pytest.importorskip("reportlab")
SKILLS = Path(__file__).resolve().parent.parent / "src" / "forge" / "skills"


@pytest.mark.parametrize("skill", ["make-document", "make-spreadsheet", "pdf-toolkit"])
def test_the_committed_catalogues_are_valid_and_up_to_date(skill: str) -> None:
    result = build_catalogue(SKILLS / skill)
    assert result.errors == [] and result.assets
    for name, text in catalogue_files(result).items():
        committed = (SKILLS / skill / "assets" / name).read_text(encoding="utf-8").replace("\r\n", "\n")
        assert committed == text, (
            f"{skill}/assets/{name} is out of date: run scripts/build_asset_catalogue.py"
        )


async def test_a_template_is_found_copied_and_used_to_build_a_document(
    original_repo: Path, tmp_path: Path
) -> None:
    from forge.tools.document import BuildDocument

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace)
    found = await FindAsset().run(
        FindAsset.Args(query="business report with a table", type="template"), context
    )
    assert found.ok and "tpl-doc-report-clean" in found.content
    added = await AddAsset().run(AddAsset.Args(id="tpl-doc-report-clean"), context)
    assert added.ok, added.content
    assert workspace.path_of("docs/templates/report-clean.docx").read_bytes().startswith(b"PK")
    outline = {
        "title": "Sales",
        "template": "docs/templates/report-clean.docx",
        "blocks": [{"type": "heading", "text": "Hello"}],
    }
    workspace.write_text("docs/o.json", json.dumps(outline), "x")
    built = await BuildDocument().run(
        BuildDocument.Args(outline="docs/o.json", output="docs/out.docx"), context
    )
    assert built.ok, built.content
    from forge.documents.read import read_document

    text = read_document(workspace.path_of("docs/out.docx").read_bytes()).markdown
    assert "Hello" in text and "State the one thing" not in text  # the template's sample text is gone


def test_the_starting_outlines_build_without_formula_faults() -> None:
    from forge.pdfs.build import build_pdf, parse_pdf_spec
    from forge.sheets.build import build_workbook
    from forge.sheets.check import check_workbook
    from forge.sheets.spec import parse_workbook

    for name in ("budget", "tracker"):
        data = build_workbook(
            parse_workbook(
                (SKILLS / "make-spreadsheet" / "templates" / f"{name}.json").read_text(encoding="utf-8")
            )
        )
        assert [f for f in check_workbook(data) if f.level == "error"] == [] and not [
            f for f in check_workbook(data)
        ]
    pdf = build_pdf(
        parse_pdf_spec((SKILLS / "pdf-toolkit" / "templates" / "handout.json").read_text(encoding="utf-8")),
        lambda n: b"",
    )
    assert pdf.startswith(b"%PDF")

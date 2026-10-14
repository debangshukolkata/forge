"""D-350: the catalogue of tokenised design systems is valid, searchable and can be added to a project."""

from __future__ import annotations

from pathlib import Path

from forge.designsystem.lint import lint_text
from forge.designsystem.novelty import fingerprint, is_different_enough
from forge.designsystem.spec import parse_design_md
from forge.parity.assets import build_catalogue
from forge.toolkit.base import ToolContext
from forge.tools.assets import AddAsset, FindAsset
from forge.workspace.create import create_workspace

SKILL = Path(__file__).resolve().parent.parent / "src" / "forge" / "skills" / "ui-design-quality"
SYSTEMS = sorted((SKILL / "recipes" / "design-systems").glob("*.design.md"))


def test_every_catalogue_system_is_a_clean_design_md_with_a_picture() -> None:
    assert len(SYSTEMS) >= 14
    for path in SYSTEMS:
        findings = [
            f for f in lint_text(path.read_text(encoding="utf-8")) if f.severity in ("error", "warning")
        ]
        assert findings == [], (path.name, findings)
        assert (
            SKILL / "assets" / "preview" / f"{path.name.removesuffix('.design.md')}-specimen.jpg"
        ).is_file()
    assert {a.id for a in build_catalogue(SKILL).assets if a.type == "design-system"} == {
        p.name.removesuffix(".design.md") for p in SYSTEMS
    }


def test_the_catalogue_offers_real_variety() -> None:
    prints = {p.name: fingerprint(parse_design_md(p.read_text(encoding="utf-8"))) for p in SYSTEMS}
    assert {f.tone for f in prints.values()} == {"light", "dark"} and len(
        {f.accent_hue for f in prints.values()}
    ) >= 5
    assert len({f.display_font for f in prints.values()}) >= 8
    assert is_different_enough(prints["ds-dark-dashboard.design.md"], prints["ds-soft-editorial.design.md"])
    assert is_different_enough(prints["ds-bold-poster.design.md"], prints["ds-clean-product.design.md"])


async def test_a_system_is_found_by_what_the_product_needs_and_added_as_the_projects_design_md(
    original_repo: Path, tmp_path: Path
) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace)
    found = await FindAsset().run(
        FindAsset.Args(query="dark analytics dashboard monitoring", type="design-system"), context
    )
    assert found.ok and "ds-dark-dashboard" in found.content
    added = await AddAsset().run(AddAsset.Args(id="ds-dark-dashboard"), context)
    assert added.ok, added.content
    text = workspace.path_of("DESIGN.md").read_text(encoding="utf-8")
    assert "name: Dark dashboard" in text and "dials:" in text

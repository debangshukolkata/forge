"""D-490: palettes the user can choose from, applied to a DESIGN.md; a colour the owner accepted below the contrast guideline is left alone by the lint and the audit."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.designsystem.lint import lint_text
from forge.designsystem.palettes import (
    PAGES,
    PALETTES,
    accepted_backgrounds,
    apply_palette,
    custom_palette,
    palette_by_id,
)
from forge.toolkit.base import ToolContext
from forge.tools.design_palette import DesignPalette, palette_html
from forge.workspace.create import create_workspace

SKILL = Path(__file__).resolve().parent.parent / "src" / "forge" / "skills" / "ui-design-quality"
OFFICE = (SKILL / "recipes" / "design-systems" / "ds-office-polish.design.md").read_text(encoding="utf-8")


def test_every_palette_passes_white_text_except_the_bright_orange_the_owner_asked_for() -> None:
    below = [p.id for p in PALETTES if p.below_aa]
    assert below == ["orange-bright"], below
    assert all(p.ratio >= 4.5 for p in PALETTES if p.id != "orange-bright")
    assert {i for page in PAGES for i in page} == {p.id for p in PALETTES}
    assert all(len(page) <= 4 for page in PAGES)  # ask_user shows at most four options


def test_applying_a_palette_changes_only_the_colour_roles_and_the_primary_button() -> None:
    blue = palette_by_id("blue")
    assert blue is not None
    after = apply_palette(OFFICE, blue)
    assert 'primary: "#2563EB"' in after and 'brand: "#2563EB"' in after and "contrast-accepted" not in after
    assert [f for f in lint_text(after) if f.severity in ("error", "warning")] == []
    assert after.count("## ") == OFFICE.count("## ")  # the prose is untouched


def test_the_bright_orange_is_recorded_as_accepted_and_the_lint_leaves_it_alone() -> None:
    orange = palette_by_id("orange-bright")
    assert orange is not None
    after = apply_palette(OFFICE, orange)
    assert accepted_backgrounds(after)[0] == "#FF7A00" and len(accepted_backgrounds(after)) == 2
    findings = lint_text(after)
    assert [f for f in findings if f.severity == "error"] == []
    assert any(f.rule == "contrast-accepted" for f in findings)
    # without the note the same colours are an error
    without = "\n".join(line for line in after.split("\n") if not line.startswith("contrast-accepted"))
    assert any(f.severity == "error" and f.rule == "low-contrast" for f in lint_text(without))
    # choosing a palette that passes removes the note again
    assert accepted_backgrounds(apply_palette(after, palette_by_id("teal"))) == []  # type: ignore[arg-type]


def test_a_custom_colour_gets_readable_text_and_a_bad_one_is_refused() -> None:
    dark = custom_palette("#0A84FF")
    assert dark is not None and dark.primary == "#0A84FF" and dark.brand == "#0A84FF"
    pale = custom_palette("FFE08A", "#FFB000")
    assert pale is not None and pale.on_primary == "#111111" and pale.brand == "#FFB000"
    assert (
        custom_palette("blue") is None
        and custom_palette("#12345") is None
        and custom_palette("#0A84FF", "nope") is None
    )


def test_the_palette_picture_names_the_colours_and_the_contrast() -> None:
    html = palette_html(palette_by_id("orange-bright"))  # type: ignore[arg-type]
    assert "#FF7A00" in html and "below the 4.5 guideline" in html
    assert "below the 4.5" not in palette_html(palette_by_id("teal"))  # type: ignore[arg-type]


@pytest.fixture
def context(original_repo: Path, tmp_path: Path) -> ToolContext:
    return ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))


async def test_the_tool_applies_a_palette_to_the_project_design_md(context: ToolContext) -> None:
    context.workspace.write_text("DESIGN.md", OFFICE, "x")
    tool = DesignPalette()
    result = await tool.run(DesignPalette.Args(action="apply", palette="green"), context)
    assert result.ok and "Applied the Green palette" in result.content
    assert 'primary: "#15803D"' in context.workspace.path_of("DESIGN.md").read_text(encoding="utf-8")
    custom = await tool.run(DesignPalette.Args(action="apply", primary="#7C3AED", brand="#A78BFA"), context)
    assert custom.ok and "Your colour" in custom.content
    orange = await tool.run(DesignPalette.Args(action="apply", palette="orange-bright"), context)
    assert orange.ok and "recorded as accepted" in orange.content
    missing = await tool.run(DesignPalette.Args(action="apply", palette="nope"), context)
    assert not missing.ok and "orange-bright" in missing.content
    absent = await tool.run(
        DesignPalette.Args(action="apply", palette="blue", path="nothing/DESIGN.md"), context
    )
    assert not absent.ok and "No DESIGN.md" in absent.content


@pytest.mark.e2e
async def test_showing_the_palettes_draws_four_pictures_and_says_how_to_ask(context: ToolContext) -> None:
    pytest.importorskip("playwright.async_api")
    result = await DesignPalette().run(DesignPalette.Args(action="show"), context)
    assert result.ok, result.content
    for identifier in PAGES[0]:
        assert (context.workspace.root / ".forge" / "palettes" / f"{identifier}.png").is_file()
        assert f"`{identifier}`" in result.content
    assert (
        "ONE ask_user call" in result.content
        and "page=2" in result.content
        and "below 4.5 to 1" in result.content
    )
    assert (
        "page=3"
        not in (await DesignPalette().run(DesignPalette.Args(action="show", page=3), context)).content
    )

"""D-354: the plain-HTML composition recipes render cleanly at desktop and phone width and are in the catalogue."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.tools.ui_audit import AUDIT_SCRIPT

SKILL = Path(__file__).resolve().parent.parent / "src" / "forge" / "skills" / "ui-design-quality"
FILES = sorted((SKILL / "recipes" / "compositions").glob("*.html"))


def test_there_are_seven_compositions_each_in_the_catalogue_with_pictures() -> None:
    from forge.parity.assets import build_catalogue

    assert len(FILES) == 7
    ids = {
        a.id
        for a in build_catalogue(SKILL).assets
        if a.type == "section" and a.id.startswith("lay-") and not a.id.startswith("lay-react-")
    }
    assert ids == {f"lay-{f.stem}" for f in FILES}
    for file in FILES:
        assert (SKILL / "assets" / "preview" / f"lay-{file.stem}-desktop.jpg").is_file()
        assert (SKILL / "assets" / "preview" / f"lay-{file.stem}-phone.jpg").is_file()


@pytest.mark.parametrize("file", FILES, ids=[f.stem for f in FILES])
def test_a_composition_has_no_sideways_scroll_and_a_clean_audit_at_both_widths(file: Path) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(channel="msedge", headless=True)
        except Exception as error:
            pytest.skip(str(error))
        try:
            for width in (1280, 375):
                page = browser.new_page(viewport={"width": width, "height": 800})
                page.goto(file.resolve().as_uri())
                page.wait_for_timeout(200)
                assert page.evaluate("document.documentElement.scrollWidth - window.innerWidth") <= 1, (
                    f"{file.stem} scrolls sideways at {width}"
                )
                if width == 1280:
                    findings = [
                        f for f in page.evaluate(AUDIT_SCRIPT)["findings"] if "system font stack" not in f
                    ]  # the recipes name their fonts; fetch_font brings them in
                    assert findings == [], (file.stem, findings)
                page.close()
        finally:
            browser.close()


async def test_a_composition_is_found_by_the_product_and_copied_into_the_project(
    original_repo: Path, tmp_path: Path
) -> None:
    from forge.toolkit.base import ToolContext
    from forge.tools.assets import AddAsset, FindAsset
    from forge.workspace.create import create_workspace

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    workspace.write_text(
        "DESIGN.md", "# Brand guide", "the design gate wants a DESIGN.md before a page is added"
    )
    context = ToolContext(workspace=workspace)
    found = await FindAsset().run(
        FindAsset.Args(query="late-night ramen bar japanese", type="section"), context
    )
    assert found.ok and "lay-vertical-type" in found.content
    added = await AddAsset().run(AddAsset.Args(id="lay-vertical-type"), context)
    assert added.ok, added.content
    assert "writing-mode:vertical-rl" in workspace.path_of("compositions/vertical-type.html").read_text(
        encoding="utf-8"
    )

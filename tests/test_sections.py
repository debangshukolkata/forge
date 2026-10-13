"""L1: every section and template builds with Vite + Tailwind v4, type-checks under strict TypeScript, passes the style audit at
1280 and 375 px without horizontal overflow or console errors, and the contact form really validates. Screenshots go to
test-artifacts/sections/. Skipped when ui-react/node_modules is not installed."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.toolkit.base import ToolContext
from forge.tools.assets import AddAsset
from forge.workspace.create import create_workspace
from tests import vite_harness as harness

RECIPES = Path(__file__).resolve().parents[1] / "src/forge/skills/ui-design-quality/recipes"
SHOTS = Path(__file__).resolve().parents[1] / "test-artifacts" / "sections"
TEMPLATES = ["tpl-landing-charity", "tpl-landing-saas", "tpl-landing-portfolio"]
SECTION_NAMES = sorted(p.stem for p in (RECIPES / "sections").glob("*.tsx"))

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not harness.available(), reason="ui-react/node_modules is not installed"),
]


def _check(result: dict[str, object]) -> None:
    assert result["errors"] == []
    for width in (1280, 375):
        assert "no measurable problems" in str(result["audit"][width]), result["audit"][width]  # type: ignore[index]
        assert result["overflow"][width] == 0, f"horizontal overflow at {width}px"  # type: ignore[index]


@pytest.mark.parametrize("template", TEMPLATES)
async def test_template_builds_and_passes_the_audit(
    template: str, tmp_path: Path, original_repo: Path
) -> None:
    context = ToolContext(
        workspace=create_workspace(original_repo, tmp_path / "ws", "backend"), design_first=False
    )
    added = await AddAsset().run(AddAsset.Args(id=template, project_dir="web"), context)
    assert added.ok, added.content
    web = context.workspace.repo_dir / "web"
    files: dict[str, str | bytes] = {}
    for path in web.rglob("*"):
        if path.is_file() and path.name != "NOTICES.md":
            relative = path.relative_to(web).as_posix()
            files[relative] = (
                path.read_bytes() if path.suffix == ".woff2" else path.read_text(encoding="utf-8")
            )
    assert "src/App.tsx" in files and "src/index.css" in files
    assert any(name.endswith(".woff2") for name in files)
    dist = harness.build(template, files, title=template)
    with harness.serve(dist) as url:
        result = await harness.audit(url, SHOTS, template)
    _check(result)


def _gallery() -> dict[str, str | bytes]:
    files: dict[str, str | bytes] = {
        "src/index.css": (RECIPES / "templates/charity/index.css").read_text(encoding="utf-8")
    }
    files["src/index.css"] = (
        str(files["src/index.css"])
        .replace('@import "./fonts/fraunces.css";\n', "")
        .replace('@import "./fonts/inter.css";\n', "")
    )
    for name in SECTION_NAMES:
        files[f"src/sections/{name}.tsx"] = (RECIPES / "sections" / f"{name}.tsx").read_text(encoding="utf-8")
    shown = [n for n in SECTION_NAMES if n != "ArtTile"]
    imports = "\n".join(f'import {n} from "./sections/{n}";' for n in shown)
    body = "\n".join(f"        <{n} />" for n in shown)
    files["src/App.tsx"] = (
        f"{imports}\n\nexport default function App() {{\n  return (\n    <>\n{body}\n    </>\n  );\n}}\n"
    )
    return files


async def test_all_sections_together_and_the_form_validates() -> None:
    from playwright.async_api import async_playwright

    dist = harness.build("gallery", _gallery(), title="Section gallery")
    with harness.serve(dist) as url:
        result = await harness.audit(url, SHOTS, "gallery")
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(channel="msedge", headless=True)
            page = await browser.new_page(viewport={"width": 1280, "height": 900})
            await page.goto(url)
            await page.click("text=Confirm my slot")
            assert await page.locator("#cf-name-error").inner_text() == "Please enter your full name."
            assert "asha@example.org" in await page.locator("#cf-email-error").inner_text()
            await page.fill("#cf-name", "Asha Roy")
            await page.fill("#cf-email", "asha@example.org")
            await page.click("text=Confirm my slot")
            await page.wait_for_selector("text=You are booked.")
            # FAQ answers are hidden until opened, and the first one opens with a click
            await page.click("summary:has-text('Who can donate?')")
            assert await page.locator("details[open]").count() == 1
            await browser.close()
    _check(result)

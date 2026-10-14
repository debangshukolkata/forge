"""D-377: the React versions of the application screens type-check, build with Vite, render like the HTML recipes (same text), and pass the style audit with no
sideways scroll at desktop and phone width."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests import vite_harness as harness

SKILL = Path(__file__).resolve().parent.parent / "src" / "forge" / "skills" / "ui-design-quality"
REACT = SKILL / "recipes" / "app-react"
IDS = ["dashboard-kpi", "table-data", "form-wizard", "settings-account", "inbox"]
SHOTS = Path(__file__).resolve().parent.parent / "test-artifacts" / "app-screens-react"

pytestmark = [
    pytest.mark.skipif(not harness.available(), reason="ui-react/node_modules is not installed"),
]


def project_files(screen_id: str) -> dict[str, str]:
    folder = REACT / screen_id
    return {
        "src/App.tsx": f'import Screen from "./screens/{screen_id}/Screen";\nexport default function App() {{\n  return <Screen />;\n}}\n',
        "src/index.css": (folder / "tokens.css").read_text(encoding="utf-8"),
        f"src/screens/{screen_id}/Screen.tsx": (folder / "Screen.tsx").read_text(encoding="utf-8"),
        f"src/screens/{screen_id}/screen.css": (folder / "screen.css").read_text(encoding="utf-8"),
    }


async def body_text(page: object, url: str) -> str:
    await page.goto(url)  # type: ignore[attr-defined]
    await page.wait_for_load_state("networkidle")  # type: ignore[attr-defined]
    return re.sub(r"\s+", " ", str(await page.evaluate("document.body.innerText"))).strip()  # type: ignore[attr-defined]


@pytest.mark.parametrize("screen_id", IDS)
async def test_a_react_screen_builds_audits_clean_and_shows_the_same_text_as_its_html_recipe(
    screen_id: str,
) -> None:
    from playwright.async_api import async_playwright

    dist = harness.build(f"app-react-{screen_id}", project_files(screen_id), title=screen_id)
    with harness.serve(dist) as url:
        result = await harness.audit(url, SHOTS, screen_id)
        assert result["errors"] == [], result["errors"]
        overflow: dict[int, int] = result["overflow"]  # type: ignore[assignment]
        assert all(value <= 1 for value in overflow.values()), (screen_id, overflow)
        audit_text: str = result["audit"][1280]  # type: ignore[index]
        problems = [
            line for line in audit_text.splitlines()[1:] if line.strip() and "system font stack" not in line
        ]
        assert problems == [], (screen_id, problems)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(channel="msedge", headless=True)
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            react_text = await body_text(page, url)
            html_text = await body_text(
                page, (SKILL / "recipes" / "app-screens" / f"{screen_id}.html").resolve().as_uri()
            )
            await browser.close()
        assert react_text == html_text, (screen_id, react_text[:200], html_text[:200])


def test_every_react_screen_is_in_the_catalogue_with_its_three_files() -> None:
    from forge.parity.assets import build_catalogue

    assets = {a.id: a for a in build_catalogue(SKILL).assets}
    for screen_id in IDS:
        asset = assets[f"app-react-{screen_id}"]
        assert [Path(f["to"]).name for f in asset.files] == ["Screen.tsx", "screen.css", "tokens.css"]
        assert "react" in asset.tags and "app screen" in asset.tags

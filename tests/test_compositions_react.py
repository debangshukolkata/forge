"""D-398: the React versions of the seven compositions type-check, build with Vite, audit clean at both widths and show the same text as their HTML recipes."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests import vite_harness as harness

SKILL = Path(__file__).resolve().parent.parent / "src" / "forge" / "skills" / "ui-design-quality"
REACT = SKILL / "recipes" / "compositions-react"
IDS = sorted(folder.name for folder in REACT.iterdir() if folder.is_dir())
SHOTS = Path(__file__).resolve().parent.parent / "test-artifacts" / "compositions-react"

pytestmark = [
    pytest.mark.skipif(not harness.available(), reason="ui-react/node_modules is not installed"),
]


def project_files(name: str) -> dict[str, str]:
    folder = REACT / name
    return {
        "src/App.tsx": "\n".join(
            [
                f'import Composition from "./compositions/{name}/Composition";',
                "export default function App() {",
                "  return <Composition />;",
                "}",
                "",
            ]
        ),
        "src/index.css": "",
        f"src/compositions/{name}/Composition.tsx": (folder / "Composition.tsx").read_text(encoding="utf-8"),
        f"src/compositions/{name}/composition.css": (folder / "composition.css").read_text(encoding="utf-8"),
        f"src/compositions/{name}/tokens.css": (folder / "tokens.css").read_text(encoding="utf-8"),
    }


async def body_text(page: object, url: str) -> str:
    await page.goto(url)  # type: ignore[attr-defined]
    await page.wait_for_load_state("networkidle")  # type: ignore[attr-defined]
    return re.sub(r"\s+", " ", str(await page.evaluate("document.body.innerText"))).strip()  # type: ignore[attr-defined]


def test_there_is_a_react_version_of_every_composition_in_the_catalogue() -> None:
    from forge.parity.assets import build_catalogue

    assert len(IDS) == 8
    assets = {a.id: a for a in build_catalogue(SKILL).assets}
    for name in IDS:
        asset = assets[f"lay-react-{name}"]
        assert [Path(f["to"]).name for f in asset.files] == [
            "Composition.tsx",
            "composition.css",
            "tokens.css",
        ]
        assert "react" in asset.tags and "composition" in asset.tags


@pytest.mark.parametrize("name", IDS)
async def test_a_react_composition_builds_audits_clean_and_shows_the_same_text_as_its_html_recipe(
    name: str,
) -> None:
    from playwright.async_api import async_playwright

    dist = harness.build(f"comp-react-{name}", project_files(name), title=name)
    with harness.serve(dist) as url:
        result = await harness.audit(url, SHOTS, name)
        assert result["errors"] == [], result["errors"]
        overflow: dict[int, int] = result["overflow"]  # type: ignore[assignment]
        assert all(value <= 1 for value in overflow.values()), (name, overflow)
        audit_text: str = result["audit"][1280]  # type: ignore[index]
        problems = [
            line
            for line in audit_text.splitlines()[1:]
            if line.strip()
            and "system font stack" not in line
            and "only picture is a drawn motif" not in line
        ]  # the recipes name their fonts and draw a stand-in motif for the product's own picture
        assert problems == [], (name, problems)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(channel="msedge", headless=True)
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            react_text = await body_text(page, url)
            html_text = await body_text(
                page, (SKILL / "recipes" / "compositions" / f"{name}.html").resolve().as_uri()
            )
            await browser.close()
        assert react_text == html_text, (name, react_text[:200], html_text[:200])

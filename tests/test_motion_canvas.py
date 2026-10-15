"""D-384: the beam, the particles and the globe type-check and build with Vite; in Edge the beam draws a path with a moving light, the particles and the globe paint pixels and keep
changing, and under reduced motion they are drawn once and then stay still."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests import vite_harness as harness

RECIPES = (
    Path(__file__).resolve().parent.parent / "src" / "forge" / "skills" / "ui-design-quality" / "recipes"
)
pytestmark = [pytest.mark.skipif(not harness.available(), reason="ui-react/node_modules is not installed")]

APP = """import { useRef } from "react";
import { AnimatedBeam, GlobeLite, Particles } from "./motion-canvas";

export default function App() {
  const box = useRef<HTMLDivElement>(null);
  const a = useRef<HTMLDivElement>(null);
  const b = useRef<HTMLDivElement>(null);
  return (
    <main style={{ padding: 24, font: "16px system-ui" }}>
      <div ref={box} id="beam-box" style={{ position: "relative", display: "flex", justifyContent: "space-between", width: 500, height: 160, alignItems: "center" }}>
        <div ref={a} id="a" style={{ width: 60, height: 60, borderRadius: 30, background: "#c7d2fe" }} />
        <div ref={b} id="b" style={{ width: 60, height: 60, borderRadius: 30, background: "#fde68a" }} />
        <AnimatedBeam containerRef={box} fromRef={a} toRef={b} />
      </div>
      <div id="hero" style={{ width: 500, height: 220, border: "1px solid #ddd" }}><Particles count={50} /></div>
      <GlobeLite size={240} />
    </main>
  );
}
"""


def files() -> dict[str, str]:
    return {
        "src/App.tsx": APP,
        "src/index.css": ":root{--color-primary:#4f46e5}body{margin:0}",
        "src/motion-canvas.tsx": (RECIPES / "motion-canvas.tsx").read_text(encoding="utf-8"),
    }


@pytest.fixture(scope="module")
def site() -> str:
    dist = harness.build("motion-canvas", files(), title="Motion canvas")
    with harness.serve(dist) as url:
        yield url  # type: ignore[misc]


PIXELS = "(sel) => { const c = document.querySelector(sel); const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0, h = 0; for (let i = 3; i < d.length; i += 4) { if (d[i] > 0) n++; h = (h * 31 + d[i - 3] + d[i]) % 1000003; } return [n, h]; }"


async def run(site: str, reduced: bool) -> dict[str, object]:
    from playwright.async_api import async_playwright

    out: dict[str, object] = {}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="msedge", headless=True)
        page = await browser.new_page(
            viewport={"width": 700, "height": 900}, reduced_motion="reduce" if reduced else "no-preference"
        )
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(site)
        await page.wait_for_timeout(700)
        out["paths"] = await page.evaluate("document.querySelectorAll('svg.beam path').length")
        out["animates"] = await page.evaluate("document.querySelectorAll('svg.beam animate').length")
        out["aria"] = await page.evaluate(
            "[...document.querySelectorAll('svg.beam, canvas')].every(e => e.getAttribute('aria-hidden') === 'true')"
        )
        first = {k: await page.evaluate(PIXELS, f"canvas.{k}") for k in ("particles", "globe-lite")}
        await page.wait_for_timeout(500)
        second = {k: await page.evaluate(PIXELS, f"canvas.{k}") for k in ("particles", "globe-lite")}
        out["painted"] = {k: first[k][0] > 20 for k in first}
        out["changed"] = {k: first[k][1] != second[k][1] for k in first}
        out["errors"] = errors
        await browser.close()
    return out


async def test_the_effects_draw_and_keep_moving(site: str) -> None:
    seen = await run(site, reduced=False)
    assert seen["errors"] == [] and seen["aria"] is True
    assert seen["paths"] == 2 and seen["animates"] == 1  # the line and the travelling light
    assert seen["painted"] == {"particles": True, "globe-lite": True}
    assert seen["changed"] == {"particles": True, "globe-lite": True}


async def test_under_reduced_motion_they_are_drawn_once_and_stay_still(site: str) -> None:
    seen = await run(site, reduced=True)
    assert seen["errors"] == []
    assert seen["paths"] == 1 and seen["animates"] == 0  # a still line
    assert seen["painted"] == {"particles": True, "globe-lite": True}
    assert seen["changed"] == {"particles": False, "globe-lite": False}

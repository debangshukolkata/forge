"""L6: the showpiece effects (motion-fancy.css) do what they say in Edge, without console errors, and stop under reduced motion."""

from __future__ import annotations

import functools
import http.server
import shutil
import threading
from pathlib import Path

import pytest

RECIPES = Path(__file__).resolve().parents[1] / "src" / "forge" / "skills" / "ui-design-quality" / "recipes"
ARTIFACTS = Path(__file__).resolve().parents[1] / "test-artifacts" / "motion"

CELLS = "".join("<i></i>" for _ in range(48))
PAGE = f"""<!doctype html><meta charset="utf-8"><title>Motion kit part 3</title><link rel="icon" href="data:,">
<link rel="stylesheet" href="motion-fancy.css">
<style>
 body {{ font: 16px system-ui; margin: 0; padding: 24px; background: #f8fafc; color: #0f172a; }}
 section {{ margin: 0 0 24px; padding: 16px; background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; }}
 h2 {{ margin: 0 0 12px; font-size: 14px; text-transform: uppercase; letter-spacing: .08em; color: #475569; }}
 .row {{ display: flex; flex-wrap: wrap; gap: 24px; align-items: center; }}
 .icon {{ background: #c7d2fe; }}
</style>
<section><h2>Orbit, buttons, avatars</h2><div class="row">
 <div class="orbit" style="--r:70px"><b>core</b><span class="dot" id="dot1" style="--a:0deg">1</span><span class="dot" style="--a:120deg">2</span><span class="dot" style="--a:240deg">3</span></div>
 <a class="btn-rainbow" id="rainbow" href="#">Rainbow border</a>
 <a class="btn-shiny" id="shiny" href="#">Shiny button</a>
 <div class="avatar-stack" id="avatars"><span>A</span><span>B</span><span>C</span><span>+9</span></div></div></section>
<section><h2>Flicker grid and sparkles</h2><div class="row">
 <div class="flicker-grid" id="flicker" style="--cols:12;width:360px">{CELLS}</div>
 <div class="sparkles" id="sparkles" style="width:200px;height:90px;background:#0f172a;border-radius:12px">
  <i style="--x:20%;--y:30%;--d:0s"></i><i style="--x:60%;--y:55%;--d:.8s"></i><i style="--x:82%;--y:20%;--d:1.6s"></i></div></div></section>
<section><h2>Warp and dock</h2><div class="row">
 <div class="warp" id="warp" style="width:320px;height:160px;background:#0f172a;border-radius:12px"></div>
 <div class="dock" id="dock"><a class="icon" id="d1" href="#" aria-label="one">1</a><a class="icon" id="d2" href="#" aria-label="two">2</a><a class="icon" id="d3" href="#" aria-label="three">3</a><a class="icon" id="d4" href="#" aria-label="four">4</a></div></div></section>
"""


@pytest.mark.e2e
async def test_showpiece_effects_work_and_respect_reduced_motion(tmp_path: Path) -> None:
    pytest.importorskip("playwright.async_api")
    from playwright.async_api import async_playwright

    site = tmp_path / "site"
    site.mkdir()
    shutil.copy2(RECIPES / "motion-fancy.css", site / "motion-fancy.css")
    (site / "index.html").write_text(PAGE, encoding="utf-8")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    errors: list[str] = []
    checks = {
        "#dot1": ("orbit", None),
        "#rainbow": ("rb-spin", None),
        "#shiny": ("shine-pass", None),
        "#flicker > i:nth-child(1)": ("flicker", None),
        "#sparkles > i": ("twinkle", None),
        "#warp": ("warp-run", "::before"),
    }
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(channel="msedge", headless=True)
            page = await browser.new_page(viewport={"width": 1000, "height": 700})
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            await page.goto(f"http://127.0.0.1:{server.server_address[1]}/")
            await page.wait_for_timeout(1200)

            async def animation(selector: str, pseudo: str | None) -> str:
                return str(
                    await page.evaluate(
                        "([s, p]) => getComputedStyle(document.querySelector(s), p).animationName",
                        [selector, pseudo],
                    )
                )

            for selector, (name, pseudo) in checks.items():
                assert name in await animation(selector, pseudo), f"{selector} is not running {name}"
            # dots keep apart: three dots at different positions
            positions = await page.evaluate(
                "[...document.querySelectorAll('.orbit .dot')].map(d => { const r = d.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y)].join(',') })"
            )
            assert len(set(positions)) == 3
            assert "conic-gradient" in await page.evaluate(
                "getComputedStyle(document.getElementById('rainbow')).backgroundImage"
            )
            margin = await page.evaluate(
                "getComputedStyle(document.querySelector('#avatars span:nth-child(2)')).marginLeft"
            )
            assert margin.startswith("-")
            await page.hover("#d2")
            await page.wait_for_timeout(500)
            scale = lambda sel: page.evaluate(f"getComputedStyle(document.querySelector('{sel}')).transform")  # noqa: E731
            assert (
                "1.5" in await scale("#d2") and "1.22" in await scale("#d1") and "1.22" in await scale("#d3")
            )
            assert await scale("#d4") == "none"
            await page.mouse.move(2, 2)
            await page.screenshot(path=str(ARTIFACTS / "motion-fancy.png"), full_page=True)

            await page.emulate_media(reduced_motion="reduce")
            await page.wait_for_timeout(200)
            for selector, (_, pseudo) in checks.items():
                assert await animation(selector, pseudo) == "none", (
                    f"{selector} still animates under reduced motion"
                )
            await browser.close()
    finally:
        server.shutdown()
    assert errors == []

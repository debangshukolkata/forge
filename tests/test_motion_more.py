"""L2: the second motion stylesheet. A demo page uses every class; in Edge each one must do what its comment says, the
page must have no console errors, and prefers-reduced-motion must switch the animations off."""

from __future__ import annotations

import functools
import http.server
import shutil
import threading
from pathlib import Path

import pytest

RECIPES = Path(__file__).resolve().parents[1] / "src" / "forge" / "skills" / "ui-design-quality" / "recipes"
ARTIFACTS = Path(__file__).resolve().parents[1] / "test-artifacts" / "motion"

PAGE = """<!doctype html><meta charset="utf-8"><title>Motion kit part 2</title>
<link rel="icon" href="data:,"><link rel="stylesheet" href="motion-more.css">
<style>
 body { font: 16px system-ui; margin: 0; padding: 24px; background: #f8fafc; color: #0f172a; }
 section { margin: 0 0 28px; padding: 16px; background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; }
 h2 { margin: 0 0 12px; font-size: 14px; text-transform: uppercase; letter-spacing: .08em; color: #475569; }
 .row { display: flex; flex-wrap: wrap; gap: 16px; align-items: center; }
 .box { padding: 14px 18px; background: #eef2ff; border-radius: 10px; }
 .tall { height: 120px; }
 .bg { height: 120px; width: 220px; border-radius: 10px; border: 1px solid #e2e8f0; }
</style>
<div class="scroll-progress" id="progress"></div>
<section id="entrances"><h2>Entrances</h2><div class="row">
 <div class="box in-fade" id="in-fade">fade</div><div class="box in-left" style="--i:1" id="in-left">left</div>
 <div class="box in-right" style="--i:2" id="in-right">right</div><div class="box in-scale" style="--i:3" id="in-scale">scale</div>
 <div class="box in-blur" style="--i:4" id="in-blur">blur</div><div class="box in-clip" style="--i:5" id="in-clip">clip</div>
 <div class="box in-flip" style="--i:6" id="in-flip">flip</div></div></section>
<section id="text"><h2>Text</h2><div class="row">
 <span class="type-writer" style="--chars:19" id="type-writer">Typed, one letter ok</span>
 <strong class="text-sweep" id="text-sweep" style="font-size:28px">Sweeping light</strong>
 <span>A <span class="marker" id="marker">highlighted phrase</span> inside text</span>
 <h3 class="words" id="words" style="margin:0"><span style="--w:0">Words</span> <span style="--w:1">rise</span> <span style="--w:2">in</span></h3>
 <strong class="text-gradient" id="text-gradient" style="font-size:28px">Gradient</strong></div></section>
<section id="hover"><h2>Hover and focus</h2><div class="row">
 <div class="box hover-lift" id="hover-lift" tabindex="0">lift</div><div class="box hover-glow" id="hover-glow" tabindex="0">glow</div>
 <div class="hover-zoom" id="hover-zoom" style="width:140px;height:90px;border-radius:10px"><svg width="140" height="90"><rect width="140" height="90" fill="#6366f1"/></svg></div>
 <a href="#" class="hover-slide-underline" id="hover-slide-underline">Slide underline</a>
 <a href="#" class="group" id="group">Read more <span class="nudge" id="nudge">&rarr;</span></a>
 <button class="press box" id="press">press</button>
 <div class="row hover-dim-siblings" id="dim"><div class="box">one</div><div class="box">two</div><div class="box">three</div></div></div></section>
<section id="ambient"><h2>Ambient</h2><div class="row">
 <div class="bg bg-grid" id="bg-grid"></div><div class="bg bg-dots" id="bg-dots"></div>
 <div class="bg bg-mesh bg-fade-edges" id="bg-mesh"></div>
 <div class="pulse-ring" id="pulse-ring" style="width:60px;height:60px;border-radius:50%;background:#6366f1"></div>
 <div class="drift" id="drift" style="width:40px;height:40px;background:#a5b4fc;border-radius:8px"></div>
 <div class="bg bg-grid grid-pulse" id="grid-pulse"></div>
 <div class="marquee-vertical" id="marquee-vertical" style="--h:8rem;width:180px"><div class="track">
  <div class="box">alpha</div><div class="box">beta</div><div class="box">gamma</div><div class="box">alpha</div><div class="box">beta</div><div class="box">gamma</div></div></div></div></section>
<section id="feedback"><h2>Feedback</h2><div class="row">
 <div class="box shake" id="shake">shake</div>
 <svg class="check-draw" id="check-draw" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="3" stroke-linecap="round"><path d="M4 12l5 5L20 6"/></svg>
 <span class="spinner" id="spinner"></span>
 <div class="progress-ring" id="progress-ring" style="--value:60"></div>
 <div class="box toast-in" id="toast-in">toast</div><div class="box pop" id="pop">pop</div></div></section>
<section id="threed"><h2>3D</h2><div class="row">
 <div class="flip-card" id="flip-card" tabindex="0" style="width:160px;height:90px"><div class="flip-inner" style="height:90px">
  <div class="face box" style="height:90px">front</div><div class="face back box" style="background:#c7d2fe">back</div></div></div>
 <div class="stack-3d" id="stack-3d" style="width:120px;height:80px;position:relative"><div class="box" style="--i:0">a</div><div class="box" style="--i:1;position:absolute;top:10px">b</div></div></div></section>
<section class="tall parallax" id="parallax" style="--from:30px;--to:-30px"><h2>Scroll</h2>parallax block</section>
<div style="height:600px"></div>
"""

ANIMATED = {
    "in-fade": "in-fade",
    "in-left": "in-left",
    "in-right": "in-right",
    "in-scale": "in-scale",
    "in-blur": "in-blur",
    "in-clip": "in-clip",
    "in-flip": "in-flip",
    "type-writer": "typing",
    "text-sweep": "sweep",
    "shake": "shake",
    "spinner": "spin",
    "toast-in": "toast-in",
    "pop": "pop",
    "drift": "shape-drift",
    "grid-pulse": "grid-glow",
    "pulse-ring": "ring-out",
}


@pytest.mark.e2e
async def test_every_effect_does_what_it_says_without_errors(tmp_path: Path) -> None:
    pytest.importorskip("playwright.async_api")
    from playwright.async_api import async_playwright

    site = tmp_path / "site"
    site.mkdir()
    shutil.copy2(RECIPES / "motion-more.css", site / "motion-more.css")
    (site / "index.html").write_text(PAGE, encoding="utf-8")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    errors: list[str] = []
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(channel="msedge", headless=True)
            page = await browser.new_page(viewport={"width": 1100, "height": 900})
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            await page.goto(url)
            await page.wait_for_timeout(1500)
            await page.screenshot(path=str(ARTIFACTS / "motion-more-top.png"), full_page=False)

            names = await page.evaluate(
                """(ids) => Object.fromEntries(ids.map(id => {
                    const el = document.getElementById(id);
                    const cs = getComputedStyle(id === 'pulse-ring' ? el : el, id === 'pulse-ring' ? '::before' : null);
                    return [id, cs.animationName];
                }))""",
                list(ANIMATED),
            )
            for ident, expected in ANIMATED.items():
                assert expected in names[ident], f"{ident}: animation is {names[ident]!r}, wanted {expected}"
            assert "word-up" in await page.evaluate(
                "getComputedStyle(document.querySelector('#words span')).animationName"
            )
            assert "marquee-up" in await page.evaluate(
                "getComputedStyle(document.querySelector('#marquee-vertical .track')).animationName"
            )
            assert "draw" in await page.evaluate(
                "getComputedStyle(document.querySelector('#check-draw path')).animationName"
            )

            assert "linear-gradient" in await page.evaluate(
                "getComputedStyle(document.getElementById('bg-grid')).backgroundImage"
            )
            assert "radial-gradient" in await page.evaluate(
                "getComputedStyle(document.getElementById('bg-dots')).backgroundImage"
            )
            assert "radial-gradient" in await page.evaluate(
                "getComputedStyle(document.getElementById('bg-mesh')).backgroundImage"
            )
            assert "conic-gradient" in await page.evaluate(
                "getComputedStyle(document.getElementById('progress-ring')).backgroundImage"
            )
            assert "linear-gradient" in await page.evaluate(
                "getComputedStyle(document.getElementById('text-gradient')).backgroundImage"
            )

            # marker grows when it becomes visible
            assert "0%" in await page.evaluate(
                "getComputedStyle(document.getElementById('marker')).backgroundSize"
            )
            await page.evaluate("document.getElementById('marker').classList.add('is-visible')")
            await page.wait_for_timeout(1100)
            assert "100%" in await page.evaluate(
                "getComputedStyle(document.getElementById('marker')).backgroundSize"
            )

            # hover and focus effects
            await page.hover("#hover-lift")
            await page.wait_for_timeout(450)
            assert (
                await page.evaluate("getComputedStyle(document.getElementById('hover-lift')).transform")
                != "none"
            )
            await page.hover("#hover-glow")
            await page.wait_for_timeout(450)
            assert "4px" in await page.evaluate(
                "getComputedStyle(document.getElementById('hover-glow')).boxShadow"
            )
            await page.hover("#hover-zoom")
            await page.wait_for_timeout(800)
            assert (
                await page.evaluate("getComputedStyle(document.querySelector('#hover-zoom svg')).transform")
                != "none"
            )
            await page.hover("#hover-slide-underline")
            await page.wait_for_timeout(450)
            assert (
                await page.evaluate(
                    "getComputedStyle(document.getElementById('hover-slide-underline'), '::after').transform"
                )
                == "matrix(1, 0, 0, 1, 0, 0)"
            )
            await page.hover("#group")
            await page.wait_for_timeout(350)
            assert (
                await page.evaluate("getComputedStyle(document.getElementById('nudge')).transform") != "none"
            )
            await page.hover("#flip-card")
            await page.wait_for_timeout(900)
            assert "matrix3d" in await page.evaluate(
                "getComputedStyle(document.querySelector('#flip-card .flip-inner')).transform"
            )
            await page.screenshot(path=str(ARTIFACTS / "motion-more-hover.png"), full_page=True)

            # scroll-driven pieces only where the browser supports them
            supports = await page.evaluate("CSS.supports('animation-timeline', 'scroll()')")
            if supports:
                assert "grow-x" in await page.evaluate(
                    "getComputedStyle(document.getElementById('progress')).animationName"
                )

            # reduced motion switches the animations off
            await page.emulate_media(reduced_motion="reduce")
            await page.wait_for_timeout(200)
            still = await page.evaluate(
                """(ids) => ids.filter(id => getComputedStyle(document.getElementById(id), id === 'pulse-ring' ? '::before' : null).animationName !== 'none')""",
                list(ANIMATED),
            )
            assert still == [], f"still animating under reduced motion: {still}"
            await browser.close()
    finally:
        server.shutdown()
    assert errors == []

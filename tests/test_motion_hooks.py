"""D-383: the React motion hooks type-check and build with Vite, and in Edge: SplitText reveals its words, ScrambleText settles on the real text, Magnetic leans toward the pointer,
PinnedSteps follows the scroll, Parallax moves with it, and under reduced motion everything is final at once."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests import vite_harness as harness

RECIPES = (
    Path(__file__).resolve().parent.parent / "src" / "forge" / "skills" / "ui-design-quality" / "recipes"
)
pytestmark = [pytest.mark.skipif(not harness.available(), reason="ui-react/node_modules is not installed")]

APP = """import { Magnetic, Parallax, PinnedSteps, ScrambleText, SplitText } from "./motion-hooks";
import "./motion-hooks.css";

const steps = [
  { title: "Book", body: "Pick a time that suits you." },
  { title: "Donate", body: "It takes about forty minutes." },
  { title: "Recover", body: "Tea, biscuits and a rest." },
];

export default function App() {
  return (
    <main>
      <h1 id="split"><SplitText text="Give blood give time" /></h1>
      <p id="scramble"><ScrambleText text="Open every day" duration={400} /></p>
      <div style={{ padding: 40 }}><Magnetic><button id="magnet" style={{ padding: "16px 28px" }}>Donate</button></Magnetic></div>
      <div style={{ height: 600 }} />
      <section id="pinned"><PinnedSteps steps={steps} /></section>
      <div style={{ height: 300 }} />
      <Parallax speed={0.5}><div id="layer" style={{ height: 120, background: "#c7d2fe" }}>layer</div></Parallax>
      <div style={{ height: 900 }} />
    </main>
  );
}
"""


def files() -> dict[str, str]:
    return {
        "src/App.tsx": APP,
        "src/index.css": "body{margin:0;font:16px system-ui;color:#111}",
        "src/motion-hooks.tsx": (RECIPES / "motion-hooks.tsx").read_text(encoding="utf-8"),
        "src/motion-hooks.css": (RECIPES / "motion-hooks.css").read_text(encoding="utf-8"),
    }


@pytest.fixture(scope="module")
def site() -> str:
    dist = harness.build("motion-hooks", files(), title="Motion hooks")
    with harness.serve(dist) as url:
        yield url  # type: ignore[misc]


async def run(site: str, reduced: bool) -> dict[str, object]:
    from playwright.async_api import async_playwright

    seen: dict[str, object] = {}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="msedge", headless=True)
        page = await browser.new_page(
            viewport={"width": 1100, "height": 800}, reduced_motion="reduce" if reduced else "no-preference"
        )
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(site)
        await page.wait_for_timeout(1200)
        seen["split_visible"] = await page.evaluate(
            "[...document.querySelectorAll('.split-piece')].every(e => getComputedStyle(e).opacity === '1')"
        )
        seen["split_label"] = await page.get_attribute("#split .split-text", "aria-label")
        seen["scramble_text"] = (await page.inner_text("#scramble")).strip()
        seen["scramble_label"] = await page.get_attribute("#scramble .scramble-text", "aria-label")
        box = await page.locator("#magnet").bounding_box()
        assert box is not None
        await page.mouse.move(box["x"] + box["width"] - 4, box["y"] + box["height"] / 2)
        await page.mouse.move(box["x"] + box["width"] - 2, box["y"] + box["height"] / 2)
        await page.wait_for_timeout(400)
        seen["magnet_transform"] = await page.evaluate(
            "getComputedStyle(document.querySelector('.magnetic')).transform"
        )
        before = await page.evaluate("document.querySelector('.pinned-list li.is-active').dataset.index")
        await page.evaluate(
            "document.querySelectorAll('.pinned-list li')[2].scrollIntoView({block: 'center'})"
        )
        await page.wait_for_timeout(700)
        after = await page.evaluate("document.querySelector('.pinned-list li.is-active').dataset.index")
        seen["pinned"] = (before, after)
        seen["pinned_panel"] = (await page.inner_text(".pinned-label")).strip()
        y0 = await page.evaluate(
            "document.querySelector('.parallax').getBoundingClientRect().top + window.scrollY"
        )
        await page.evaluate("window.scrollTo(0, document.querySelector('.parallax').offsetTop - 500)")
        await page.wait_for_timeout(300)
        t1 = await page.evaluate("getComputedStyle(document.querySelector('.parallax')).transform")
        await page.evaluate("window.scrollTo(0, document.querySelector('.parallax').offsetTop - 100)")
        await page.wait_for_timeout(300)
        t2 = await page.evaluate("getComputedStyle(document.querySelector('.parallax')).transform")
        seen["parallax"] = (t1, t2, y0)
        seen["errors"] = errors
        await browser.close()
    return seen


async def test_the_hooks_do_what_they_say(site: str) -> None:
    seen = await run(site, reduced=False)
    assert seen["errors"] == []
    assert seen["split_visible"] is True and seen["split_label"] == "Give blood give time"
    assert seen["scramble_text"] == "Open every day" and seen["scramble_label"] == "Open every day"
    assert seen["magnet_transform"] not in ("none", "matrix(1, 0, 0, 1, 0, 0)"), seen["magnet_transform"]
    assert seen["pinned"] == ("0", "2") and seen["pinned_panel"] == "Recover"
    t1, t2, _ = seen["parallax"]  # type: ignore[misc]
    assert t1 != t2  # the layer moved while the page scrolled


async def test_under_reduced_motion_everything_is_final_and_nothing_moves(site: str) -> None:
    seen = await run(site, reduced=True)
    assert seen["errors"] == []
    assert seen["split_visible"] is True and seen["scramble_text"] == "Open every day"
    assert seen["magnet_transform"] in ("none", "matrix(1, 0, 0, 1, 0, 0)")
    t1, t2, _ = seen["parallax"]  # type: ignore[misc]
    assert t1 == t2


def test_the_five_assets_are_in_the_catalogue() -> None:
    from forge.parity.assets import build_catalogue

    skill = RECIPES.parent
    ids = {a.id for a in build_catalogue(skill).assets if a.id.startswith("fx-react-")}
    assert ids >= {
        "fx-react-split-text",
        "fx-react-scramble-text",
        "fx-react-magnetic",
        "fx-react-pinned-steps",
        "fx-react-parallax",
    }

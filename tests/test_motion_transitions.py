"""D-517: the React view-transition helpers type-check and build with Vite, and in Edge a change runs inside a view transition and updates the page;
under reduced motion no transition starts and the page still updates."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests import vite_harness as harness

RECIPES = (
    Path(__file__).resolve().parent.parent / "src" / "forge" / "skills" / "ui-design-quality" / "recipes"
)
pytestmark = [pytest.mark.skipif(not harness.available(), reason="ui-react/node_modules is not installed")]

APP = """import { useState } from "react";
import { SharedElement, goTo, runTransition, useViewTransition } from "./motion-transitions";
import "./motion-transitions.css";

export default function App() {
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState("home");
  const run = useViewTransition();
  return (
    <main>
      <button id="toggle" onClick={() => runTransition(() => setOpen(!open))}>toggle</button>
      <button id="hook" onClick={() => run(() => setOpen(false))}>close</button>
      <button id="route" onClick={() => goTo(() => setPage("pricing"))}>go</button>
      <p id="state">{open ? "open" : "closed"}</p>
      <p id="page">{page}</p>
      <SharedElement name="card-1" className="card">{open ? <img alt="" width="200" height="120" /> : <span>thumb</span>}</SharedElement>
    </main>
  );
}
"""


@pytest.fixture(scope="module")
def site() -> str:
    files = {
        "src/App.tsx": APP,
        "src/index.css": "body{margin:0;font:16px system-ui}",
        "src/motion-transitions.tsx": (RECIPES / "motion-transitions.tsx").read_text(encoding="utf-8"),
        "src/motion-transitions.css": (RECIPES / "motion-transitions.css").read_text(encoding="utf-8"),
    }
    dist = harness.build("motion-transitions", files, title="View transitions")
    with harness.serve(dist) as url:
        yield url  # type: ignore[misc]


async def run(site: str, reduced: bool) -> dict[str, object]:
    from playwright.async_api import async_playwright

    seen: dict[str, object] = {}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="msedge", headless=True)
        page = await browser.new_page(reduced_motion="reduce" if reduced else "no-preference")
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.add_init_script(
            "window.__vt = 0; const original = document.startViewTransition && document.startViewTransition.bind(document);"
            "if (original) { document.startViewTransition = (cb) => { window.__vt++; return original(cb); }; }"
        )
        await page.goto(site)
        seen["supported"] = await page.evaluate("typeof document.startViewTransition === 'function'")
        await page.click("#toggle")
        await page.wait_for_timeout(600)
        seen["state"] = await page.inner_text("#state")
        await page.click("#route")
        await page.wait_for_timeout(600)
        seen["page"] = await page.inner_text("#page")
        seen["transitions"] = await page.evaluate("window.__vt")
        seen["shared_name"] = await page.evaluate(
            "document.querySelector('[data-shared]').style.viewTransitionName"
        )
        seen["errors"] = errors
        await browser.close()
    return seen


async def test_a_change_runs_inside_a_view_transition(site: str) -> None:
    seen = await run(site, reduced=False)
    assert seen["errors"] == []
    assert seen["state"] == "open" and seen["page"] == "pricing"
    assert seen["shared_name"] == "card-1"
    if seen["supported"]:
        assert seen["transitions"] == 2  # the toggle and the route change


async def test_under_reduced_motion_no_transition_starts_and_the_page_still_updates(site: str) -> None:
    seen = await run(site, reduced=True)
    assert seen["errors"] == []
    assert seen["state"] == "open" and seen["page"] == "pricing"
    assert seen["transitions"] == 0

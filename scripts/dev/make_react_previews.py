"""Pictures of the React effects and components of the ui-design-quality skill (TODO L0, D-517), which need a real build to be seen.

    python scripts/dev/make_react_previews.py

Builds one demo page with Vite + Tailwind v4 (the helper the asset tests use: ui-react/node_modules, nothing downloaded), puts each effect or component
in its own 640 x 360 box, photographs the boxes in headless Edge and writes assets/preview/<id>.jpg with a `preview:` line in the asset. The dialog is
photographed on its own because a modal dialog sits above the page. Needs ui-react/node_modules, Edge and Pillow. Then run scripts/build_asset_catalogue.py."""

from __future__ import annotations

import re
import sys
from io import BytesIO
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from tests import vite_harness as harness  # noqa: E402

SKILL = REPO / "src" / "forge" / "skills" / "ui-design-quality"
RECIPES = SKILL / "recipes"
PREVIEW = SKILL / "assets" / "preview"

# asset id -> JSX of the demo (inside a 640 x 360 box). The dialog is the only one that is shown on its own.
DEMOS: dict[str, str] = {
    "fx-count-up": '<p className="font-display text-7xl font-semibold text-brand-600"><CountUp to={450} suffix="+" duration={900} /></p>',
    "fx-marquee": '<div className="w-full"><Marquee>{["Northwind", "Meridian", "Bluebird", "Fieldwork", "Orbit Labs"].map((n) => <span key={n} className="mx-8 text-2xl font-semibold text-ink-500">{n}</span>)}</Marquee></div>',
    "fx-spotlight-card": '<SpotlightCard className="rounded-card bg-ink-900 p-8 text-white"><p className="text-xl font-semibold">Move the pointer</p><p className="mt-2 text-white/80">A soft light follows it across the card.</p></SpotlightCard>',
    "fx-tilt-card": '<TiltCard className="card w-72"><p className="font-semibold text-ink-900">Tilt card</p><p className="mt-2 text-ink-700">Leans a few degrees toward the pointer.</p></TiltCard>',
    "fx-react-split-text": '<h2 className="text-5xl font-semibold"><SplitText text="Give blood give time" /></h2>',
    "fx-react-scramble-text": '<p className="font-mono text-4xl font-semibold text-ink-900"><ScrambleText text="Open every day" duration={400} /></p>',
    "fx-react-magnetic": '<Magnetic><button className="btn-primary">Donate</button></Magnetic>',
    "fx-react-parallax": '<div className="overflow-hidden rounded-card"><Parallax speed={0.3}><div className="h-40 w-96 bg-brand-200 p-6 font-semibold text-brand-900">A layer that drifts as you scroll</div></Parallax></div>',
    "fx-react-pinned-steps": '<div className="w-full max-w-xl"><PinnedSteps steps={[{ title: "Book", body: "Pick a time that suits you." }, { title: "Donate", body: "It takes about forty minutes." }, { title: "Recover", body: "Tea, biscuits and a rest." }]} /></div>',
    "fx-react-animated-beam": "<BeamDemo />",
    "fx-react-particles": '<div className="relative h-64 w-[34rem] overflow-hidden rounded-card bg-ink-900"><Particles /></div>',
    "fx-react-globe-lite": '<div className="grid h-72 w-[34rem] place-items-center overflow-hidden rounded-card bg-ink-900"><GlobeLite size={240} /></div>',
    "cmp-data-table": '<div className="w-full max-w-xl"><DataTable rows={[{ name: "Alder & Finch", orders: 42, total: 1280 }, { name: "Northgate Print", orders: 17, total: 640 }, { name: "Tidewater Cafe", orders: 63, total: 2210 }]} columns={[{ key: "name", label: "Customer" }, { key: "orders", label: "Orders", numeric: true }, { key: "total", label: "Total", numeric: true }]} /></div>',
    "cmp-empty-state": '<EmptyState title="No invoices yet" text="Invoices you send will appear here, newest first." action={<button className="btn-primary">Create an invoice</button>} />',
    "cmp-skeleton-rows": '<div className="w-96"><SkeletonRows rows={4} /></div>',
    "cmp-tabs": '<div className="w-full max-w-xl"><Tabs tabs={[{ id: "a", label: "Overview", content: <p>The overview of the account.</p> }, { id: "b", label: "Activity", content: <p>Recent activity.</p> }, { id: "c", label: "Settings", content: <p>Account settings.</p> }]} /></div>',
}
ALONE = {
    "cmp-dialog": '<Dialog open onClose={() => undefined} title="Delete this invoice?"><p>This cannot be undone.</p><button className="btn-primary mt-4">Delete</button></Dialog>'
}

APP = """import { useRef } from "react";
import { CountUp, Marquee, SpotlightCard, TiltCard } from "./motion";
import { Magnetic, Parallax, PinnedSteps, ScrambleText, SplitText } from "./motion-hooks";
import { AnimatedBeam, GlobeLite, Particles } from "./motion-canvas";
import { DataTable, Dialog, EmptyState, SkeletonRows, Tabs, ToastRegion } from "./components-native";
import "./motion.css";
import "./motion-hooks.css";

function BeamDemo() {
  const box = useRef<HTMLDivElement>(null);
  const a = useRef<HTMLDivElement>(null);
  const b = useRef<HTMLDivElement>(null);
  return (
    <div ref={box} className="relative flex h-48 w-[34rem] items-center justify-between rounded-card bg-white p-10 shadow-soft">
      <div ref={a} className="grid h-14 w-14 place-items-center rounded-full bg-brand-100 font-semibold text-brand-700">A</div>
      <div ref={b} className="grid h-14 w-14 place-items-center rounded-full bg-brand-600 font-semibold text-white">B</div>
      <AnimatedBeam containerRef={box} fromRef={a} toRef={b} />
    </div>
  );
}

const only = new URLSearchParams(window.location.search).get("only");

export default function App() {
@@ALONE@@
  return (
    <div>
@@BOXES@@
    </div>
  );
}
"""


def main() -> int:
    from PIL import Image
    from playwright.sync_api import sync_playwright

    if not harness.available():
        print("ui-react/node_modules is not installed")
        return 1
    css = (RECIPES / "templates/charity/index.css").read_text(encoding="utf-8")
    css = css.replace('@import "./fonts/fraunces.css";\n', "").replace('@import "./fonts/inter.css";\n', "")
    boxes = "\n".join(
        f'      <section data-demo="{asset}" className="flex h-[360px] w-[640px] items-center justify-center overflow-hidden bg-ink-50 p-6">{jsx}</section>'
        for asset, jsx in DEMOS.items()
    )
    alone = "\n".join(
        f'  if (only === "{asset}") {{\n    return ({jsx});\n  }}' for asset, jsx in ALONE.items()
    )
    source = APP.replace("@@BOXES@@", boxes).replace("@@ALONE@@", alone)
    files: dict[str, str | bytes] = {"src/index.css": css, "src/App.tsx": source}
    for name in (
        "motion.tsx",
        "motion.css",
        "motion-hooks.tsx",
        "motion-hooks.css",
        "motion-canvas.tsx",
        "components-native.tsx",
    ):
        files[f"src/{name}"] = (RECIPES / name).read_text(encoding="utf-8")
    dist = harness.build("react-previews", files, title="React previews")
    PREVIEW.mkdir(parents=True, exist_ok=True)
    made = []
    with harness.serve(dist) as url, sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 700, "height": 420})
        page.goto(url)
        page.wait_for_timeout(1200)
        for asset in DEMOS:
            box = page.locator(f'[data-demo="{asset}"]')
            if box.count() == 0:
                continue
            if asset == "fx-spotlight-card":
                box.hover()
            image = Image.open(BytesIO(box.screenshot())).convert("RGB")
            image.save(PREVIEW / f"{asset}.jpg", "JPEG", quality=85)
            made.append(asset)
        page.set_viewport_size({"width": 640, "height": 360})
        for asset in ALONE:  # shown on their own: a modal dialog and a fixed toast region sit above the page
            page.goto(f"{url}?only={asset}")
            page.wait_for_timeout(700)
            Image.open(BytesIO(page.screenshot())).convert("RGB").save(
                PREVIEW / f"{asset}.jpg", "JPEG", quality=85
            )
            made.append(asset)
        browser.close()
    for asset in made:
        path = next((SKILL / "assets").glob(f"*/{asset}.md"), None)
        if path is None:
            print("no asset file for", asset)
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"^preview:", text, re.M):
            continue
        front = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, re.S)
        if front:
            path.write_text(
                text[: front.end(1)] + f"\npreview: assets/preview/{asset}.jpg" + text[front.end(1) :],
                encoding="utf-8",
                newline="\n",
            )
    print(f"{len(made)} pictures made: {', '.join(made)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

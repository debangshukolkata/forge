"""Reference pictures of the bundled templates (TODO L10): what each one looks like, so the model (which has vision) can match a picture
instead of a description. Builds every `template` asset of the ui-design-quality skill the way the asset tests do (Vite + Tailwind from
ui-react/node_modules), photographs it in headless Edge at 1280 and 375 px and writes JPEGs to `assets/preview/<id>-desktop.jpg` and
`<id>-mobile.jpg` (the page's first screens, capped in height so the files stay small).

    python scripts/dev/build_reference_shots.py [asset-id ...]

Needs ui-react/node_modules and Edge. `add_asset` copies the pictures into the project's `.forge/reference/` for `view_image`."""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from tests import vite_harness as harness  # noqa: E402

SKILL = REPO / "src" / "forge" / "skills" / "ui-design-quality"
PREVIEW = SKILL / "assets" / "preview"
MAX_HEIGHT = {1280: 3000, 375: 3600}
QUALITY = 78


async def photograph(url: str, name: str) -> list[Path]:
    from io import BytesIO

    from PIL import Image
    from playwright.async_api import async_playwright

    PREVIEW.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="msedge", headless=True)
        for width, label in ((1280, "desktop"), (375, "mobile")):
            page = await browser.new_page(viewport={"width": width, "height": 800})
            await page.goto(url)
            await page.wait_for_load_state("networkidle")
            await page.evaluate(  # reveal-on-scroll content must be on screen
                "async () => { for (let y = 0; y < document.body.scrollHeight; y += 400) { window.scrollTo(0, y); "
                "await new Promise(r => setTimeout(r, 60)); } window.scrollTo(0, 0); }"
            )
            await page.wait_for_timeout(600)
            data = await page.screenshot(full_page=True)
            image = Image.open(BytesIO(data)).convert("RGB")
            if image.height > MAX_HEIGHT[width]:
                image = image.crop((0, 0, image.width, MAX_HEIGHT[width]))
            target = PREVIEW / f"{name}-{label}.jpg"
            image.save(target, "JPEG", quality=QUALITY, optimize=True)
            written.append(target)
            await page.close()
        await browser.close()
    return written


async def build(asset_id: str) -> list[Path]:
    from forge.toolkit.base import ToolContext
    from forge.tools.assets import AddAsset
    from forge.workspace.create import create_workspace

    with tempfile.TemporaryDirectory() as folder:
        original = Path(folder) / "repo"
        (original / "app").mkdir(parents=True)
        (original / "app" / "README.md").write_text("x", encoding="utf-8")
        workspace = create_workspace(original, Path(folder) / "ws", "app")
        context = ToolContext(workspace=workspace, design_first=False)
        added = await AddAsset().run(AddAsset.Args(id=asset_id, project_dir="web"), context)
        if not added.ok:
            raise SystemExit(f"{asset_id}: {added.content}")
        web = workspace.repo_dir / "web"
        files: dict[str, str | bytes] = {}
        for path in web.rglob("*"):
            if path.is_file() and path.name != "NOTICES.md":
                relative = path.relative_to(web).as_posix()
                files[relative] = (
                    path.read_bytes() if path.suffix == ".woff2" else path.read_text(encoding="utf-8")
                )
        dist = harness.build(asset_id, files, title=asset_id)
        with harness.serve(dist) as url:
            return await photograph(url, asset_id)


def main(ids: list[str]) -> int:
    if not harness.available():
        print("ui-react/node_modules is missing: run npm install in ui-react first")
        return 2
    wanted = ids or sorted(p.stem for p in (SKILL / "assets" / "template").glob("*.md"))
    for asset_id in wanted:
        for picture in asyncio.run(build(asset_id)):
            print(f"{picture.relative_to(REPO)}  {picture.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

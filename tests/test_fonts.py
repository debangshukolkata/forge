"""L3: the bundled offline fonts are licensed, small, complete and really render without the internet."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from forge.parity.assets import load_catalogue, search
from forge.toolkit.base import ToolContext
from forge.tools.assets import AddAsset
from forge.workspace.create import create_workspace

SKILL = Path(__file__).resolve().parents[1] / "src" / "forge" / "skills" / "ui-design-quality"
FONTS = SKILL / "fonts"
BUDGET_BYTES = 1_500_000  # decision D-268: the whole bundle stays under 1.5 MB


def test_the_bundle_is_small_licensed_and_complete() -> None:
    families = sorted(p for p in FONTS.iterdir() if p.is_dir())
    assert len(families) >= 14
    total = 0
    for family in families:
        woff2 = list(family.glob("*.woff2"))
        assert woff2, family.name
        total += sum(f.stat().st_size for f in woff2)
        licence = (family / f"{family.name}-OFL.txt").read_text(encoding="utf-8")
        assert "SIL Open Font License" in licence and "Copyright" in licence
        css = (family / f"{family.name}.css").read_text(encoding="utf-8")
        for name in re.findall(r"url\(/fonts/([\w.-]+)\)", css):
            assert (family / name).is_file(), f"{family.name}.css points at missing {name}"
        assert "font-display: swap" in css and "format('woff2-variations')" in css
    assert total <= BUDGET_BYTES, f"bundled fonts are {total} bytes"


def test_every_font_and_pairing_is_in_the_catalogue() -> None:
    catalogue = load_catalogue(SKILL)
    fonts = [a for a in catalogue if a.type == "font"]
    pairs = [a for a in catalogue if a.type == "font-pairing"]
    assert len(fonts) == len([p for p in FONTS.iterdir() if p.is_dir()])
    assert len(pairs) >= 10
    assert all(a.licence == "OFL-1.1" for a in fonts + pairs)
    families = {a.id.removeprefix("font-") for a in fonts}
    for pair in pairs:
        used = {Path(f["from"]).parts[1] for f in pair.files}
        assert used <= families and len(used) == 2


def test_retrieval_of_fonts_and_pairings() -> None:
    catalogue = load_catalogue(SKILL)
    assert "pair-warm-editorial" in [a.id for a in search(catalogue, "warm editorial charity fonts", limit=3)]
    assert "pair-bengali" in [a.id for a in search(catalogue, "bengali text font", limit=3)]
    assert "pair-hindi" in [a.id for a in search(catalogue, "hindi devanagari font", limit=3)]
    assert "font-jetbrains-mono" in [a.id for a in search(catalogue, "monospace code font", limit=3)]


async def test_adding_a_pairing_copies_binary_fonts_unchanged(tmp_path: Path, original_repo: Path) -> None:
    context = ToolContext(
        workspace=create_workspace(original_repo, tmp_path / "ws", "backend"), design_first=False
    )
    result = await AddAsset().run(AddAsset.Args(id="pair-warm-editorial", project_dir="web"), context)
    assert result.ok, result.content
    web = context.workspace.repo_dir / "web"
    source = FONTS / "fraunces" / "fraunces-latin-wght-normal.woff2"
    copied = web / "public" / "fonts" / "fraunces-latin-wght-normal.woff2"
    assert copied.read_bytes() == source.read_bytes()
    assert "url(/fonts/inter-latin-wght-normal.woff2)" in (web / "src" / "fonts" / "inter.css").read_text(
        encoding="utf-8"
    )
    assert (web / "public" / "fonts" / "inter-OFL.txt").is_file()
    again = await AddAsset().run(AddAsset.Args(id="pair-warm-editorial", project_dir="web"), context)
    assert "Files written" not in again.content and "already the same" in again.content


@pytest.mark.e2e
async def test_every_bundled_family_renders_from_local_files_alone(tmp_path: Path) -> None:
    """Serves the fonts from a local folder (no internet) and asks Edge whether each family loaded and changes the text."""
    import functools
    import http.server
    import shutil
    import threading

    pytest.importorskip("playwright.async_api")
    from playwright.async_api import async_playwright

    site = tmp_path / "site"
    (site / "fonts").mkdir(parents=True)
    families = sorted(p for p in FONTS.iterdir() if p.is_dir())
    css, rows = [], []
    for family in families:
        for item in family.glob("*.woff2"):
            shutil.copy2(item, site / "fonts" / item.name)
        css.append((family / f"{family.name}.css").read_text(encoding="utf-8"))
        name = re.search(r"font-family: '([^']+)'", css[-1]).group(1)  # type: ignore[union-attr]
        rows.append(name)
    sample = "Hamburgefonstiv 0123456789 " + "আমি हिन्दी"
    html = (
        "<!doctype html><meta charset=utf-8><style>"
        + "\n".join(css).replace("url(/fonts/", "url(fonts/")
        + "</style><body style='font-size:32px'>"
        + "".join(
            f"<p id='p{i}' style='display:inline-block;font-family:\"{n}\", monospace'>{sample}</p>"
            for i, n in enumerate(rows)
        )
        + "<p id='fallback' style='display:inline-block;font-family:monospace'>"
        + sample
        + "</p>"
    )
    (site / "index.html").write_text(html, encoding="utf-8")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(channel="msedge", headless=True)
            page = await browser.new_page()
            requests: list[str] = []
            page.on("request", lambda request: requests.append(request.url))
            await page.goto(f"http://127.0.0.1:{server.server_address[1]}/")
            await page.evaluate("document.fonts.ready")
            result = await page.evaluate(
                """async (names) => {
                    for (const n of names) await document.fonts.load('32px "' + n + '"', 'Hamburgefonstiv');
                    const loaded = [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family.replace(/"/g, ''));
                    const widths = names.map((n, i) => document.getElementById('p' + i).getBoundingClientRect().width);
                    return { loaded, widths, fallback: document.getElementById('fallback').getBoundingClientRect().width };
                }""",
                rows,
            )
            await browser.close()
    finally:
        server.shutdown()
    assert set(rows) <= set(result["loaded"]), f"not loaded: {sorted(set(rows) - set(result['loaded']))}"
    assert all(url.startswith("http://127.0.0.1") for url in requests), "a request left the machine"
    different = [w for w in result["widths"] if abs(w - result["fallback"]) > 1]
    assert (
        len(different) >= len(rows) - 2
    )  # a family may coincide with the monospace fallback width, not most of them

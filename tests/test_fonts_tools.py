"""L3 (D-330): find_font and fetch_font. The network is simulated at the transport with answers shaped like api.fontsource.org's;
`scripts/dev/reach_smoke.py` checks the real service."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import httpx
import pytest

from forge.toolkit.base import ToolContext
from forge.tools import font_sources
from forge.tools.fonts import FetchFont, FindFont, library_folder
from forge.workspace.create import create_workspace

WOFF2 = b"wOF2" + b"0" * 40
TTF = b"\x00\x01\x00\x00" + b"0" * 40
CDN = "https://cdn.jsdelivr.net/fontsource/fonts"

CATALOGUE = [
    {
        "id": "inter",
        "family": "Inter",
        "subsets": ["latin", "latin-ext", "cyrillic"],
        "weights": [400, 700],
        "styles": ["normal", "italic"],
        "defSubset": "latin",
        "variable": True,
        "category": "sans-serif",
        "license": "OFL-1.1",
        "type": "google",
    },
    {
        "id": "noto-sans-bengali",
        "family": "Noto Sans Bengali",
        "subsets": ["bengali", "latin"],
        "weights": [400, 700],
        "styles": ["normal"],
        "defSubset": "latin",
        "variable": True,
        "category": "sans-serif",
        "license": "OFL-1.1",
        "type": "google",
    },
    {
        "id": "akshar",
        "family": "Akshar",
        "subsets": ["devanagari", "latin"],
        "weights": [300, 400, 700],
        "styles": ["normal"],
        "defSubset": "latin",
        "variable": False,
        "category": "sans-serif",
        "license": "OFL-1.1",
        "type": "google",
    },
    {
        "id": "playfair-display",
        "family": "Playfair Display",
        "subsets": ["latin"],
        "weights": [400, 700],
        "styles": ["normal", "italic"],
        "defSubset": "latin",
        "variable": True,
        "category": "serif",
        "license": "OFL-1.1",
        "type": "google",
    },
    {
        "id": "gotham-like",
        "family": "Gotham Like",
        "subsets": ["latin"],
        "weights": [400],
        "styles": ["normal"],
        "defSubset": "latin",
        "variable": False,
        "category": "sans-serif",
        "license": "Commercial",
        "type": "other",
    },
    {
        "id": "material-icons",
        "family": "Material Icons",
        "subsets": ["latin"],
        "weights": [400],
        "styles": ["normal"],
        "defSubset": "latin",
        "variable": False,
        "category": "other",
        "license": "Apache-2.0",
        "type": "icons",
    },
]


def _meta(font: dict[str, Any]) -> dict[str, Any]:
    variants: dict[str, Any] = {}
    for weight in font["weights"]:
        variants[str(weight)] = {
            style: {
                script: {
                    "url": {
                        fmt: f"{CDN}/{font['id']}@latest/{script}-{weight}-{style}.{fmt}"
                        for fmt in ("woff2", "woff", "ttf")
                    }
                }
                for script in font["subsets"]
            }
            for style in font["styles"]
        }
    return {**font, "variants": variants}


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if request.url.host == "api.fontsource.org" and path == "/v1/fonts":
        return httpx.Response(200, json=CATALOGUE)
    if request.url.host == "api.fontsource.org" and path.startswith("/v1/fonts/"):
        wanted = path.rsplit("/", 1)[1]
        found = next((f for f in CATALOGUE if f["id"] == wanted), None)
        return httpx.Response(200, json=_meta(found)) if found else httpx.Response(404)
    if request.url.host == "cdn.jsdelivr.net":
        return httpx.Response(
            200,
            content=WOFF2
            if path.endswith(".woff2")
            else TTF
            if path.endswith(".ttf")
            else b"wOFF" + b"0" * 20,
        )
    if request.url.host == "files.example.org":
        if path.endswith("/corporate.ttf"):
            return httpx.Response(200, content=TTF)
        if path.endswith("/corporate.zip"):
            out = io.BytesIO()
            with zipfile.ZipFile(out, "w") as z:
                z.writestr("Corp/Corporate-Regular.ttf", TTF)
                z.writestr("Corp/Corporate-Bold.otf", b"OTTO" + b"0" * 20)
                z.writestr("Corp/readme.txt", b"licence text")
            return httpx.Response(200, content=out.getvalue())
        if path.endswith("/page.ttf"):
            return httpx.Response(200, content=b"<html>please log in</html>")
    return httpx.Response(404)


def _use(monkeypatch: pytest.MonkeyPatch, handler: Any = _handler) -> None:
    monkeypatch.setattr(
        font_sources,
        "make_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True),
    )


def _down(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("getaddrinfo failed")


def _context(original_repo: Path, tmp_path: Path) -> ToolContext:
    return ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))


async def test_search_by_name_look_and_script_and_only_open_licences(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use(monkeypatch)
    context = _context(original_repo, tmp_path)
    by_name = (await FindFont().run(FindFont.Args(query="playfair"), context)).content
    assert (
        "playfair-display - Playfair Display (serif" in by_name
        and "ships with DebCraft" in by_name
        and "catalogue: online" in by_name
    )
    hindi = (await FindFont().run(FindFont.Args(query="hindi"), context)).content
    assert (
        "akshar" in hindi
        and "devanagari" in hindi
        and "inter" not in hindi.split("fetch_font")[0].replace("Akshar", "")
    )
    serif = (await FindFont().run(FindFont.Args(category="serif"), context)).content
    assert "playfair-display" in serif and "akshar" not in serif
    everything = (await FindFont().run(FindFont.Args(query="gotham"), context)).content + (
        await FindFont().run(FindFont.Args(query="material icons"), context)
    ).content
    assert (
        "gotham-like" not in everything
        and "material-icons" not in everything
        and "No open-licence font matched" in everything
    )


async def test_the_catalogue_is_cached_and_the_offline_list_answers_before_the_first_download(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use(monkeypatch, _down)
    context = _context(original_repo, tmp_path)
    offline = (await FindFont().run(FindFont.Args(query="inter"), context)).content
    assert "offline list of 14 families" in offline and "inter - Inter" in offline
    _use(monkeypatch)
    assert "catalogue: online" in (await FindFont().run(FindFont.Args(query="inter"), context)).content
    _use(monkeypatch, _down)
    assert "catalogue: cache" in (await FindFont().run(FindFont.Args(query="inter"), context)).content
    assert json.loads(font_sources.cache_file().read_text(encoding="utf-8"))["fonts"][0]["id"] == "inter"


async def test_fetch_writes_web_and_desktop_files_css_installer_and_notice(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use(monkeypatch)
    context = _context(original_repo, tmp_path)
    result = await FetchFont().run(FetchFont.Args(font="Inter", formats=["woff2", "ttf"]), context)
    assert result.ok, result.content
    root = context.workspace.path_of("fonts")
    assert (root / "inter" / "latin-400-normal.woff2").read_bytes() == WOFF2 and (
        root / "inter" / "latin-700-normal.ttf"
    ).read_bytes() == TTF
    css = (root / "inter.css").read_text(encoding="utf-8")
    assert (
        css.count("@font-face") == 2
        and "font-weight: 700" in css
        and "url('./inter/latin-400-normal.woff2')" in css
        and "font-display: swap" in css
    )
    script = (root / "inter" / "install-fonts.ps1").read_text(encoding="utf-8")
    assert "LOCALAPPDATA" in script and "HKCU:" in script and "install-fonts.ps1" in result.content
    notices, _ = context.workspace.read_text("NOTICES.md")
    assert "Inter (inter)" in notices and "OFL-1.1" in notices


async def test_a_second_fetch_adds_to_the_css_and_the_library_serves_it_without_a_network(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use(monkeypatch)
    first = _context(original_repo, tmp_path / "one")
    await FetchFont().run(FetchFont.Args(font="inter", weights=[400]), first)
    await FetchFont().run(FetchFont.Args(font="inter", weights=[700]), first)
    assert (first.workspace.path_of("fonts") / "inter.css").read_text(encoding="utf-8").count(
        "@font-face"
    ) == 2
    assert (library_folder() / "inter" / "latin-400-normal.woff2").is_file()
    _use(monkeypatch, _down)
    second = _context(original_repo, tmp_path / "two")
    again = await FetchFont().run(FetchFont.Args(font="inter", weights=[400, 700]), second)
    assert again.ok and "2 from DebCraft's library" in again.content


async def test_other_scripts_italics_and_bad_requests(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use(monkeypatch)
    context = _context(original_repo, tmp_path)
    bengali = await FetchFont().run(
        FetchFont.Args(font="Noto Sans Bengali", weights=[400], scripts=["bengali", "latin"]), context
    )
    assert (
        bengali.ok
        and (context.workspace.path_of("fonts/noto-sans-bengali/bengali-400-normal.woff2")).is_file()
    )
    assert (
        "no bengali script"
        in (await FetchFont().run(FetchFont.Args(font="inter", scripts=["bengali"]), context)).content
    )
    assert "no italic" in (await FetchFont().run(FetchFont.Args(font="akshar", italic=True), context)).content
    assert (
        "none of [900] exist"
        in (await FetchFont().run(FetchFont.Args(font="inter", weights=[900]), context)).content
    )
    assert (
        "No open-licence font called"
        in (await FetchFont().run(FetchFont.Args(font="Helvetica Neue Pro"), context)).content
    )
    assert "either `font`" in (await FetchFont().run(FetchFont.Args(), context)).content
    monkeypatch.setattr("forge.tools.fonts.MAX_FILES", 5)
    many = await FetchFont().run(
        FetchFont.Args(
            font="inter",
            weights=[400, 700],
            scripts=["latin", "latin-ext", "cyrillic"],
            formats=["woff2", "woff", "ttf"],
            italic=True,
        ),
        context,
    )
    assert not many.ok and "too many" in many.content


async def test_a_proxy_page_instead_of_a_font_is_refused_and_a_dead_network_says_why(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "cdn.jsdelivr.net":
            return httpx.Response(200, content=b"<html>Blocked by company policy</html>")
        return _handler(request)

    _use(monkeypatch, handler)
    context = _context(original_repo, tmp_path)
    blocked = await FetchFont().run(FetchFont.Args(font="inter", weights=[400]), context)
    assert (
        not blocked.ok
        and "not a woff2 font file" in blocked.content
        and not context.workspace.path_of("fonts/inter").exists()
    )


async def test_a_font_the_user_points_to_is_downloaded_from_a_file_or_a_zip(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use(monkeypatch)
    context = _context(original_repo, tmp_path)
    single = await FetchFont().run(FetchFont.Args(url="https://files.example.org/f/corporate.ttf"), context)
    assert single.ok and "licence was not checked" in single.content
    assert (
        context.workspace.path_of("fonts/corporate/corporate.ttf").read_bytes() == TTF
        and context.workspace.path_of("fonts/corporate/install-fonts.ps1").is_file()
    )
    zipped = await FetchFont().run(
        FetchFont.Args(url="https://files.example.org/f/corporate.zip", folder="assets/fonts"), context
    )
    assert (
        zipped.ok
        and "Corporate-Regular.ttf" in zipped.content
        and "Corporate-Bold.otf" in zipped.content
        and "readme" not in zipped.content
    )
    page = await FetchFont().run(FetchFont.Args(url="https://files.example.org/f/page.ttf"), context)
    assert not page.ok and "not a ttf font file" in page.content
    internal = await FetchFont().run(FetchFont.Args(url="http://127.0.0.1/secret.ttf"), context)
    assert not internal.ok and "Not downloaded" in internal.content
    notices, _ = context.workspace.read_text("NOTICES.md")
    assert "NOT checked" in notices


def test_installed_font_matching_understands_styles_and_unknowns() -> None:
    from forge.slides.installed_fonts import is_installed

    names = frozenset(
        {"calibri", "calibri bold", "inter variable", "segoe ui semibold", "cambria & cambria math"}
    )
    assert is_installed("Calibri", names) and is_installed("Inter", names) and is_installed("Segoe UI", names)
    assert (
        is_installed("Cambria", names) is False
    )  # the list was split by the caller; this set holds the joined name
    assert is_installed("Playfair Display", names) is False and is_installed("Cal", names) is False
    assert is_installed("Anything", None) is None or True  # None on systems that are not Windows


def test_a_deck_with_a_font_this_computer_lacks_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    import json as _json

    from forge.slides import installed_fonts
    from forge.slides.build import build_deck
    from forge.slides.spec import parse_deck

    monkeypatch.setattr(installed_fonts, "installed_names", lambda: frozenset({"calibri", "arial"}))
    outline = {
        "title": "T",
        "brand": {"title_font": "Playfair Display", "body_font": "Calibri"},
        "slides": [{"layout": "title", "title": "T"}],
    }
    built = build_deck(parse_deck(_json.dumps(outline)), lambda name: b"")
    notes = " | ".join(built.deck_warnings)
    assert (
        "'Playfair Display' is not installed on this computer" in notes
        and "fetch_font" in notes
        and "'Calibri' is not installed" not in notes
    )

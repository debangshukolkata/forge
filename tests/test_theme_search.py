"""TH1..TH5 (D-492): theme search, a read-only study that keeps facts only, and the overlap check that proves a page shares no code with the studied theme.

The network is a mock transport (the sites, not a model); no live site is called."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import httpx
import pytest

from forge.toolkit.base import ToolContext
from forge.tools import theme_sources as sources
from forge.tools.theme_search import ThemeSearch
from forge.workspace.create import create_workspace

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 40

THEME_JSON = {
    "settings": {
        "color": {
            "palette": [
                {"slug": "base", "color": "#FAF7F2", "name": "Base"},
                {"slug": "contrast", "color": "#1B1B1B", "name": "Contrast"},
                {"slug": "primary", "color": "#C2410C", "name": "Primary"},
            ]
        },
        "typography": {
            "fontFamilies": [{"slug": "serif", "fontFamily": "'Fraunces', Georgia, serif"}],
            "fontSizes": [{"slug": "large", "size": "2rem"}],
        },
        "layout": {"contentSize": "640px", "wideSize": "1200px"},
    }
}
STYLE_CSS = """/*
Theme Name: Solar Test
License: GNU General Public License v2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html
*/
.wp-block-cover.is-style-solar-hero .wp-block-cover__inner-container > h1 { margin-block: 0 var(--wp--preset--spacing--50); letter-spacing: -0.02em; }
"""
HERO = """<!-- wp:cover --><div><!-- wp:heading --><h1>Words of the theme</h1><!-- /wp:heading --><!-- wp:buttons --><!-- /wp:buttons --></div><!-- /wp:cover -->"""
GRID = """<!-- wp:columns --><!-- wp:column --><!-- /wp:column --><!-- wp:column --><!-- /wp:column --><!-- wp:column --><!-- /wp:column --><!-- /wp:columns -->"""

TREE = {
    "tree": [
        {"path": "theme.json", "type": "blob"},
        {"path": "style.css", "type": "blob"},
        {"path": "patterns/hero.php", "type": "blob"},
        {"path": "patterns/three-up.php", "type": "blob"},
        {"path": "assets/huge.png", "type": "blob"},
    ]
}
RAW = {
    "theme.json": json.dumps(THEME_JSON),
    "style.css": STYLE_CSS,
    "patterns/hero.php": HERO,
    "patterns/three-up.php": GRID,
}


def _package() -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for path, text in RAW.items():
            archive.writestr(f"solar-test/{path}", text)
    return out.getvalue()


def _handler(request: httpx.Request) -> httpx.Response:
    host, path = request.url.host, request.url.path
    if host == "api.wordpress.org" and request.url.params.get("action") == "query_themes":
        return httpx.Response(
            200,
            json={
                "themes": [
                    {
                        "name": "Solar Test",
                        "slug": "solar-test",
                        "author": {"display_name": "Someone"},
                        "preview_url": "//wp-themes.com/solar-test/",
                        "screenshot_url": "//ts.w.org/solar.png",
                        "tags": {"portfolio": "Portfolio", "minimal": "Minimal"},
                        "rating": 90,
                    }
                ]
            },
        )
    if host == "api.wordpress.org" and request.url.params.get("action") == "theme_information":
        return httpx.Response(
            200, json={"download_link": "https://downloads.wordpress.org/theme/solar-test.1.0.zip"}
        )
    if host == "downloads.wordpress.org":
        return httpx.Response(200, content=_package())
    if host == "public-api.wordpress.com":
        return httpx.Response(500)
    if host == "api.github.com" and path == "/search/repositories":
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "full_name": "acme/solar",
                        "name": "solar",
                        "owner": {"login": "acme"},
                        "topics": ["theme"],
                    }
                ]
            },
        )
    if host == "api.github.com" and "/git/trees/" in path:
        return httpx.Response(200, json=TREE)
    if host == "raw.githubusercontent.com":
        relative = path.split("/HEAD/", 1)[1]
        return httpx.Response(200, text=RAW[relative]) if relative in RAW else httpx.Response(404)
    if host == "ts.w.org":
        return httpx.Response(200, content=PNG)
    return httpx.Response(404)


@pytest.fixture
def context(original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ToolContext:
    monkeypatch.setattr(
        sources, "make_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(_handler))
    )
    return ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))


async def test_search_lists_the_public_sources_saves_pictures_and_survives_one_being_down(
    context: ToolContext,
) -> None:
    result = await ThemeSearch().run(ThemeSearch.Args(action="search", query="minimal portfolio"), context)
    assert result.ok, result.content
    assert "Solar Test (solar-test, wordpress.org)" in result.content and "acme/solar" not in result.content
    assert "solar (solar, github)" in result.content and "wordpress.com could not be read" in result.content
    assert "ONE ask_user call" in result.content and "Picture:" in result.content
    assert any((context.workspace.path_of(".") / ".forge" / "themes").glob("*.png")), result.content


async def test_a_term_from_the_host_never_leaves_in_a_search(context: ToolContext) -> None:
    context.sensitive_terms = ("ministry",)
    result = await ThemeSearch().run(ThemeSearch.Args(action="search", query="Ministry portal"), context)
    assert not result.ok and "sensitive" in result.content


@pytest.mark.parametrize("source", ["acme/solar", "https://github.com/acme/solar.git", "solar-test"])
async def test_study_keeps_facts_not_text_from_a_repository_or_a_package(
    context: ToolContext, source: str
) -> None:
    result = await ThemeSearch().run(ThemeSearch.Args(action="study", source=source), context)
    assert result.ok, result.content
    folder = context.workspace.path_of(".") / ".forge" / "inspiration"
    note = (folder / ("solar.md" if "/" in source else "solar-test.md")).read_text(encoding="utf-8")
    assert "#C2410C" in note and "Fraunces" in note and "contentSize: 640px" in note
    assert (
        "GNU General Public License" in note
        and "cover 1, heading 1, buttons 1" in note
        and "columns 1 (3 columns)" in note
    )
    assert "Words of the theme" not in note  # the theme's own text is not kept
    assert not list(context.workspace.path_of(".").rglob("hero.php"))  # no theme file lands in the project
    draft = next(folder.glob("*.DESIGN.md")).read_text(encoding="utf-8")
    assert "#C2410C" in draft and "Fraunces" in draft
    assert "Solar Test" in (folder / "LOG.md").read_text(encoding="utf-8")


async def test_the_overlap_check_passes_an_original_page_and_stops_copied_code(context: ToolContext) -> None:
    await ThemeSearch().run(ThemeSearch.Args(action="study", source="acme/solar"), context)
    root = context.workspace.path_of(".")
    (root / "index.html").write_text(
        "<main class='hero'><h1>Fresh bread at dawn</h1></main><style>.hero{padding:4rem 1rem;background:#faf7f2}</style>",
        encoding="utf-8",
    )
    assert (await ThemeSearch().run(ThemeSearch.Args(action="check"), context)).ok
    (root / "copy.css").write_text(
        STYLE_CSS.split("*/")[1] + ".extra{color:red}", encoding="utf-8"
    )  # the theme's own rule pasted in
    caught = await ThemeSearch().run(ThemeSearch.Args(action="check"), context)
    assert (
        not caught.ok
        and "TOO CLOSE" in caught.content
        and "copy.css" in caught.content
        and "index.html" not in caught.content
    )


async def test_check_without_a_study_says_what_to_do_first(context: ToolContext) -> None:
    result = await ThemeSearch().run(ThemeSearch.Args(action="check"), context)
    assert not result.ok and "study first" in result.content


def test_the_fingerprint_holds_hashes_and_ignores_layout_of_the_text() -> None:
    spaced = (
        "a { color : red ; margin : 0 auto ; padding : 1rem 2rem ; border : 1px solid blue ; display : grid }"
    )
    squeezed = "a{color:red;margin:0 auto;padding:1rem 2rem;border:1px solid blue;display:grid}"
    known = set(sources.fingerprint(spaced))
    assert all(isinstance(value, int) for value in known)
    assert sources.overlap(known, "x.css", squeezed).shared > 0
    assert sources.overlap(known, "y.css", "b{color:blue}").shared == 0


def test_parsers_survive_missing_fields() -> None:
    data: dict[str, Any] = {"themes": [{"slug": "x"}, {"name": "no slug"}, "junk"]}
    assert [t.slug for t in sources.parse_wporg(data)] == ["x"]
    assert sources.parse_wpcom({"themes": [{"id": "y", "taxonomies": {"a": [{"name": "Blog"}]}}]})[
        0
    ].tags == ["Blog"]
    assert sources.github_repo("https://example.com/a/b") == "" and sources.github_repo("a/b") == "a/b"

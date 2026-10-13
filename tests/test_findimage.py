"""D5 (D-328): find_image and fetch_image. The network is simulated at the transport (httpx MockTransport) with answers shaped like the
real services'; `scripts/dev/reach_smoke.py` is the check against the real ones."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest

from forge.config import Secrets
from forge.toolkit.base import ToolContext
from forge.tools import image_sources
from forge.tools.findimage import FetchImage, FindImage
from forge.tools.image_sources import licence_allowed, normalise_licence
from forge.workspace.create import create_workspace

SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M3 12l9-9 9 9"/></svg>'
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def _handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    host, path = request.url.host, request.url.path
    if host == "api.iconify.design" and path == "/search":
        return httpx.Response(200, json={"icons": ["lucide:house", "fa:home", "mdi:home"], "total": 3})
    if host == "api.iconify.design" and path == "/collections":
        return httpx.Response(
            200,
            json={
                "lucide": {
                    "name": "Lucide",
                    "author": {"name": "Lucide Contributors"},
                    "license": {"title": "ISC", "spdx": "ISC"},
                },
                "fa": {"name": "Font Awesome Pro", "license": {"title": "Commercial", "spdx": "Commercial"}},
                "mdi": {
                    "name": "Material Design Icons",
                    "author": {"name": "Pictogrammers"},
                    "license": {"title": "Apache 2.0", "spdx": "Apache-2.0"},
                },
            },
        )
    if host == "api.iconify.design" and path.endswith(".svg"):
        return httpx.Response(200, content=SVG, headers={"content-type": "image/svg+xml"})
    if host == "api.openverse.org":
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "abc-1",
                        "title": "Vineyard &amp; hills",
                        "creator": "Ana",
                        "url": "https://img.example.org/v.jpg",
                        "thumbnail": "https://api.openverse.org/t/abc-1",
                        "license": "by",
                        "license_version": "4.0",
                        "attribution": '"Vineyard" by Ana is licensed under CC BY 4.0.',
                        "foreign_landing_url": "https://example.org/p/1",
                        "width": 4000,
                        "height": 3000,
                        "category": "photograph",
                    },
                    {
                        "id": "abc-2",
                        "title": "No commercial",
                        "creator": "Bo",
                        "url": "https://img.example.org/n.jpg",
                        "license": "by-nc",
                        "license_version": "4.0",
                    },
                    {
                        "id": "abc-3",
                        "title": "Public",
                        "creator": "Cy",
                        "url": "https://img.example.org/p.jpg",
                        "license": "cc0",
                        "license_version": "1.0",
                        "category": "illustration",
                    },
                ]
            },
        )
    if host == "commons.wikimedia.org":
        return httpx.Response(
            200,
            json={
                "query": {
                    "pages": {
                        "1": {
                            "title": "File:Vines.jpg",
                            "index": 1,
                            "imageinfo": [
                                {
                                    "mime": "image/jpeg",
                                    "thumburl": "https://upload.wikimedia.org/t/Vines.jpg",
                                    "url": "https://upload.wikimedia.org/Vines.jpg",
                                    "descriptionurl": "https://commons.wikimedia.org/wiki/File:Vines.jpg",
                                    "thumbwidth": 2000,
                                    "thumbheight": 1300,
                                    "extmetadata": {
                                        "LicenseShortName": {"value": "CC BY 4.0"},
                                        "Artist": {"value": "<a href='x'>Dee</a>"},
                                    },
                                }
                            ],
                        },
                        "2": {
                            "title": "File:Closed.jpg",
                            "index": 2,
                            "imageinfo": [
                                {
                                    "mime": "image/jpeg",
                                    "url": "https://upload.wikimedia.org/c.jpg",
                                    "extmetadata": {"LicenseShortName": {"value": "All rights reserved"}},
                                }
                            ],
                        },
                    }
                }
            },
        )
    if host == "images-api.nasa.gov" and path == "/search":
        return httpx.Response(
            200,
            json={
                "collection": {
                    "items": [
                        {
                            "data": [{"nasa_id": "PIA1", "title": "Mars", "photographer": "JPL"}],
                            "links": [{"href": "https://images-assets.nasa.gov/PIA1~thumb.jpg"}],
                        }
                    ]
                }
            },
        )
    if host == "images-api.nasa.gov" and path.startswith("/asset/"):
        return httpx.Response(
            200,
            json={
                "collection": {
                    "items": [
                        {"href": "http://images-assets.nasa.gov/PIA1~orig.jpg"},
                        {"href": "http://images-assets.nasa.gov/PIA1~large.jpg"},
                    ]
                }
            },
        )
    if host == "api.pexels.com":
        assert request.headers["authorization"] == "pexels-key"
        return httpx.Response(
            200,
            json={
                "photos": [
                    {
                        "id": 7,
                        "alt": "A lake",
                        "photographer": "Eli",
                        "url": "https://pexels.com/photo/7",
                        "width": 5000,
                        "height": 3000,
                        "src": {
                            "large2x": "https://images.pexels.com/7.jpg",
                            "medium": "https://images.pexels.com/7m.jpg",
                        },
                    }
                ]
            },
        )
    if host == "api.unsplash.com":
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "u1",
                        "alt_description": "Hills",
                        "user": {"name": "Flo"},
                        "links": {
                            "html": "https://unsplash.com/photos/u1",
                            "download_location": "https://api.unsplash.com/photos/u1/download",
                        },
                        "urls": {
                            "regular": "https://images.unsplash.com/u1",
                            "small": "https://images.unsplash.com/u1s",
                        },
                        "width": 3000,
                        "height": 2000,
                    }
                ]
            },
        )
    if host == "pixabay.com":
        return httpx.Response(
            200,
            json={
                "hits": [
                    {
                        "id": 9,
                        "tags": "tree, field",
                        "user": "Gus",
                        "pageURL": "https://pixabay.com/p/9",
                        "largeImageURL": "https://pixabay.com/9.jpg",
                        "type": "vector/svg",
                        "imageWidth": 1200,
                        "imageHeight": 800,
                    }
                ]
            },
        )
    if host in (
        "img.example.org",
        "upload.wikimedia.org",
        "images-assets.nasa.gov",
        "images.pexels.com",
        "images.unsplash.com",
        "pixabay.com",
    ) or url.endswith(".jpg"):
        return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})
    if path.endswith("/download"):
        return httpx.Response(200, json={"url": "x"})
    return httpx.Response(404)


def _use(monkeypatch: pytest.MonkeyPatch, handler: Any = _handler) -> None:
    monkeypatch.setattr(
        image_sources,
        "make_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True),
    )


def _context(original_repo: Path, tmp_path: Path, values: dict[str, str] | None = None) -> ToolContext:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    return ToolContext(workspace=workspace, secrets=Secrets(values or {}, None))


def test_licence_names_are_understood_and_only_free_commercial_ones_pass() -> None:
    assert normalise_licence("CC BY 4.0") == "cc-by-4.0" and normalise_licence("cc0") == "cc0-1.0"
    for ok in ("MIT", "ISC", "Apache-2.0", "CC0-1.0", "by-4.0", "Pexels License"):
        assert licence_allowed(ok), ok
    for bad in ("by-nc-4.0", "by-nd-2.0", "by-sa-4.0", "Commercial", "", "All rights reserved", "GPL-3.0"):
        assert not licence_allowed(bad), bad


async def test_keyless_sources_are_searched_together_with_licences_and_credit(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use(monkeypatch)
    context = _context(original_repo, tmp_path)
    result = await FindImage().run(FindImage.Args(query="vineyard", limit=12), context)
    assert result.ok, result.content
    text = result.content
    assert (
        "iconify:lucide:house" in text and "iconify:mdi:home" in text and "fa:home" not in text
    )  # a paid set is left out
    assert (
        "openverse:abc-1" in text and "abc-2" not in text and "openverse:abc-3" in text
    )  # non-commercial left out
    assert "wikimedia:Vines.jpg" in text and "Closed.jpg" not in text and "nasa:PIA1" in text
    assert "credit: Lucide icons by Lucide Contributors (ISC)" in text and "no credit needed" in text
    assert "pexels (add PEXELS_API_KEY" in text and "Vineyard & hills" in text
    assert "openverse:abc-1" in context.image_candidates


async def test_keyed_sources_join_when_their_key_is_in_the_env(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use(monkeypatch)
    keys = {
        "PEXELS_API_KEY": "pexels-key",
        "UNSPLASH_ACCESS_KEY": "u-key",
        "PIXABAY_API_KEY": "p-key",
    }  # check_secrets: fake
    result = await FindImage().run(
        FindImage.Args(query="lake", kind="photo", limit=15), _context(original_repo, tmp_path, keys)
    )
    assert "pexels:7" in result.content and "unsplash:u1" in result.content and "pixabay:9" in result.content
    assert "Photo by Eli on Pexels" in result.content and "iconify" not in result.content


async def test_a_blocked_source_is_named_with_the_reason_and_the_others_still_answer(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.openverse.org":
            raise httpx.ConnectError(
                "[SSL: CERTIFICATE_VERIFY_FAILED] self signed certificate in certificate chain"
            )
        if request.url.host == "commons.wikimedia.org":
            return httpx.Response(403)
        if request.url.host == "images-api.nasa.gov":
            return httpx.Response(200, text="<html>Please log in to the proxy</html>")
        return _handler(request)

    _use(monkeypatch, handler)
    result = await FindImage().run(FindImage.Args(query="vineyard"), _context(original_repo, tmp_path))
    assert result.ok and "iconify:lucide:house" in result.content and "Not reached:" in result.content
    assert "openverse could not be reached" in result.content and "certificate" in result.content
    assert (
        "wikimedia refused the request (403)" in result.content
        and "nasa did not answer with data" in result.content
    )


async def test_when_nothing_answers_the_tool_says_so(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("getaddrinfo failed")

    _use(monkeypatch, down)
    result = await FindImage().run(FindImage.Args(query="vineyard"), _context(original_repo, tmp_path))
    assert (
        result.ok and "Nothing found" in result.content and result.content.count("could not be reached") == 4
    )


async def test_fetch_saves_the_file_records_the_licence_and_returns_the_credit(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use(monkeypatch)
    context = _context(original_repo, tmp_path)
    await FindImage().run(FindImage.Args(query="home", limit=15), context)
    icon = await FetchImage().run(
        FetchImage.Args(id="iconify:lucide:house", path="assets/house.png"), context
    )
    assert icon.ok, icon.content
    assert (
        context.workspace.path_of("assets/house.svg").read_bytes() == SVG
    )  # the extension follows the content
    assert "Credit line to show with it: Lucide icons by Lucide Contributors (ISC)" in icon.content
    photo = await FetchImage().run(FetchImage.Args(id="openverse:abc-1", path="assets/vines.jpg"), context)
    assert photo.ok and (context.workspace.path_of("assets/vines.png")).exists()
    notices, _ = context.workspace.read_text("NOTICES.md")
    assert (
        "`assets/house.svg`" in notices
        and "ISC" in notices
        and "`assets/vines.png`" in notices
        and "CC BY" in notices.upper()
    )
    again = await FetchImage().run(
        FetchImage.Args(id="iconify:lucide:house", path="assets/house.svg"), context
    )
    assert again.ok and notices.count("assets/house.svg") == (
        context.workspace.read_text("NOTICES.md")[0]
    ).count("assets/house.svg")


async def test_nasa_picks_a_large_file_and_unsplash_gets_its_ping(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return _handler(request)

    _use(monkeypatch, handler)
    context = _context(original_repo, tmp_path, {"UNSPLASH_ACCESS_KEY": "u-key"})  # check_secrets: fake
    await FindImage().run(FindImage.Args(query="mars hills", sources=["nasa", "unsplash"]), context)
    assert (await FetchImage().run(FetchImage.Args(id="nasa:PIA1", path="mars.jpg"), context)).ok
    assert any(url.endswith("PIA1~large.jpg") for url in seen)
    assert (await FetchImage().run(FetchImage.Args(id="unsplash:u1", path="hills.jpg"), context)).ok
    assert any(url.endswith("/photos/u1/download") for url in seen)


@pytest.mark.parametrize(
    ("answer", "message"),
    [
        (
            httpx.Response(
                200,
                content=b"<svg><script>alert(1)</script></svg>",
                headers={"content-type": "image/svg+xml"},
            ),
            "script",
        ),
        (
            httpx.Response(200, content=b"<html>login</html>", headers={"content-type": "text/html"}),
            "did not give a picture",
        ),
        (httpx.Response(404), "404"),
        (httpx.Response(302, headers={"location": "http://127.0.0.1/admin.png"}), "not allowed"),
        (
            httpx.Response(
                200, content=b"x" * 100, headers={"content-type": "image/png", "content-length": "100"}
            ),
            "",
        ),
    ],
)
async def test_unsafe_or_wrong_downloads_are_refused(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, answer: httpx.Response, message: str
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return answer if request.url.path.endswith(".svg") else _handler(request)

    _use(monkeypatch, handler)
    context = _context(original_repo, tmp_path)
    await FindImage().run(FindImage.Args(query="home", sources=["iconify"]), context)
    result = await FetchImage().run(FetchImage.Args(id="iconify:lucide:house", path="a.svg"), context)
    if message:
        assert not result.ok and message in result.content
    else:
        assert result.ok


async def test_unknown_ids_and_host_terms_are_refused(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use(monkeypatch)
    context = _context(original_repo, tmp_path)
    assert (
        "search with find_image first"
        in (await FetchImage().run(FetchImage.Args(id="iconify:x:y", path="a.svg"), context)).content
    )
    context.sensitive_terms = ["AcmeBank"]
    blocked = await FindImage().run(FindImage.Args(query="AcmeBank logo"), context)
    assert not blocked.ok and "host-identifying" in blocked.content

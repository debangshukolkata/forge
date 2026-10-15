"""D-436: AI-image libraries as SAMPLE sources: found after the licensed ones, marked, recorded in NOTICES.md as samples to replace."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from forge.tools import image_sources
from forge.tools.findimage import FetchImage, FindImage
from forge.tools.sample_sources import SAMPLE_SOURCES, imagemythos, kaleido, okslop
from tests.test_findimage import _context, _use

PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 64

OKSLOP_JSON = {
    "results": [
        {
            "id": "abc1",
            "width": 1024,
            "height": 768,
            "alt_description": "Sourdough loaf on a board",
            "is_design": None,
            "urls": {
                "full": "https://okslop.com/img/abc1/full",
                "regular": "https://okslop.com/img/abc1/preview",
                "small": "https://okslop.com/img/abc1/thumb",
            },
            "links": {"html": "https://okslop.com/image/sourdough-loaf"},
        }
    ]
}
KALEIDO_JSON = {
    "results": [
        {"id": 7, "url": "/image/k7_peach.webp?t=1", "style": "food_photography", "dominant_color": "peach"}
    ]
}
MYTHOS_HTML = (
    '<script>{"itemListElement":[{"@type":"ListItem","position":1,"url":"https://www.imagemythos.com/image/snowy-mountain-sunset-20261015-1-77",'
    '"name":"Snowy Mountain Sunset","image":"https://s.imagemythos.com/artify/aaaa-1111.jpeg"}]}</script>'
)


def handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if "okslop.com/api/v1/search/photos" in url:
        return httpx.Response(200, json=OKSLOP_JSON)
    if "kaleidoimages.ai/search" in url:
        assert "-nsfw" in url  # the safety terms are always added
        return httpx.Response(200, json=KALEIDO_JSON)
    if "imagemythos.com/category/nature" in url:
        return httpx.Response(200, text=MYTHOS_HTML)
    if url.startswith(
        ("https://okslop.com/img/", "https://kaleidoimages.ai/image/", "https://s.imagemythos.com/")
    ):
        return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})
    return httpx.Response(404, json={})


async def test_each_provider_turns_its_answer_into_marked_candidates() -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        first = (await okslop(client, "sourdough", 6))[0]
        second = (await kaleido(client, "sourdough", 6))[0]
        third = (await imagemythos(client, "snowy mountain landscape", 6))[0]
        assert await imagemythos(client, "sourdough bread", 6) == []  # no category fits: nothing is invented
    assert first.id == "okslop:abc1" and first.download_url.endswith("/full") and first.extra["sample"]
    assert (
        second.download_url == "https://kaleidoimages.ai/image/k7_peach.webp?t=1"
        and "not confirmed" in second.licence
    )
    assert (
        third.download_url.endswith("aaaa-1111.jpeg")
        and third.licence.startswith("CC0")
        and third.kind == "photo"
    )
    assert all("[SAMPLE: replace before publishing]" in c.describe() for c in (first, second, third))


async def test_find_image_lists_samples_after_the_licensed_pictures_and_fetch_records_them(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def combined(request: httpx.Request) -> httpx.Response:
        if "openverse" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "ov1",
                            "title": "Bread",
                            "creator": "Ann",
                            "license": "cc0",
                            "license_version": "1.0",
                            "url": "https://img.example/bread.jpg",
                            "thumbnail": "https://img.example/t.jpg",
                            "foreign_landing_url": "https://example.org/bread",
                            "width": 1200,
                            "height": 800,
                        }
                    ]
                },
            )
        return handler(request)

    _use(monkeypatch, combined)
    context = _context(original_repo, tmp_path)
    result = await FindImage().run(FindImage.Args(query="sourdough", kind="photo", sources=[]), context)
    lines = [line for line in result.content.splitlines() if line[:2].strip().rstrip(".").isdigit()]
    kinds = ["SAMPLE" in line for line in lines]
    assert any(kinds) and kinds == sorted(kinds), "every licensed picture comes before the first sample"
    sample_id = next(line.split(". ", 1)[1].split(" - ")[0] for line in lines if "SAMPLE" in line)
    saved = await FetchImage().run(FetchImage.Args(id=sample_id, path="public/loaf.png"), context)
    assert saved.ok and "SAMPLE picture" in saved.content and "brand-assets" in saved.content
    notices, _ = context.workspace.read_text("NOTICES.md")
    assert "SAMPLE PICTURE: replace before publishing" in notices and "public/loaf." in notices


def test_the_sample_sources_are_registered_and_the_agent_string_does_not_name_httpx() -> None:
    assert set(SAMPLE_SOURCES) <= set(image_sources.PROVIDERS)
    assert "httpx" not in image_sources.USER_AGENT.lower() and "github.com" in image_sources.USER_AGENT
    assert json.loads(json.dumps(KALEIDO_JSON))  # keep the fixtures valid JSON

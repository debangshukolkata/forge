"""Sample pictures (D-436): AI-generated image libraries used so a page feels real before the user's own pictures exist.

The user's decision (2026-10-15): a page built with sample pictures is better than a page of grey boxes, and the user replaces them. So these sources are
offered by `find_image` after every licensed source, each result is marked SAMPLE with what its terms allow, `fetch_image` records the picture in NOTICES.md as a
sample to replace, and the closing message lists them. They are not a substitute for licensed pictures on a page that ships.

- OKSLOP (okslop.com): a documented REST API, Unsplash-shaped; commercial use without credit, but the user indemnifies the site, nothing is warranted, and images can be
  removed. An optional `OKSLOP_API_KEY` in the .env file raises the limits; search works without it.
- KaleidoImages (kaleidoimages.ai): a personal project with an open API; it says only that images are free to use, so commercial use is NOT confirmed: sample only.
- ImageMythos (imagemythos.com): CC0 as the site states; it has no API and its robots.txt disallows /search, /api/ and /download/, so only its three category pages are read
  (nature, architecture, art), a few requests at a time, and the image files come from its image host. It has no food or product pictures: landscapes, abstract art and buildings.
- Generated Gallery (generatedgallery.com) is not searched: it indexes other people's uploads from Civitai and PromptHero with their own terms and mixed content."""

from __future__ import annotations

import re
from html import unescape

import httpx

from forge.tools.image_sources import Candidate, Provider, SourceError, _get_json

OKSLOP = "https://okslop.com/api/v1/search/photos"
KALEIDO = "https://kaleidoimages.ai"
MYTHOS = "https://www.imagemythos.com"
SAMPLE_SOURCES = ("okslop", "kaleido", "imagemythos")
OPTIONAL_KEY_NAMES = {"okslop": "OKSLOP_API_KEY"}
MAX_PER_SOURCE = 3
KALEIDO_EXCLUDE = " -nsfw -nude -naked -erotic"  # the search has no safety filter of its own
CATEGORY_WORDS = {
    "nature": {
        "nature",
        "landscape",
        "mountain",
        "forest",
        "sea",
        "ocean",
        "beach",
        "sky",
        "sunset",
        "snow",
        "meadow",
        "river",
        "tree",
        "desert",
        "dunes",
        "aurora",
        "scenery",
    },
    "architecture": {
        "architecture",
        "building",
        "buildings",
        "city",
        "pavilion",
        "interior",
        "house",
        "tower",
        "bridge",
        "concrete",
        "glass",
    },
    "art": {
        "abstract",
        "art",
        "pattern",
        "texture",
        "geometric",
        "gradient",
        "background",
        "shape",
        "shapes",
        "minimal",
    },
}


def _words(text: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", text.lower()) if len(w) > 2}


def _sample(candidate: Candidate) -> Candidate:
    candidate.extra["sample"] = True
    return candidate


async def okslop(client: httpx.AsyncClient, query: str, limit: int, key: str = "") -> list[Candidate]:
    params: dict[str, str | int] = {"query": query, "per_page": min(limit, MAX_PER_SOURCE * 2)}
    response = await client.get(
        OKSLOP, params=params, headers={"Authorization": f"Client-ID {key}"} if key else None
    )
    if (
        response.status_code in (401, 403) and key
    ):  # a key the site does not accept: the keyless search still works
        response = await client.get(OKSLOP, params=params)
    data = _get_json(response, "okslop")
    found: list[Candidate] = []
    for item in (data.get("results") or [])[:MAX_PER_SOURCE]:
        urls = item.get("urls") or {}
        download = urls.get("full") or urls.get("regular")
        if not download:
            continue
        title = str(item.get("alt_description") or item.get("description") or "AI-generated picture")[:110]
        found.append(
            _sample(
                Candidate(
                    id=f"okslop:{item['id']}",
                    source="okslop",
                    kind="illustration" if item.get("is_design") else "photo",
                    title=title,
                    licence="OKSLOP licence: commercial use, no credit; AI-generated",
                    page_url=str((item.get("links") or {}).get("html", "")),
                    download_url=str(download),
                    preview_url=str(urls.get("small", "")),
                    width=int(item.get("width") or 0),
                    height=int(item.get("height") or 0),
                    attribution="",
                    extra={"fallback": str(urls.get("regular", ""))},
                )
            )
        )
    return found


async def kaleido(client: httpx.AsyncClient, query: str, limit: int, key: str = "") -> list[Candidate]:
    response = await client.get(
        f"{KALEIDO}/search", params={"q": query + KALEIDO_EXCLUDE, "limit": MAX_PER_SOURCE}
    )
    data = _get_json(response, "kaleido")
    found: list[Candidate] = []
    for item in (data.get("results") or [])[:MAX_PER_SOURCE]:
        url = str(item.get("url", ""))
        if not url:
            continue
        style = str(item.get("style", "")).replace("_", " ")
        found.append(
            _sample(
                Candidate(
                    id=f"kaleido:{item.get('id')}",
                    source="kaleido",
                    kind="photo",
                    title=f"AI picture, {style or 'style unknown'}, {str(item.get('dominant_color', '')).replace('_', ' ')}"[
                        :110
                    ],
                    licence="no licence stated: sample only, commercial use not confirmed",
                    page_url=KALEIDO,
                    download_url=KALEIDO + url,
                    attribution="",
                )
            )
        )
    return found


_MYTHOS_ITEM = re.compile(
    r'"@type":"ListItem","position":\d+,"url":"(https://www\.imagemythos\.com/image/[^"]+)","name":"([^"]+)","image":"(https://s\.imagemythos\.com/artify/[^"]+)"'
)


def _mythos_category(query: str) -> str:
    wanted = _words(query)
    best = max(CATEGORY_WORDS, key=lambda name: len(wanted & CATEGORY_WORDS[name]))
    return best if wanted & CATEGORY_WORDS[best] else ""


async def imagemythos(client: httpx.AsyncClient, query: str, limit: int, key: str = "") -> list[Candidate]:
    """Landscapes, buildings and abstract art only: the category pages are the part of the site its robots.txt allows (no search)."""
    category = _mythos_category(query)
    if not category:
        return []
    response = await client.get(f"{MYTHOS}/category/{category}")
    if response.status_code >= 400:
        raise SourceError(f"imagemythos answered {response.status_code}")
    wanted = _words(query)
    seen: set[str] = set()
    scored: list[tuple[int, Candidate]] = []
    for page, name, image in _MYTHOS_ITEM.findall(response.text):
        if image in seen:
            continue
        seen.add(image)
        title = unescape(name)
        scored.append(
            (
                len(wanted & _words(title)),
                _sample(
                    Candidate(
                        id=f"imagemythos:{page.rsplit('-', 1)[-1]}",
                        source="imagemythos",
                        kind="photo" if category == "nature" else "illustration",
                        title=title[:110],
                        licence="CC0 (as stated by the site); AI-generated",
                        page_url=page,
                        download_url=image,
                        attribution="",
                    )
                ),
            )
        )
    scored.sort(key=lambda row: -row[0])
    return [candidate for _, candidate in scored[:MAX_PER_SOURCE]]


SAMPLE_PROVIDERS: dict[str, Provider] = {"okslop": okslop, "kaleido": kaleido, "imagemythos": imagemythos}

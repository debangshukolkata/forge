"""Where pictures come from (TODO D5, D-328): free sources of icons, cliparts and photos, each with its licence.

Every provider turns one search into `Candidate`s that say what the picture is, who made it, under which licence and where the file is.
Sources that need no key: Iconify (icons and vector clip art, licence per icon set), Openverse (photos and drawings, Creative Commons
and public domain), Wikimedia Commons, NASA. Sources with a free key that goes in the .env file: Pexels (`PEXELS_API_KEY`), Unsplash
(`UNSPLASH_ACCESS_KEY`), Pixabay (`PIXABAY_API_KEY`). Only licences that allow commercial use and changes are offered: CC0, public
domain, CC BY, MIT, ISC, Apache-2.0 and the three photo sites' own licences. Anything else (non-commercial, no-derivatives,
share-alike, unknown) is left out, because a picture in a company deck must not carry a surprise."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from html import unescape
from typing import Any
from urllib.parse import quote

import httpx

USER_AGENT = "DebCraft/1.0 (https://github.com/debangshukolkata/forge; open-licence image search) httpx"  # Wikimedia refuses anonymous agents
TIMEOUT_S = 15.0
ICONIFY = "https://api.iconify.design"
OPENVERSE = "https://api.openverse.org/v1/images/"
WIKIMEDIA = "https://commons.wikimedia.org/w/api.php"
NASA = "https://images-api.nasa.gov"
PEXELS = "https://api.pexels.com/v1/search"
UNSPLASH = "https://api.unsplash.com/search/photos"
PIXABAY = "https://pixabay.com/api/"
KEY_NAMES = {"pexels": "PEXELS_API_KEY", "unsplash": "UNSPLASH_ACCESS_KEY", "pixabay": "PIXABAY_API_KEY"}
KEYLESS = ("iconify", "openverse", "wikimedia", "nasa")
ICON_SOURCES = ("iconify",)
PHOTO_SOURCES = ("openverse", "wikimedia", "nasa", "pexels", "unsplash", "pixabay")
ALLOWED_LICENCES = {  # SPDX-like keys, lower case
    "cc0-1.0",
    "cc0",
    "pdm",
    "public domain",
    "cc-by-4.0",
    "cc-by-3.0",
    "cc-by-2.0",
    "cc-by-2.5",
    "mit",
    "isc",
    "apache-2.0",
    "unsplash license",
    "pexels license",
    "pixabay license",
    "nasa media usage guidelines",
}
NEEDS_ATTRIBUTION = {
    "cc-by-4.0",
    "cc-by-3.0",
    "cc-by-2.0",
    "cc-by-2.5",
    "mit",
    "isc",
    "apache-2.0",
}  # credit or keep the notice
PREFERRED_ICON_SETS = (
    "lucide",
    "tabler",
    "ph",
    "mdi",
    "heroicons",
    "bi",
    "fluent",
    "carbon",
    "solar",
    "iconoir",
)


@dataclass
class Candidate:
    id: str  # "source:reference": what fetch_image is given
    source: str
    kind: str  # icon, photo or illustration
    title: str
    licence: str
    author: str = ""
    page_url: str = ""
    download_url: str = ""
    preview_url: str = ""
    width: int = 0
    height: int = 0
    attribution: str = ""  # the credit line to place near the picture; empty when none is needed
    extra: dict[str, Any] = field(
        default_factory=dict
    )  # what the download step needs (a tracking address, a file title)

    def describe(self) -> str:
        size = f", {self.width}x{self.height}" if self.width else ""
        credit = f"; credit: {self.attribution}" if self.attribution else "; no credit needed"
        by = f" by {self.author}" if self.author else ""
        return f"{self.id} - {self.kind}: {self.title}{by} ({self.licence}{size}){credit}"


class SourceError(Exception):
    """A source could not be searched; the message says why (blocked, key missing or rejected, rate limit)."""


Provider = Callable[[httpx.AsyncClient, str, int, str], Awaitable[list[Candidate]]]


def normalise_licence(raw: str) -> str:
    text = re.sub(r"\s+", " ", (raw or "").strip().lower())
    text = text.replace("creative commons ", "cc ").replace("attribution", "by")
    match = re.match(r"^(?:cc[ -]?)?(by|0|zero|pdm)(?:[ -]([0-9.]+))?$", text)
    if match:
        kind, version = match.groups()
        if kind in ("0", "zero"):
            return "cc0-1.0"
        if kind == "pdm":
            return "pdm"
        return f"cc-by-{version}" if version else "cc-by-4.0"
    return text


def licence_allowed(raw: str) -> bool:
    return normalise_licence(raw) in ALLOWED_LICENCES


def _get_json(response: httpx.Response, source: str) -> Any:
    if response.status_code in (401, 403):
        raise SourceError(
            f"{source} refused the request ({response.status_code}): the key is missing or wrong, or the network blocks it"
        )
    if response.status_code == 429:
        raise SourceError(f"{source} says too many requests (429): try again later")
    if response.status_code >= 400:
        raise SourceError(f"{source} answered {response.status_code}")
    try:
        return response.json()
    except ValueError as error:
        raise SourceError(f"{source} did not answer with data (a proxy or login page in between?)") from error


# --- Iconify: icons and vector clip art ---


async def iconify(client: httpx.AsyncClient, query: str, limit: int, key: str = "") -> list[Candidate]:
    found = _get_json(
        await client.get(f"{ICONIFY}/search", params={"query": query, "limit": min(limit * 6, 64)}), "iconify"
    )
    names: list[str] = list(found.get("icons", []))
    prefixes = sorted({name.split(":")[0] for name in names})
    sets = (
        _get_json(
            await client.get(f"{ICONIFY}/collections", params={"prefixes": ",".join(prefixes)}), "iconify"
        )
        if prefixes
        else {}
    )
    candidates: list[Candidate] = []
    for name in sorted(names, key=lambda n: _icon_rank(n.split(":")[0])):
        prefix, icon = name.split(":", 1)
        info = sets.get(prefix, {})
        licence = (info.get("license") or {}).get("spdx") or (info.get("license") or {}).get("title") or ""
        if not licence_allowed(licence):
            continue
        author = (info.get("author") or {}).get("name", "")
        normal = normalise_licence(licence)
        credit = (
            f"{info.get('name', prefix)} icons by {author} ({licence})"
            if normal in NEEDS_ATTRIBUTION and author
            else ""
        )
        candidates.append(
            Candidate(
                id=f"iconify:{prefix}:{icon}",
                source="iconify",
                kind="icon",
                title=f"{icon} ({info.get('name', prefix)})",
                licence=licence,
                author=author,
                page_url=f"https://icon-sets.iconify.design/{prefix}/{icon}/",
                download_url=f"{ICONIFY}/{prefix}/{icon}.svg",
                preview_url=f"{ICONIFY}/{prefix}/{icon}.svg",
                attribution=credit,
            )
        )
        if len(candidates) >= limit:
            break
    return candidates


def _icon_rank(prefix: str) -> int:
    return PREFERRED_ICON_SETS.index(prefix) if prefix in PREFERRED_ICON_SETS else len(PREFERRED_ICON_SETS)


# --- Openverse: Creative Commons photos and drawings ---


async def openverse(client: httpx.AsyncClient, query: str, limit: int, key: str = "") -> list[Candidate]:
    params: dict[str, Any] = {
        "q": query,
        "license": "cc0,pdm,by",
        "page_size": min(limit * 2, 20),
        "mature": "false",
    }
    data = _get_json(await client.get(OPENVERSE, params=params), "openverse")
    candidates: list[Candidate] = []
    for item in data.get("results", []):
        licence = f"{item.get('license', '')}-{item.get('license_version', '')}".strip("-")
        if not licence_allowed(licence) or not item.get("url"):
            continue
        normal = normalise_licence(licence)
        candidates.append(
            Candidate(
                id=f"openverse:{item['id']}",
                source="openverse",
                kind="illustration"
                if item.get("category") in ("illustration", "digitized_artwork")
                else "photo",
                title=unescape(item.get("title") or "untitled"),
                licence=licence.upper(),
                author=item.get("creator") or "",
                page_url=item.get("foreign_landing_url") or "",
                download_url=item["url"],
                preview_url=item.get("thumbnail") or "",
                width=int(item.get("width") or 0),
                height=int(item.get("height") or 0),
                attribution=unescape(item.get("attribution") or "") if normal in NEEDS_ATTRIBUTION else "",
                extra={"fallback": item.get("thumbnail") or ""},  # Openverse keeps its own smaller copy
            )
        )
        if len(candidates) >= limit:
            break
    return candidates


# --- Wikimedia Commons ---


def _plain(text: str) -> str:
    return unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


async def wikimedia(client: httpx.AsyncClient, query: str, limit: int, key: str = "") -> list[Candidate]:
    params: dict[str, Any] = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap|drawing {query}",
        "gsrnamespace": 6,
        "gsrlimit": min(limit * 3, 30),
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|size|mime",
        "iiurlwidth": 2000,
    }
    data = _get_json(await client.get(WIKIMEDIA, params=params), "wikimedia")
    pages = sorted((data.get("query", {}).get("pages", {})).values(), key=lambda p: p.get("index", 0))
    candidates: list[Candidate] = []
    for page in pages:
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        licence = (meta.get("LicenseShortName") or {}).get("value", "")
        if not licence_allowed(licence.replace("CC BY ", "cc-by-").replace("CC0", "cc0")) or not info.get(
            "mime", ""
        ).startswith("image/"):
            continue
        author = _plain((meta.get("Artist") or {}).get("value", ""))
        normal = normalise_licence(licence.replace("CC BY ", "cc-by-"))
        title = page.get("title", "").removeprefix("File:")
        candidates.append(
            Candidate(
                id=f"wikimedia:{title}",
                source="wikimedia",
                kind="illustration" if info.get("mime") == "image/svg+xml" else "photo",
                title=title,
                licence=licence,
                author=author,
                page_url=info.get("descriptionurl", ""),
                download_url=info.get("thumburl") or info.get("url", ""),
                preview_url=info.get("thumburl") or "",
                width=int(info.get("thumbwidth") or info.get("width") or 0),
                height=int(info.get("thumbheight") or info.get("height") or 0),
                attribution=f"{title} by {author or 'unknown'}, {licence}, Wikimedia Commons"
                if normal in NEEDS_ATTRIBUTION
                else "",
            )
        )
        if len(candidates) >= limit:
            break
    return candidates


# --- NASA ---


async def nasa(client: httpx.AsyncClient, query: str, limit: int, key: str = "") -> list[Candidate]:
    data = _get_json(
        await client.get(f"{NASA}/search", params={"q": query, "media_type": "image", "page_size": limit}),
        "nasa",
    )
    candidates: list[Candidate] = []
    for item in data.get("collection", {}).get("items", [])[:limit]:
        meta = (item.get("data") or [{}])[0]
        links = item.get("links") or [{}]
        nasa_id = meta.get("nasa_id", "")
        candidates.append(
            Candidate(
                id=f"nasa:{nasa_id}",
                source="nasa",
                kind="photo",
                title=meta.get("title", "NASA image"),
                licence="NASA media usage guidelines",
                author=meta.get("photographer") or meta.get("secondary_creator") or "NASA",
                page_url=f"https://images.nasa.gov/details/{quote(nasa_id)}",
                download_url=links[0].get("href", ""),
                preview_url=links[0].get("href", ""),
                attribution=f"Image: NASA ({nasa_id})",
                extra={"asset_url": f"{NASA}/asset/{quote(nasa_id)}"},
            )
        )
    return candidates


# --- Pexels, Unsplash, Pixabay (free keys) ---


async def pexels(client: httpx.AsyncClient, query: str, limit: int, key: str = "") -> list[Candidate]:
    data = _get_json(
        await client.get(PEXELS, params={"query": query, "per_page": limit}, headers={"Authorization": key}),
        "pexels",
    )
    return [
        Candidate(
            id=f"pexels:{photo['id']}",
            source="pexels",
            kind="photo",
            title=photo.get("alt") or "Pexels photo",
            licence="Pexels License",
            author=photo.get("photographer", ""),
            page_url=photo.get("url", ""),
            download_url=(photo.get("src") or {}).get("large2x")
            or (photo.get("src") or {}).get("original", ""),
            preview_url=(photo.get("src") or {}).get("medium", ""),
            width=int(photo.get("width") or 0),
            height=int(photo.get("height") or 0),
            attribution=f"Photo by {photo.get('photographer', 'unknown')} on Pexels",
        )
        for photo in data.get("photos", [])[:limit]
    ]


async def unsplash(client: httpx.AsyncClient, query: str, limit: int, key: str = "") -> list[Candidate]:
    data = _get_json(
        await client.get(
            UNSPLASH,
            params={"query": query, "per_page": limit},
            headers={"Authorization": f"Client-ID {key}"},
        ),
        "unsplash",
    )
    return [
        Candidate(
            id=f"unsplash:{photo['id']}",
            source="unsplash",
            kind="photo",
            title=photo.get("alt_description") or photo.get("description") or "Unsplash photo",
            licence="Unsplash License",
            author=(photo.get("user") or {}).get("name", ""),
            page_url=(photo.get("links") or {}).get("html", ""),
            download_url=(photo.get("urls") or {}).get("regular", ""),
            preview_url=(photo.get("urls") or {}).get("small", ""),
            width=int(photo.get("width") or 0),
            height=int(photo.get("height") or 0),
            attribution=f"Photo by {(photo.get('user') or {}).get('name', 'unknown')} on Unsplash",
            extra={"track": (photo.get("links") or {}).get("download_location", ""), "key": key},
        )
        for photo in data.get("results", [])[:limit]
    ]


async def pixabay(client: httpx.AsyncClient, query: str, limit: int, key: str = "") -> list[Candidate]:
    data = _get_json(
        await client.get(
            PIXABAY, params={"key": key, "q": query, "per_page": max(3, limit), "safesearch": "true"}
        ),
        "pixabay",
    )
    return [
        Candidate(
            id=f"pixabay:{hit['id']}",
            source="pixabay",
            kind="illustration" if hit.get("type") in ("illustration", "vector/svg") else "photo",
            title=hit.get("tags") or "Pixabay picture",
            licence="Pixabay License",
            author=hit.get("user", ""),
            page_url=hit.get("pageURL", ""),
            download_url=hit.get("largeImageURL") or hit.get("webformatURL", ""),
            preview_url=hit.get("previewURL", ""),
            width=int(hit.get("imageWidth") or 0),
            height=int(hit.get("imageHeight") or 0),
            attribution="",
        )
        for hit in data.get("hits", [])[:limit]
    ]


PROVIDERS: dict[str, Provider] = {
    "iconify": iconify,
    "openverse": openverse,
    "wikimedia": wikimedia,
    "nasa": nasa,
    "pexels": pexels,
    "unsplash": unsplash,
    "pixabay": pixabay,
}


def make_client() -> httpx.AsyncClient:
    """The HTTP client for the sources; tests replace this with one on a mock transport (the network, not a model)."""
    from forge.net import use_system_certificates

    use_system_certificates()  # a company network that inspects HTTPS: trust what Windows trusts
    return httpx.AsyncClient(timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}, follow_redirects=True)

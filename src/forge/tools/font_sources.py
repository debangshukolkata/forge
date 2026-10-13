"""Where fonts come from (TODO L3, D-330): the Fontsource catalogue, about 2,100 open-licence families (Google Fonts and others).

`api.fontsource.org` lists every family with its category, scripts (latin, devanagari, bengali, cyrillic, korean, ...), weights, whether
it is variable and its licence, and gives download addresses for each weight and script as woff2 (web), woff and ttf (desktop). Only
families under a licence that allows embedding and redistribution are offered (OFL-1.1, Apache-2.0, MIT, ISC, UFL-1.0). The catalogue
(about 500 KB) is fetched once and kept for a week in DebCraft's own folder, so searching works offline after the first time; before
the first time the 14 families that ship with the web skills answer."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from forge.config import forge_home

API = "https://api.fontsource.org/v1/fonts"
USER_AGENT = "DebCraft/1.0 (https://github.com/debangshukolkata/forge; font search) httpx"
TIMEOUT_S = 30.0
CACHE_DAYS = 7
ALLOWED_LICENCES = {"ofl-1.1", "apache-2.0", "mit", "isc", "ufl-1.0"}
SCRIPT_WORDS = {  # words people use for a script or language, to the subset names Fontsource uses
    "hindi": "devanagari",
    "devanagari": "devanagari",
    "marathi": "devanagari",
    "bengali": "bengali",
    "bangla": "bengali",
    "tamil": "tamil",
    "telugu": "telugu",
    "gujarati": "gujarati",
    "kannada": "kannada",
    "malayalam": "malayalam",
    "arabic": "arabic",
    "hebrew": "hebrew",
    "thai": "thai",
    "korean": "korean",
    "japanese": "japanese",
    "chinese": "chinese-simplified",
    "cyrillic": "cyrillic",
    "russian": "cyrillic",
    "greek": "greek",
    "vietnamese": "vietnamese",
}
CATEGORIES = ("sans-serif", "serif", "monospace", "display", "handwriting")
FORMATS = ("woff2", "woff", "ttf")
BUNDLED = (  # the families whose web files ship with the skills (D-268): no download needed for a web project
    "archivo", "dm-sans", "fraunces", "inter", "jetbrains-mono", "lora", "manrope", "noto-sans-bengali",
    "noto-sans-devanagari", "nunito", "outfit", "playfair-display", "plus-jakarta-sans", "space-grotesk",
)  # fmt: skip


@dataclass
class Font:
    id: str
    family: str
    category: str
    subsets: list[str]
    weights: list[int]
    styles: list[str]
    variable: bool
    licence: str
    default_subset: str = "latin"
    extra: dict[str, Any] = field(default_factory=dict)

    def describe(self) -> str:
        scripts = ", ".join(s for s in self.subsets if not s.endswith("-ext")) or "latin"
        weights = f"{min(self.weights)}-{max(self.weights)}" if self.weights else "?"
        note = " [ships with DebCraft: web files offline]" if self.id in BUNDLED else ""
        return (
            f"{self.id} - {self.family} ({self.category}; {scripts}; weights {weights}"
            f"{', variable' if self.variable else ''}{', italic' if 'italic' in self.styles else ''}; {self.licence}){note}"
        )


class FontError(Exception):
    """The catalogue or a font could not be reached or read; the message says why."""


def cache_file() -> Path:
    return forge_home() / "library" / "fonts" / "catalogue.json"


def make_client() -> httpx.AsyncClient:
    """The HTTP client; tests replace this with one on a mock transport (the network, not a model)."""
    from forge.net import use_system_certificates

    use_system_certificates()
    return httpx.AsyncClient(timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


def _to_font(row: dict[str, Any]) -> Font | None:
    licence = str(row.get("license", ""))
    if licence.lower() not in ALLOWED_LICENCES or row.get("type") == "icons":
        return None
    return Font(
        id=row["id"],
        family=row.get("family", row["id"]),
        category=row.get("category", ""),
        subsets=list(row.get("subsets", [])),
        weights=[int(w) for w in row.get("weights", [])],
        styles=list(row.get("styles", ["normal"])),
        variable=bool(row.get("variable", False)),
        licence=licence,
        default_subset=row.get("defSubset", "latin"),
    )


def _read_cache(max_age_days: float | None) -> list[dict[str, Any]] | None:
    try:
        stored = json.loads(cache_file().read_text(encoding="utf-8"))
        age_days = (time.time() - float(stored["fetched"])) / 86400
        if max_age_days is not None and age_days > max_age_days:
            return None
        return list(stored["fonts"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


async def load_catalogue(client: httpx.AsyncClient | None = None) -> tuple[list[Font], str]:
    """(fonts, where they came from: 'online', 'cache' or 'offline list'). Never raises: a failed download falls back."""
    fresh = _read_cache(CACHE_DAYS)
    if fresh is not None:
        return [f for f in map(_to_font, fresh) if f], "cache"
    problem = ""
    try:
        if client is not None:  # the caller's open client is used as it is
            response = await client.get(API)
        else:
            async with make_client() as http:
                response = await http.get(API)
        if response.status_code == 200 and isinstance(response.json(), list):
            rows = response.json()
            cache_file().parent.mkdir(parents=True, exist_ok=True)
            cache_file().write_text(json.dumps({"fetched": time.time(), "fonts": rows}), encoding="utf-8")
            return [f for f in map(_to_font, rows) if f], "online"
        problem = f"HTTP {response.status_code}"
    except (httpx.HTTPError, ValueError, OSError) as error:
        problem = type(error).__name__
    stale = _read_cache(None)
    if stale is not None:
        return [
            f for f in map(_to_font, stale) if f
        ], f"cache (older than {CACHE_DAYS} days; the catalogue could not be refreshed: {problem})"
    return (
        _offline_list(),
        f"offline list of {len(BUNDLED)} families (the catalogue could not be reached: {problem})",
    )


def _offline_list() -> list[Font]:
    return [
        Font(
            id=name,
            family=name.replace("-", " ").title(),
            category="sans-serif",
            subsets=["latin"]
            + (["bengali"] if "bengali" in name else ["devanagari"] if "devanagari" in name else []),
            weights=[400, 700],
            styles=["normal"],
            variable=True,
            licence="OFL-1.1",
        )
        for name in BUNDLED
    ]


def search(
    fonts: list[Font], query: str, category: str = "", script: str = "", limit: int = 10
) -> list[Font]:
    words = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if w]
    wanted_script = SCRIPT_WORDS.get(script.lower(), script.lower()) if script else ""
    for word in words:
        wanted_script = wanted_script or SCRIPT_WORDS.get(word, "")
    scored: list[tuple[int, str, Font]] = []
    for font in fonts:
        if category and font.category != category:
            continue
        if wanted_script and not any(s == wanted_script or s.startswith(wanted_script) for s in font.subsets):
            continue
        name = re.sub(r"[^a-z0-9]+", "", font.family.lower())
        joined = "".join(words)
        score = 0
        if joined and joined == name:
            score += 100
        elif joined and joined in name:
            score += 40
        score += sum(8 for w in words if w in font.family.lower().split())
        score += sum(2 for w in words if w == font.category or w in font.category)
        if not words:
            score = 1
        if score or wanted_script:
            score += 3 * (font.id in BUNDLED) + (1 if font.variable else 0)
            scored.append((score, font.family, font))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [font for _, _, font in scored[:limit]]


async def metadata(font_id: str, client: httpx.AsyncClient) -> dict[str, Any]:
    """The detailed record of one family: the download address of every weight, style and script."""
    response = await client.get(f"{API}/{font_id}")
    if response.status_code == 404:
        raise FontError(f"no font '{font_id}' in the catalogue: search with find_font")
    if response.status_code >= 400:
        raise FontError(f"the font catalogue answered {response.status_code}")
    try:
        data = response.json()
    except ValueError as error:
        raise FontError(
            "the font catalogue did not answer with data (a proxy or login page in between?)"
        ) from error
    if str(data.get("license", "")).lower() not in ALLOWED_LICENCES:
        raise FontError(
            f"{data.get('family', font_id)} is licensed {data.get('license', 'unknown')}: not offered"
        )
    return dict(data)


def variant_urls(
    meta: dict[str, Any], weights: list[int], scripts: list[str], italic: bool, fmt: str
) -> list[tuple[str, int, str, str]]:
    """(script, weight, style, url) for what was asked for and exists."""
    style = "italic" if italic else "normal"
    found = []
    for weight in weights:
        for script in scripts:
            entry = (((meta.get("variants") or {}).get(str(weight)) or {}).get(style) or {}).get(script)
            url = ((entry or {}).get("url") or {}).get(fmt)
            if url:
                found.append((script, weight, style, url))
    return found


def font_face_css(family: str, files: list[tuple[str, int, str, str]], folder: str) -> str:
    """@font-face rules for downloaded woff2 files: (script, weight, style, file name)."""
    rules = []
    for _, weight, style, name in files:
        rules.append(
            f"@font-face {{\n  font-family: '{family}';\n  font-style: {style};\n  font-weight: {weight};\n  font-display: swap;\n"
            f"  src: url('{folder}/{name}') format('woff2');\n}}\n"
        )
    return "\n".join(rules)

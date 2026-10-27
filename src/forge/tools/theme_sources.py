"""Where theme ideas come from, and what is read from them (TH1..TH5, D-492).

A theme is studied the way a person looks at it: its public listing, its public preview, its public repository. What is kept is facts (colours, font names, sizes,
section order, how many columns and pictures a section has) in a note of our own words. Nothing a theme wrote is kept as text, and the page that follows is written
from our design system, so this module also keeps a fingerprint of the studied files (hashes of runs of tokens, never the text) that `overlap` uses to prove that
the page shares no code with them."""

from __future__ import annotations

import json
import re
import zlib
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from forge.tools.image_sources import SourceError
from forge.tools.web_guard import WebPolicy, check_resolving

USER_AGENT = "DebCraft/1.0 (https://github.com/debangshukolkata/forge; theme study) httpx"
TIMEOUT_S = 30.0
WPORG_API = "https://api.wordpress.org/themes/info/1.2/"
WPCOM_API = "https://public-api.wordpress.com/rest/v1.2/themes"
GITHUB_API = "https://api.github.com"
GITHUB_RAW = "https://raw.githubusercontent.com"
WPORG_DOWNLOAD = "https://downloads.wordpress.org/theme/"
MAX_FILE_BYTES = 400_000
MAX_STUDY_FILES = 60
WINDOW = 16  # tokens per fingerprint window: boilerplate such as a reset is shorter than this
RUN_FLAG = 6  # consecutive shared windows (a run of about 21 tokens) that make a file too close
SHARE_FLAG = 0.05  # or this share of a file's windows
CHECKED_SUFFIXES = (".html", ".css", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte")


@dataclass
class Theme:
    source: str  # wordpress.org, wordpress.com or github
    name: str
    slug: str
    author: str = ""
    preview_url: str = ""
    screenshot_url: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    rating: float = 0.0
    repo: str = ""  # owner/name when the theme is a repository

    def line(self) -> str:
        bits = [f"{self.name} ({self.slug}, {self.source})"]
        if self.author:
            bits.append(f"by {self.author}")
        if self.tags:
            bits.append("tags: " + ", ".join(self.tags[:6]))
        if self.preview_url:
            bits.append(f"preview {self.preview_url}")
        return "; ".join(bits)


def make_client() -> httpx.AsyncClient:
    """The HTTP client; tests replace this with one on a mock transport (the network, not a model)."""
    from forge.net import use_system_certificates

    use_system_certificates()
    return httpx.AsyncClient(timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}, follow_redirects=False)


def _absolute(url: str) -> str:
    return ("https:" + url) if url.startswith("//") else url


def parse_wporg(data: dict[str, Any]) -> list[Theme]:
    themes: list[Theme] = []
    for row in data.get("themes", []) or []:
        if not isinstance(row, dict) or not row.get("slug"):
            continue
        author = row.get("author")
        tags = row.get("tags")
        themes.append(
            Theme(
                source="wordpress.org",
                name=str(row.get("name", row["slug"])),
                slug=str(row["slug"]),
                author=str(author.get("display_name", "") if isinstance(author, dict) else author or ""),
                preview_url=_absolute(str(row.get("preview_url", ""))),
                screenshot_url=_absolute(str(row.get("screenshot_url", ""))),
                description=re.sub(r"<[^>]+>", "", str(row.get("description", "")))[:300],
                tags=[str(t) for t in (tags.values() if isinstance(tags, dict) else tags or [])],
                rating=float(row.get("rating", 0) or 0) / 20,
            )
        )
    return themes


def parse_wpcom(data: dict[str, Any]) -> list[Theme]:
    themes: list[Theme] = []
    for row in data.get("themes", []) or []:
        if not isinstance(row, dict) or not (row.get("id") or row.get("slug")):
            continue
        raw_taxonomies = row.get("taxonomies")
        taxonomies: dict[str, Any] = raw_taxonomies if isinstance(raw_taxonomies, dict) else {}
        tags = [
            str(item.get("name", item.get("slug", "")))
            for items in taxonomies.values()
            if isinstance(items, list)
            for item in items
            if isinstance(item, dict)
        ]
        themes.append(
            Theme(
                source="wordpress.com",
                name=str(row.get("name", row.get("id"))),
                slug=str(row.get("id") or row.get("slug")),
                author=str(row.get("author", "")),
                preview_url=_absolute(str(row.get("demo_uri", ""))),
                screenshot_url=_absolute(str(row.get("screenshot", ""))),
                description=re.sub(r"<[^>]+>", "", str(row.get("description", "")))[:300],
                tags=[t for t in tags if t],
            )
        )
    return themes


def parse_github(data: dict[str, Any]) -> list[Theme]:
    themes: list[Theme] = []
    for row in data.get("items", []) or []:
        if not isinstance(row, dict) or not row.get("full_name"):
            continue
        owner = row.get("owner")
        themes.append(
            Theme(
                source="github",
                name=str(row.get("name", "")),
                slug=str(row.get("name", "")).lower(),
                author=str(owner.get("login", "") if isinstance(owner, dict) else ""),
                preview_url=str(row.get("homepage") or ""),
                description=str(row.get("description") or "")[:300],
                tags=[str(t) for t in row.get("topics", []) or []],
                repo=str(row["full_name"]),
            )
        )
    return themes


async def get_json(client: httpx.AsyncClient, url: str, policy: WebPolicy) -> Any:
    reason = await check_resolving(url, policy)
    if reason:
        raise SourceError(f"Not fetched: {reason}.")
    response = await client.get(url)
    if response.status_code >= 400:
        raise SourceError(f"{urlparse(url).hostname} answered {response.status_code}")
    try:
        return response.json()
    except ValueError as error:
        raise SourceError(f"{urlparse(url).hostname} did not answer with data") from error


async def get_bytes(
    client: httpx.AsyncClient, url: str, policy: WebPolicy, limit: int = MAX_FILE_BYTES
) -> bytes:
    """The bytes of one public file; redirects are followed by hand so each hop meets the address policy, and the size is capped."""
    current = url
    for _ in range(5):
        reason = await check_resolving(current, policy)
        if reason:
            raise SourceError(f"Not fetched: {reason}.")
        response = await client.get(current)
        if response.is_redirect:
            current = str(response.url.join(response.headers.get("location", "")))
            continue
        if response.status_code >= 400:
            raise SourceError(f"{urlparse(current).hostname} answered {response.status_code}")
        if len(response.content) > limit:
            raise SourceError(f"the file is larger than {limit // 1000} KB")
        return response.content
    raise SourceError("too many redirects")


async def search_themes(
    client: httpx.AsyncClient, query: str, policy: WebPolicy, number: int = 8
) -> tuple[list[Theme], list[str]]:
    """The public theme lists of WordPress.org and WordPress.com, and GitHub repositories; one source being down is a note, not a failure."""
    found: list[Theme] = []
    notes: list[str] = []
    sources = (
        (
            "wordpress.org",
            f"{WPORG_API}?action=query_themes&request[search]={quote(query)}&request[per_page]={number}"
            "&request[fields][screenshot_url]=1&request[fields][preview_url]=1&request[fields][tags]=1"
            "&request[fields][rating]=1&request[fields][description]=1",
            parse_wporg,
        ),
        ("wordpress.com", f"{WPCOM_API}?search={quote(query)}&number={number}", parse_wpcom),
        (
            "github",
            f"{GITHUB_API}/search/repositories?q={quote(query + ' theme')}&per_page={min(number, 5)}&sort=stars",
            parse_github,
        ),
    )
    for name, url, parse in sources:
        try:
            found += parse(await get_json(client, url, policy))[:number]
        except (SourceError, httpx.HTTPError) as error:
            notes.append(f"{name} could not be read ({str(error)[:100]})")
    return found, notes


async def wpcom_theme(client: httpx.AsyncClient, slug: str, policy: WebPolicy) -> dict[str, Any] | None:
    """The WordPress.com list entry of one theme, or None. Paid and marketplace themes are listed there but have no public files."""
    data = await get_json(client, f"{WPCOM_API}?search={quote(slug)}&number=10", policy)
    for row in data.get("themes", []) if isinstance(data, dict) else []:
        if isinstance(row, dict) and slug in (str(row.get("id", "")), str(row.get("stylesheet", ""))):
            return row
    return None


def theme_slug(text: str) -> str:
    """The theme name from a WordPress.org or WordPress.com theme address, or the text itself when it is a plain name."""
    cleaned = text.strip()
    if "://" in cleaned or cleaned.startswith(("wordpress.org/", "wordpress.com/")):
        parsed = urlparse(cleaned if "://" in cleaned else "https://" + cleaned)
        parts = [p for p in parsed.path.split("/") if p]
        for marker in ("theme", "themes"):
            if marker in parts and parts.index(marker) + 1 < len(parts):
                return parts[parts.index(marker) + 1]
    return cleaned


# --- reading a theme -----------------------------------------------------------------------------------------------------


def github_repo(text: str) -> str:
    """`owner/name` from a repository address or from `owner/name`; empty when it is neither."""
    cleaned = text.strip()
    parsed = urlparse(cleaned if "://" in cleaned else "https://github.com/" + cleaned.lstrip("/"))
    parts = [p for p in parsed.path.split("/") if p]
    if "." in (
        parts[0] if parts else "."
    ):  # a web address without its scheme, not an owner (GitHub owners have no dots)
        return ""
    if (parsed.hostname or "") in ("github.com", "www.github.com") and len(parts) >= 2:
        return f"{parts[0]}/{parts[1].removesuffix('.git')}"
    return ""


STUDY_FOLDERS = ("patterns/", "templates/", "parts/", "styles/")


def wanted_paths(tree: list[str]) -> list[str]:
    """Which files of a repository are read: the design files first, then the patterns, templates and parts that show section order."""
    names = [p for p in tree if p.rsplit("/", 1)[-1] in ("theme.json", "style.css") and p.count("/") <= 1]
    chosen = list(names)
    for folder in STUDY_FOLDERS:
        chosen += sorted(p for p in tree if p.startswith(folder) and p.endswith((".php", ".html", ".json")))[
            :20
        ]
    return chosen[:MAX_STUDY_FILES]


@dataclass
class Study:
    slug: str
    licence: str = ""
    licence_uri: str = ""
    theme_name: str = ""
    palette: dict[str, str] = field(default_factory=dict)  # slug -> hex
    fonts: list[str] = field(default_factory=list)
    font_sizes: dict[str, str] = field(default_factory=dict)
    layout: dict[str, str] = field(default_factory=dict)
    shadows: list[str] = field(default_factory=list)
    sections: list[tuple[str, str]] = field(default_factory=list)  # (file, what it holds)
    files_read: list[str] = field(default_factory=list)
    fingerprint: list[int] = field(default_factory=list)


def _header(css: str, key: str) -> str:
    match = re.search(rf"^\s*\*?\s*{key}\s*:\s*(.+)$", css[:4000], re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else ""


def _block_counts(markup: str) -> str:
    """Section structure from WordPress block comments, as counts only: `columns 1 (3 columns), image 3, heading 1`."""
    counts: dict[str, int] = {}
    for name in re.findall(r"<!--\s*wp:([\w/-]+)", markup):
        counts[name] = counts.get(name, 0) + 1
    if not counts:
        return ""
    parts = []
    for name in (
        "cover",
        "heading",
        "paragraph",
        "image",
        "gallery",
        "buttons",
        "columns",
        "query",
        "navigation",
        "group",
    ):
        if name in counts:
            extra = f" ({counts['column']} columns)" if name == "columns" and counts.get("column") else ""
            parts.append(f"{name} {counts[name]}{extra}")
    return ", ".join(parts)


def _first_family(value: str) -> str:
    match = re.match(r"""\s*['"]?([^,'"]+)""", value)
    return match.group(1).strip() if match else ""


def study_files(slug: str, files: dict[str, str]) -> Study:
    """Facts from a theme's files: licence, palette, fonts, sizes, widths, shadows and the structure of each pattern and template. No text of the theme is kept."""
    study = Study(slug=slug, files_read=sorted(files))
    css = next((t for p, t in files.items() if p.rsplit("/", 1)[-1] == "style.css" and p.count("/") <= 1), "")
    study.licence = _header(css, "License")
    study.licence_uri = _header(css, "License URI")
    study.theme_name = _header(css, "Theme Name")
    config = next(
        (t for p, t in files.items() if p.rsplit("/", 1)[-1] == "theme.json" and p.count("/") <= 1), ""
    )
    try:
        data = json.loads(config) if config else {}
    except ValueError:
        data = {}
    settings = data.get("settings", {}) if isinstance(data, dict) else {}
    settings = settings if isinstance(settings, dict) else {}
    color = settings.get("color", {}) if isinstance(settings.get("color"), dict) else {}
    palette = color.get("palette", [])
    for item in palette if isinstance(palette, list) else []:
        if isinstance(item, dict) and re.match(r"^#[0-9a-fA-F]{6}$", str(item.get("color", ""))):
            study.palette[str(item.get("slug", item.get("name", "")))] = str(item["color"]).upper()
    typography = settings.get("typography", {}) if isinstance(settings.get("typography"), dict) else {}
    for family in typography.get("fontFamilies", []) or []:
        if isinstance(family, dict):
            name = _first_family(str(family.get("fontFamily", "")))
            if name and name not in study.fonts and not name.startswith("var("):
                study.fonts.append(name)
    for size in typography.get("fontSizes", []) or []:
        if isinstance(size, dict) and size.get("slug") and size.get("size"):
            study.font_sizes[str(size["slug"])] = str(size["size"])[:40]
    layout = settings.get("layout", {}) if isinstance(settings.get("layout"), dict) else {}
    study.layout = {k: str(v) for k, v in layout.items() if k in ("contentSize", "wideSize")}
    shadow = settings.get("shadow", {}) if isinstance(settings.get("shadow"), dict) else {}
    for preset in shadow.get("presets", []) or []:
        if isinstance(preset, dict) and preset.get("shadow"):
            study.shadows.append(f"{preset.get('slug', '')} = {str(preset['shadow'])[:60]}")
    for path, text in sorted(files.items()):
        if path.startswith(STUDY_FOLDERS[:3]):
            structure = _block_counts(text)
            if structure:
                study.sections.append((path, structure))
    study.fingerprint = fingerprint(
        "\n".join(t for p, t in files.items() if p.endswith((".css", ".php", ".html", ".js")))
    )
    return study


# --- fingerprint and overlap ---------------------------------------------------------------------------------------------


def tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_#.%-]+|[^\sA-Za-z0-9_]", text.lower())


def _windows(text: str) -> list[int]:
    items = tokens(text)
    return [
        zlib.crc32(" ".join(items[i : i + WINDOW]).encode()) for i in range(max(len(items) - WINDOW + 1, 0))
    ]


def fingerprint(text: str) -> list[int]:
    """Hashes of every run of 16 tokens: enough to find copied code later, nothing that can be turned back into the text."""
    return sorted(set(_windows(text)))


@dataclass
class Overlap:
    path: str
    shared: int
    total: int
    longest_run: int

    @property
    def too_close(self) -> bool:
        return self.longest_run >= RUN_FLAG or (self.total > 0 and self.shared / self.total >= SHARE_FLAG)


def overlap(known: set[int], path: str, text: str) -> Overlap:
    """How much of a file is made of runs of tokens that the studied theme also has."""
    hashes = _windows(text)
    shared = longest = run = 0
    for value in hashes:
        if value in known:
            shared += 1
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return Overlap(path, shared, len(hashes), longest)

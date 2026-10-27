"""find_image and fetch_image (TODO D5, D-328): free, licensed icons, cliparts and photos from open sources.

`find_image` searches the sources that can be reached (see image_sources.py) at the same time and lists candidates with their licence and
the credit line they need; a source that cannot be reached is named with the reason, so a blocked company network shows up at once.
`fetch_image` downloads one candidate into the project (public addresses only, size-capped, image content only, SVG without scripts),
records it in NOTICES.md and returns the credit line to put near it. Nothing is hot-linked."""

from __future__ import annotations

import asyncio
import contextlib
import re
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
from pydantic import Field

from forge.net import connection_hint, root_cause
from forge.slides.icons import IconError, icon_svg, search_icons
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools import image_sources as sources
from forge.tools import picture_library
from forge.tools.brand_pictures import project_candidates
from forge.tools.illustration_set import FOLDER as DOODLE_FOLDER
from forge.tools.illustration_set import HEX, doodle_candidates, recoloured
from forge.tools.image_sources import PROVIDERS, Candidate, SourceError
from forge.tools.sample_sources import OPTIONAL_KEY_NAMES, SAMPLE_SOURCES
from forge.tools.web_guard import WebPolicy, check_resolving

NOTICES = "NOTICES.md"
SITE = "the site's address"  # what a connection hint tells the user to check
MAX_BYTES = 25 * 1024 * 1024
SEARCH_TIMEOUT_S = 20.0
EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
}
UNSAFE_SVG = re.compile(
    r"<\s*script|<\s*foreignObject|\son\w+\s*=|javascript:|<!\s*ENTITY|(?:xlink:)?href\s*=\s*[\"']\s*https?:",
    re.I,
)
KIND_SOURCES = {
    "icon": ("iconify",),
    "photo": ("openverse", "wikimedia", "nasa", "pexels", "unsplash", "pixabay", *SAMPLE_SOURCES),
    "illustration": ("iconify", "openverse", "wikimedia", "pixabay", *SAMPLE_SOURCES),
    "any": tuple(PROVIDERS),
}


def available_sources(secrets: Any, kind: str, wanted: list[str]) -> tuple[list[str], list[str]]:
    """(sources to ask, sources skipped because their key is not in the .env file)."""
    chosen, skipped = [], []
    for name in wanted or KIND_SOURCES[kind]:
        if name not in PROVIDERS:
            continue
        key_name = sources.KEY_NAMES.get(name)
        if key_name and not (secrets.get(key_name) if secrets is not None else None):
            skipped.append(f"{name} (add {key_name} to the .env file to use it)")
        else:
            chosen.append(name)
    return chosen, skipped


async def _search_one(
    client: httpx.AsyncClient, name: str, query: str, limit: int, secrets: Any
) -> tuple[str, list[Candidate] | str]:
    key_name = sources.KEY_NAMES.get(name) or OPTIONAL_KEY_NAMES.get(name)
    key = secrets.get(key_name) if secrets is not None and key_name else ""
    try:
        found = await asyncio.wait_for(PROVIDERS[name](client, query, limit, key or ""), SEARCH_TIMEOUT_S)
        return name, found
    except SourceError as error:
        return name, str(error)
    except TimeoutError:
        return (
            name,
            f"{name} did not answer in {SEARCH_TIMEOUT_S:.0f} s: a proxy is probably required (HTTPS_PROXY) or the site is blocked",
        )
    except httpx.HTTPError as error:
        detail = root_cause(error)
        return (
            name,
            f"{name} could not be reached ({detail[:120]}): {connection_hint(detail, SITE)}",
        )


BUNDLED_LICENCES = {"lucide": ("ISC", "Lucide Contributors"), "material": ("Apache-2.0", "Google")}


def local_candidates(query: str, kind: str, limit: int) -> list[Candidate]:
    """Pictures that need no network: the bundled icons (Lucide, Material) and what earlier fetches left in the library."""
    found: list[Candidate] = []
    if kind in ("icon", "illustration", "any"):
        for name in search_icons(query, limit):
            library, _, bare = name.partition(":")
            licence, author = BUNDLED_LICENCES[library]
            found.append(
                Candidate(
                    id=f"bundled:{name}",
                    source="bundled",
                    kind="icon",
                    title=f"{bare} ({library})",
                    licence=licence,
                    author=author,
                    attribution=f"{library.capitalize()} icons by {author} ({licence})",
                )
            )
    for record in picture_library.search(query, limit):
        found.append(
            Candidate(
                id=f"library:{record['id']}",
                source="library",
                kind=record.get("kind", "photo"),
                title=record["title"],
                licence=record["licence"],
                author=record.get("author", ""),
                page_url=record.get("page", ""),
                attribution=record.get("credit", ""),
                extra={"file": record["file"]},
            )
        )
    return found


def _interleave(groups: list[list[Candidate]], limit: int) -> list[Candidate]:
    merged: list[Candidate] = []
    for position in range(max((len(g) for g in groups), default=0)):
        for group in groups:
            if position < len(group):
                merged.append(group[position])
    return merged[:limit]


class FindImage(Tool):
    name = "find_image"
    sends_outside = True
    read_only = True
    description = (
        "Search pictures: the user's own files first (the project's brand-assets, assets/brand or brand folder; ids project:...), then free, licensed icons and vector clip art (Iconify: Lucide, Tabler, Material and others), photos and drawings "
        "(Openverse, Wikimedia Commons, NASA, and Pexels, Unsplash or Pixabay when their key is in the .env file). Only licences that "
        "allow commercial use and changes are listed (CC0, public domain, CC BY, MIT, ISC, Apache-2.0 and the photo sites' licences), "
        "each with the credit line it needs. Pictures that need no network come first: the bundled Lucide and Material icons (ids "
        "bundled:...) and the library of earlier downloads (ids library:...), so use those when they fit. "
        "Search in English, with the subject (and a style word for clip art). Then call "
        "fetch_image with the id of the one you want. A source that cannot be reached is reported with the reason; when none can, say so "
        "and use find_asset, draw an SVG, or generate_image."
    )

    class Args(ToolArgs):
        query: str = Field(min_length=2, max_length=200, description="What the picture shows, in English")
        kind: Literal["any", "icon", "photo", "illustration"] = "any"
        limit: int = Field(default=8, ge=1, le=15)
        sources: list[str] = Field(
            default_factory=list, description="Only these sources (default: all that fit the kind)"
        )

    def summary(self, args: FindImage.Args) -> str:
        return f"find image: {args.query}"

    async def run(self, args: FindImage.Args, context: ToolContext) -> ToolResult:
        if any(re.search(re.escape(t), args.query, re.IGNORECASE) for t in context.sensitive_terms):
            return ToolResult(ok=False, content="Not searched: the query contains a host-identifying term.")
        context.last_image_query = args.query
        names, skipped = available_sources(context.secrets, args.kind, args.sources)
        own = [] if args.sources else project_candidates(context.workspace.repo_dir, args.query, 6)
        doodles = (
            doodle_candidates(args.query, 3)
            if not args.sources and args.kind in ("illustration", "any")
            else []
        )
        local = [] if args.sources else [*own, *local_candidates(args.query, args.kind, 4), *doodles]
        if not names and not local:
            return ToolResult(
                ok=False, content="No source fits: " + "; ".join(skipped or ["unknown source names"])
            )
        async with sources.make_client() as client:
            results = await asyncio.gather(
                *(_search_one(client, n, args.query, args.limit, context.secrets) for n in names)
            )
        groups = [r for n, r in results if isinstance(r, list) and n not in SAMPLE_SOURCES]
        problems = [r for _, r in results if isinstance(r, str)]
        sample_groups = [r for n, r in results if isinstance(r, list) and n in SAMPLE_SOURCES]
        # sample pictures (D-436) come after every licensed one, never mixed into them
        chosen = [*local, *_interleave(groups, args.limit), *_interleave(sample_groups, 4)]
        for candidate in chosen:
            context.image_candidates[candidate.id] = candidate
        lines = [f"{i}. {c.describe()}" for i, c in enumerate(chosen, start=1)]
        out = (
            [f"{len(chosen)} licensed picture(s) for '{args.query}':", *lines]
            if chosen
            else [f"Nothing found for '{args.query}' in the sources that answered."]
        )
        if problems:
            out += ["", "Not reached:", *[f"- {p}" for p in problems]]
        if skipped:
            out += ["", "Not used: " + "; ".join(skipped)]
        if chosen:
            out += [
                "",
                "Use fetch_image with an id and a path in the project. Look at the picture afterwards (view_image) and keep the credit line.",
            ]
        return ToolResult(ok=True, content="\n".join(out))


SUBJECT_CHECK_PROMPT = (
    "You check a stock picture against what was asked for. Reply with exactly one line: `YES: <six words on what it shows>` or `NO: <ten words on why not>`. "
    "Answer NO when it shows a different subject than requested, when any lettering in it is garbled or unreadable, when it has a watermark, when a hand, a face or an object is visibly malformed, "
    "or when it is a poster, a packaging mock-up or a drawing although a photograph of the subject was asked for."
)


async def subject_problem(context: ToolContext, data: bytes, subject: str) -> str | None:
    """None when the picture fits the request (or cannot be checked here); otherwise why it does not. Pictures from the network, above all the AI-image samples, are
    often not what their title says (a search for bread returned a lavender-field package with garbled lettering, found in the Fernhill live check, 2026-10-15)."""
    if context.router is None or not subject:
        return None
    try:
        import io

        from PIL import Image

        from forge.llm.base import ChatRequest, Message
        from forge.vision import images

        url, _ = images.for_model(Image.open(io.BytesIO(data)))
        request = ChatRequest(
            messages=[
                Message.system(SUBJECT_CHECK_PROMPT),
                Message(role="user", content=f"Requested: a picture of {subject}", images=[url]),
            ]
        )
        response = await context.ask_model("vision", request, "checking the picture")
    except Exception:  # a picture that cannot be checked is not refused for that
        return None
    answer = str(response.text).strip()
    return answer[3:].strip(" :") if answer.upper().startswith("NO") else None


class FetchImage(Tool):
    name = "fetch_image"
    sends_outside = True
    read_only = False
    description = (
        "Download a picture found with find_image into the project and record its source and licence in NOTICES.md. Give the id and a "
        "path (the extension is corrected to match the file). Returns the credit line to put near the picture when its licence needs one "
        "(and suggested alt text). SVG icons can be recoloured by editing the file's colour values."
    )

    class Args(ToolArgs):
        id: str = Field(description="An id from find_image, e.g. iconify:lucide:house or openverse:...")
        path: str = Field(description="Where to save it in the project, e.g. assets/house.svg")
        color: str = Field(
            default="#111827", description="For a bundled icon: its colour (hex or currentColor)"
        )
        size: int = Field(
            default=24, ge=8, le=1024, description="For a bundled icon: width and height in pixels"
        )
        accent: str = Field(
            default="",
            description="For an Open Doodles illustration (doodle:...): the project's accent colour, #RRGGBB, to replace its pink",
        )
        ink: str = Field(
            default="",
            description="For an Open Doodles illustration: replace its black outlines with this #RRGGBB",
        )

    def summary(self, args: FetchImage.Args) -> str:
        return f"fetch image {args.id} to {args.path}"

    async def run(self, args: FetchImage.Args, context: ToolContext) -> ToolResult:
        candidate = context.image_candidates.get(args.id)
        if candidate is None:
            return ToolResult(
                ok=False,
                content=f"{args.id} was not found in this session's results: search with find_image first.",
            )
        if candidate.source in ("bundled", "library", "project", "open-doodles"):
            return _save_local(context, candidate, args)
        policy = context.web_policy or WebPolicy()
        try:
            async with sources.make_client() as client:
                data, content_type, note = await download_candidate(client, candidate, policy)
                if candidate.extra.get("track"):  # Unsplash asks for a ping when a photo is used
                    await _ping(client, candidate)
        except SourceError as error:
            return ToolResult(ok=False, content=str(error))
        except httpx.HTTPError as error:
            detail = root_cause(error)
            return ToolResult(
                ok=False,
                content=f"The file could not be downloaded ({detail[:120]}): {connection_hint(detail, SITE)}",
            )
        extension = EXTENSIONS.get(content_type)
        if extension is None:
            return ToolResult(
                ok=False,
                content=f"The address did not give a picture (it gave {content_type or 'something else'}).",
            )
        if extension == ".svg" and UNSAFE_SVG.search(data.decode("utf-8", "replace")):
            return ToolResult(
                ok=False,
                content="The SVG holds a script or an outside link, so it was not saved. Pick another picture.",
            )
        if candidate.kind in ("photo", "illustration"):
            problem = await subject_problem(context, data, context.last_image_query)
            if problem:
                return ToolResult(
                    ok=False,
                    content=f"Not saved: the picture does not match '{context.last_image_query}' ({problem}). Take another candidate, or search again with other words.",
                )
        path = re.sub(r"\.[A-Za-z0-9]{2,5}$", "", args.path) + extension
        context.workspace.write_bytes(path, data, f"picture from {candidate.source}: {candidate.title}")
        _record_notice(context, path, candidate)
        with contextlib.suppress(
            OSError
        ):  # the library is a convenience; a full disk must not fail the download
            picture_library.remember(_library_record(candidate), data, extension, context.last_image_query)
        credit = candidate.attribution
        lines = [
            f"Saved {path} ({len(data) // 1024} KB; {candidate.licence}; source {candidate.page_url or candidate.source})."
        ]
        if note:
            lines.append(note)
        lines.append(f"Credit line to show with it: {credit}" if credit else "No credit line is required.")
        lines.append(f"Suggested alt text: {candidate.title[:120]}. Record in NOTICES.md: done.")
        if candidate.extra.get("sample"):
            lines.append(
                "This is a SAMPLE picture (AI-generated, terms: "
                + candidate.licence
                + "): it makes the page feel real until the user supplies their own. "
                "Say so in your final message, list every sample picture by file name, and say that their own pictures go in brand-assets/ to replace them."
            )
        return ToolResult(ok=True, content="\n".join(lines))


async def download_candidate(
    client: httpx.AsyncClient, candidate: Candidate, policy: WebPolicy
) -> tuple[bytes, str, str]:
    """(bytes, content type, a note for the user). When the picture's own site refuses (hot-link protection, a company proxy block)
    and the source keeps its own smaller copy (Openverse does), that copy is used and the note says so."""
    url = await _download_url(client, candidate)
    reason = await check_resolving(url, policy)
    if reason:
        raise SourceError(f"Not downloaded: {reason}.")
    try:
        data, content_type = await _download(client, url, policy)
        return data, content_type, ""
    except (SourceError, httpx.HTTPError) as error:
        fallback = candidate.extra.get("fallback")
        if not fallback:
            raise
        data, content_type = await _download(client, fallback, policy)
        why = str(error) if isinstance(error, SourceError) else type(error).__name__
        return (
            data,
            content_type,
            f"The original site refused ({why[:80]}); this is the smaller copy kept by {candidate.source}.",
        )


async def _download_url(client: httpx.AsyncClient, candidate: Candidate) -> str:
    asset_url = candidate.extra.get("asset_url")
    if not asset_url:
        return candidate.download_url
    response = await client.get(asset_url)  # NASA lists every size of an image
    if response.status_code >= 400:
        raise SourceError(f"nasa answered {response.status_code} for the file list")
    hrefs = [item.get("href", "") for item in response.json().get("collection", {}).get("items", [])]
    for marker in ("~large.jpg", "~medium.jpg", "~orig.jpg", ".jpg"):
        found = next((h for h in hrefs if h.lower().endswith(marker)), None)
        if found:
            return str(found).replace("http://", "https://")
    return candidate.download_url


async def _download(
    client: httpx.AsyncClient, url: str, policy: WebPolicy, limit: int = MAX_BYTES
) -> tuple[bytes, str]:
    """The bytes and content type; every redirect hop is checked against the same address policy and the size is capped."""
    current = url
    for _ in range(5):
        async with client.stream("GET", current, follow_redirects=False) as response:
            if response.is_redirect:
                current = str(response.url.join(response.headers.get("location", "")))
                reason = await check_resolving(current, policy)
                if reason:
                    raise SourceError(
                        f"a redirect led to {urlparse(current).hostname}, which is not allowed: {reason}"
                    )
                continue
            if response.status_code >= 400:
                raise SourceError(f"{urlparse(current).hostname} answered {response.status_code}")
            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data += chunk
                if len(data) > limit:
                    raise SourceError(f"the file is larger than {limit // (1024 * 1024)} MB")
            return bytes(data), content_type
    raise SourceError("too many redirects")


async def _ping(client: httpx.AsyncClient, candidate: Candidate) -> None:
    """Unsplash asks for a request to the photo's download address when it is used; a courtesy, so failures are ignored."""
    with contextlib.suppress(httpx.HTTPError):
        await client.get(
            candidate.extra["track"], headers={"Authorization": f"Client-ID {candidate.extra.get('key', '')}"}
        )


def _library_record(candidate: Candidate) -> dict[str, str]:
    return {
        "id": candidate.id,
        "title": candidate.title,
        "source": candidate.source,
        "kind": candidate.kind,
        "licence": candidate.licence,
        "author": candidate.author,
        "credit": candidate.attribution,
        "page": candidate.page_url,
    }


def _save_local(context: ToolContext, candidate: Candidate, args: Any) -> ToolResult:
    """A bundled icon written as an SVG, or a picture from the library copied into the project (no network)."""
    if candidate.source == "bundled":
        try:
            data = icon_svg(candidate.id.removeprefix("bundled:"), args.color, args.size).encode("utf-8")
        except IconError as error:
            return ToolResult(ok=False, content=str(error))
        extension = ".svg"
    elif candidate.source == "open-doodles":
        file = DOODLE_FOLDER / candidate.extra["file"]
        if not file.is_file():
            return ToolResult(
                ok=False, content="The illustration file is missing from the install: search again."
            )
        accent, ink = getattr(args, "accent", ""), getattr(args, "ink", "")
        if (accent and not HEX.match(accent)) or (ink and not HEX.match(ink)):
            return ToolResult(ok=False, content="accent and ink must be colours written as #RRGGBB.")
        data, extension = recoloured(file.read_text(encoding="utf-8"), accent, ink).encode("utf-8"), ".svg"
    elif candidate.source == "project":
        file = context.workspace.path_of(candidate.extra["file"])
        if not file.is_file():
            return ToolResult(ok=False, content="The file is gone from the project: search again.")
        data, extension = file.read_bytes(), file.suffix.lower()
        if extension == ".svg" and UNSAFE_SVG.search(data.decode("utf-8", "replace")):
            return ToolResult(
                ok=False,
                content="The SVG holds a script or an outside link, so it was not used. Ask the user for another file.",
            )
    else:
        file = picture_library.folder() / candidate.extra["file"]
        if not file.is_file():
            return ToolResult(ok=False, content="The library file is gone: search again.")
        data, extension = file.read_bytes(), file.suffix
    path = re.sub(r"\.[A-Za-z0-9]{2,5}$", "", args.path) + extension
    context.workspace.write_bytes(path, data, f"picture from {candidate.source}: {candidate.title}")
    _record_notice(context, path, candidate)
    credit = (
        f"Credit line to show with it: {candidate.attribution}"
        if candidate.attribution
        else "No credit line is required."
    )
    return ToolResult(
        ok=True,
        content=f"Saved {path} ({candidate.licence}; from the {candidate.source}, no network used).\n{credit}",
    )


def _record_notice(context: ToolContext, path: str, candidate: Candidate) -> None:
    try:
        existing, _ = context.workspace.read_text(NOTICES)
    except (OSError, ValueError, KeyError):
        existing = "# Notices\n\nThird-party pictures used in this project.\n"
    line = (
        f"- `{path}`: {candidate.title}"
        + (f" by {candidate.author}" if candidate.author else "")
        + f", {candidate.licence}, from {candidate.source}"
        + (f" ({candidate.page_url})" if candidate.page_url else "")
        + (f". Credit: {candidate.attribution}" if candidate.attribution else "")
        + (". SAMPLE PICTURE: replace before publishing" if candidate.extra.get("sample") else "")
        + "\n"
    )
    if f"`{path}`" not in existing:
        context.workspace.write_text(
            NOTICES, existing.rstrip("\n") + "\n" + line, "picture recorded in NOTICES.md"
        )


def findimage_tools() -> list[Tool]:
    return [FindImage(), FetchImage()]

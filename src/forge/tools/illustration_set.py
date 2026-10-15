"""The bundled open illustration set (TODO DIE6): Open Doodles by Pablo Stanley, CC0, 32 hand-drawn people in two colours.

`find_image` lists them (as `doodle:<name>`) when the query names what a picture shows (reading, coffee, a plant, running, a parcel...), and `fetch_image` copies one
into the project with the accent recoloured to the project's palette. CC0 needs no credit; the source is still recorded in NOTICES.md. They are a style to choose
deliberately (loose, friendly, hand-drawn): a serious or luxury brand should not use them. Files are read from the install folder and never written there."""

from __future__ import annotations

import re
from pathlib import Path

from forge.designsystem.colour import parse, to_hex
from forge.tools.image_sources import Candidate

FOLDER = Path(__file__).resolve().parent.parent / "data" / "illustrations" / "open-doodles"
ACCENT = "#FF5678"
ACCENT_SHADE = "#CF536D"
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
# what each drawing is good for, in the words a brief uses
MEANINGS = {
    "ballet": "dance arts performance studio class",
    "bikini": "summer beach holiday swimwear",
    "chilling": "relax rest lounge calm break",
    "clumsy": "mistake error oops paperwork documents admin",
    "coffee": "coffee cafe break drink morning",
    "dancing": "dance music party event festival",
    "dog-jump": "dog pet animals vet play",
    "float": "freedom dream creative idea",
    "groovy": "music dance fun party",
    "ice-cream": "ice cream dessert food summer sweet",
    "jumping": "jump energy sport fitness joy",
    "laying": "relax phone mobile reading rest",
    "levitate": "yoga wellness calm balance",
    "loving": "love care charity health kindness heart",
    "meditating": "meditation yoga wellness mindfulness calm",
    "moshing": "music concert festival energy",
    "petting": "dog pet animals vet care",
    "plant": "plant garden nature home green nursery",
    "reading": "reading book study learning education library",
    "reading-side": "reading book study learning library home",
    "roller-skating": "skating sport fitness fun wheels",
    "rolling": "play fun children energy",
    "running": "running sport fitness race fast marathon",
    "selfie": "selfie photo phone social camera",
    "sitting": "sitting relax rest seat",
    "sitting-reading": "reading book study learning library chair",
    "sleek": "running fast sport style",
    "sprinting": "sprint running sport fast delivery",
    "strolling": "walk walking stroll city travel",
    "swinging": "swing play children fun playground",
    "unboxing": "unboxing parcel package delivery order shop shopping",
    "zombieing": "halloween funny tired monday",
}


def _words(text: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", text.lower()) if len(w) > 2}


def doodle_candidates(query: str, limit: int) -> list[Candidate]:
    wanted = _words(query)
    scored = sorted(
        ((len(wanted & _words(f"{name} {meaning}")), name) for name, meaning in MEANINGS.items()),
        key=lambda row: (-row[0], row[1]),
    )
    found: list[Candidate] = []
    for score, name in scored:
        if score == 0 or len(found) >= limit or not (FOLDER / f"{name}.svg").is_file():
            continue
        found.append(
            Candidate(
                id=f"doodle:{name}",
                source="open-doodles",
                kind="illustration",
                title=f"{name.replace('-', ' ')} (Open Doodles, hand-drawn person, ink and one accent colour)",
                licence="CC0",
                author="Pablo Stanley",
                page_url="https://www.opendoodles.com/",
                attribution="",
                extra={"file": f"{name}.svg"},
            )
        )
    return found


def _shade(colour: str) -> str:
    parsed = parse(colour)
    if parsed is None:
        return ACCENT_SHADE
    return "#" + to_hex((int(parsed[0] * 0.8), int(parsed[1] * 0.8), int(parsed[2] * 0.8), 1.0))


def recoloured(svg: str, accent: str, ink: str = "") -> str:
    """The drawing with its accent (and its shade, 20 percent darker) replaced; the ink too when one is given."""
    if accent:
        svg = re.sub(re.escape(ACCENT_SHADE), _shade(accent), svg, flags=re.I)
        svg = re.sub(re.escape(ACCENT), accent, svg, flags=re.I)
    if ink:
        svg = re.sub(r"#000000\b", ink, svg, flags=re.I)
    return svg

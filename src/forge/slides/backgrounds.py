"""How dark a slide's background is (TODO P2.23, D-334), read from the file without rendering: a company template has dark and light twins
of its slides (black with waves, white with waves), and a deck should stay on one side. The slide's own background wins, then its
layout's, then the master's. A solid colour, a gradient (the mean of its stops) and a picture (the mean of its pixels) are read;
theme colours are resolved through the master's colour map (a dark master maps `bg1` to the dark colour)."""

from __future__ import annotations

import io
import re
from typing import Any

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
DEFAULT_MAP = {"bg1": "lt1", "tx1": "dk1", "bg2": "lt2", "tx2": "dk2"}
DARK_BELOW = 90.0
LIGHT_ABOVE = 170.0


def _luminance(red: int, green: int, blue: int) -> float:
    return 0.299 * red + 0.587 * green + 0.114 * blue


def _hex(value: str) -> float | None:
    if re.fullmatch(r"[0-9A-Fa-f]{6}", value or ""):
        return _luminance(int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))
    return None


def _theme_colours(master: Any) -> dict[str, str]:
    from lxml import etree  # type: ignore[import-untyped]
    from pptx.opc.constants import RELATIONSHIP_TYPE

    try:
        root = etree.fromstring(master.part.part_related_by(RELATIONSHIP_TYPE.THEME).blob)
    except (KeyError, ValueError, etree.XMLSyntaxError):
        return {}
    out: dict[str, str] = {}
    for slot in (
        "dk1",
        "lt1",
        "dk2",
        "lt2",
        "accent1",
        "accent2",
        "accent3",
        "accent4",
        "accent5",
        "accent6",
    ):
        node = root.find(f".//a:clrScheme/a:{slot}/*", NS)
        if node is not None:
            out[slot] = (node.get("val") if node.tag.endswith("srgbClr") else node.get("lastClr")) or ""
    return out


def _colour(node: Any, master: Any) -> float | None:
    """Luminance of a colour element (srgbClr, schemeClr, sysClr, prstClr), without the colour transforms (tint, shade) it may carry."""
    tag = node.tag.split("}")[1]
    if tag == "srgbClr":
        return _hex(node.get("val", ""))
    if tag == "sysClr":
        return _hex(node.get("lastClr", ""))
    if tag == "prstClr":
        return {"black": 0.0, "white": 255.0}.get(node.get("val", ""))
    if tag == "schemeClr":
        name = node.get("val", "")
        if name in DEFAULT_MAP:
            cmap = master._element.find("p:clrMap", NS)
            slot = cmap.get(name) if cmap is not None and cmap.get(name) else DEFAULT_MAP[name]
        else:
            slot = name
        return _hex(_theme_colours(master).get(slot, ""))
    return None


def _picture_mean(holder: Any, blip: Any) -> float | None:
    try:
        from PIL import Image, ImageStat

        part = holder.part.related_part(blip.get(f"{{{NS['r']}}}embed"))
        with Image.open(io.BytesIO(part.blob)) as image:
            return float(ImageStat.Stat(image.convert("L").resize((48, 27))).mean[0])
    except (ImportError, KeyError, ValueError, OSError):
        return None


def _fill_luminance(background: Any, holder: Any, master: Any) -> float | None:
    properties = background.find("p:bgPr", NS)
    if properties is None:
        return None  # a reference to the theme's background styles: not read
    solid = properties.find("a:solidFill/*", NS)
    if solid is not None:
        return _colour(solid, master)
    stops = properties.findall("a:gradFill/a:gsLst/a:gs/*", NS)
    values = [v for v in (_colour(stop, master) for stop in stops) if v is not None]
    if values:
        return sum(values) / len(values)
    blip = properties.find("a:blipFill/a:blip", NS)
    if blip is not None:
        return _picture_mean(holder, blip)
    return None


def background_luminance(slide: Any) -> float | None:
    """0 (black) to 255 (white), or None when it cannot be told from the file (then a rendered picture is needed)."""
    layout = slide.slide_layout
    master = layout.slide_master
    for holder in (slide, layout, master):
        background = holder._element.find("p:cSld/p:bg", NS)
        if background is not None:
            value = _fill_luminance(background, holder, master)
            if value is not None:
                return value
    return None


def is_dark(luminance: float | None) -> bool | None:
    """True for a dark slide, False for a light one, None for something in between or unknown."""
    if luminance is None:
        return None
    if luminance < DARK_BELOW:
        return True
    if luminance > LIGHT_ABOVE:
        return False
    return None

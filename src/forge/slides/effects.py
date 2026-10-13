"""Fills, shadows and picture shapes that python-pptx has no call for (TODO P2.2, D-282): linear gradients, fill
transparency, soft or hard shadows, rounded and circular picture frames, and sending shapes to the back. They write the
DrawingML elements in the order the schema requires (fill, outline, effects), so the package validator and PowerPoint accept
the result. python-pptx is imported inside the functions (it is an optional extra)."""

from __future__ import annotations

from typing import Any

EMU_PER_POINT = 12700
SHADOWS = {
    # kind: (blur pt, distance pt, direction in 60000ths of a degree, alpha in 1000ths of a percent)
    "soft": (18, 5, 5400000, 22000),
    "lifted": (30, 12, 5400000, 30000),
    "hard": (0, 6, 2700000, 45000),
}
FILL_TAGS = ("a:noFill", "a:solidFill", "a:gradFill", "a:blipFill", "a:pattFill", "a:grpFill")


def _element(tag: str, **attributes: str) -> Any:
    from pptx.oxml.xmlchemy import OxmlElement

    element = OxmlElement(tag)
    for name, value in attributes.items():
        element.set(name, value)
    return element


def _child(parent: Any, tag: str, **attributes: str) -> Any:
    child = _element(tag, **attributes)
    parent.append(child)
    return child


def _spPr(shape: Any) -> Any:
    return shape._element.spPr


def _first_present(spPr: Any, tags: tuple[str, ...]) -> Any:
    from pptx.oxml.ns import qn

    for tag in tags:
        found = spPr.find(qn(tag))
        if found is not None:
            return found
    return None


def _insert_fill(spPr: Any, fill: Any) -> None:
    """Puts a fill element where the schema wants it: after the geometry, before the outline and effects."""
    from pptx.oxml.ns import qn

    for tag in FILL_TAGS:
        for old in spPr.findall(qn(tag)):
            spPr.remove(old)
    anchor = _first_present(spPr, ("a:ln", "a:effectLst", "a:effectDag", "a:scene3d", "a:sp3d", "a:extLst"))
    if anchor is not None:
        anchor.addprevious(fill)
    else:
        spPr.append(fill)


def _colour(parent: Any, hex_colour: str, opacity: float) -> None:
    colour = _child(parent, "a:srgbClr", val=hex_colour.upper())
    if opacity < 1:
        _child(colour, "a:alpha", val=str(round(max(0.0, opacity) * 100000)))


def set_solid(shape: Any, hex_colour: str, opacity: float = 1.0) -> None:
    """A solid fill with optional transparency (opacity 1 = opaque, 0 = invisible)."""
    fill = _element("a:solidFill")
    _colour(fill, hex_colour, opacity)
    _insert_fill(_spPr(shape), fill)


def set_gradient(shape: Any, first: str, last: str, angle: float = 90.0, opacity: float = 1.0) -> None:
    """A linear gradient from `first` to `last`. The angle is clockwise: 0 runs left to right, 90 runs top to bottom."""
    fill = _element("a:gradFill", rotWithShape="1")
    stops = _child(fill, "a:gsLst")
    for position, colour in ((0, first), (100000, last)):
        _colour(_child(stops, "a:gs", pos=str(position)), colour, opacity)
    _child(fill, "a:lin", ang=str(round((angle % 360) * 60000)), scaled="0")
    _insert_fill(_spPr(shape), fill)


def set_shadow(shape: Any, kind: str) -> None:
    """A drop shadow ("soft", "lifted" or "hard"); "none" removes it."""
    from pptx.oxml.ns import qn

    spPr = _spPr(shape)
    for old in spPr.findall(qn("a:effectLst")):
        spPr.remove(old)
    effects = _element("a:effectLst")
    if kind in SHADOWS:
        blur, distance, direction, alpha = SHADOWS[kind]
        shadow = _child(
            effects,
            "a:outerShdw",
            blurRad=str(blur * EMU_PER_POINT),
            dist=str(distance * EMU_PER_POINT),
            dir=str(direction),
            algn="ctr",
            rotWithShape="0",
        )
        colour = _child(shadow, "a:srgbClr", val="000000")
        _child(colour, "a:alpha", val=str(alpha))
    anchor = _first_present(spPr, ("a:scene3d", "a:sp3d", "a:extLst"))  # effects come before 3-D settings
    if anchor is not None:
        anchor.addprevious(effects)
    else:
        spPr.append(effects)


def set_picture_frame(picture: Any, frame: str) -> None:
    """Crops a picture to a rounded rectangle or a circle (an oval; give it a square box for a circle)."""
    from pptx.oxml.ns import qn

    geometry = picture._element.spPr.find(qn("a:prstGeom"))
    if geometry is None:
        return
    geometry.set("prst", {"rounded": "roundRect", "circle": "ellipse"}.get(frame, "rect"))
    if frame == "rounded":
        for old in geometry.findall(qn("a:avLst")):
            geometry.remove(old)
        _child(_child(geometry, "a:avLst"), "a:gd", name="adj", fmla="val 8000")


def send_to_back(slide: Any, shape: Any) -> None:
    """Moves a shape behind everything else on the slide (right after the shape tree's own properties)."""
    tree = slide.shapes._spTree
    tree.remove(shape._element)
    tree.insert(2, shape._element)

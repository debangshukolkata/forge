"""Test helpers: company-style templates generated from python-pptx's default template (which is 4:3 and plain)."""

from __future__ import annotations

import io
import re

from pptx import Presentation
from pptx.opc.constants import RELATIONSHIP_TYPE as RT

EMU = 914400


def make_template(
    width_in: float = 13.333,
    height_in: float = 7.5,
    accents: tuple[str, ...] = ("0B6E4F", "F2A541", "3C6E9E", "B5446E", "6B5BD2", "5B6675"),
    fonts: tuple[str, str] = ("Georgia", "Arial"),
    dark: bool = False,
    sample_slide: bool = True,
    strip_layouts: tuple[str, ...] = (),
) -> bytes:
    """A template: default layouts stretched to the given size, its own accent colours and fonts, optionally a dark master."""
    prs = Presentation()
    old_w, old_h = prs.slide_width, prs.slide_height
    new_w, new_h = int(width_in * EMU), int(height_in * EMU)
    sx, sy = new_w / old_w, new_h / old_h
    prs.slide_width, prs.slide_height = new_w, new_h
    for holder in (prs.slide_master, *prs.slide_layouts):
        for shape in holder.shapes:
            if shape._element.xpath(
                "./p:spPr/a:xfrm"
            ):  # a placeholder without its own box inherits the (already scaled) master's
                shape.left, shape.top = int(shape.left * sx), int(shape.top * sy)
                shape.width, shape.height = int(shape.width * sx), int(shape.height * sy)
    theme = prs.slide_master.part.part_related_by(RT.THEME)
    xml = theme.blob.decode("utf-8")
    for index, colour in enumerate(accents, start=1):
        xml = re.sub(
            rf'(<a:accent{index}>)<a:srgbClr val="[0-9A-Fa-f]{{6}}"/>', rf'\1<a:srgbClr val="{colour}"/>', xml
        )
    xml = re.sub(r'(<a:majorFont><a:latin typeface=")[^"]+"', rf'\1{fonts[0]}"', xml)
    xml = re.sub(r'(<a:minorFont><a:latin typeface=")[^"]+"', rf'\1{fonts[1]}"', xml)
    if dark:
        xml = re.sub(r"(<a:dk1>)<a:sysClr[^>]*/>", r'\1<a:srgbClr val="0E1621"/>', xml)
        xml = re.sub(r"(<a:lt1>)<a:sysClr[^>]*/>", r'\1<a:srgbClr val="F4F6FA"/>', xml)
    theme._blob = xml.encode("utf-8")
    if dark:
        cmap = prs.slide_master._element.find(
            "{http://schemas.openxmlformats.org/presentationml/2006/main}clrMap"
        )
        cmap.set("bg1", "dk1")
        cmap.set("tx1", "lt1")
    for name in strip_layouts:
        for layout in list(prs.slide_layouts):
            if layout.name == name:
                prs.slide_layouts.remove(layout)
    if sample_slide:
        slide = prs.slides.add_slide(prs.slide_layouts[0])
        slide.shapes.title.text_frame.text = "SAMPLE SLIDE FROM THE TEMPLATE"
    out = io.BytesIO()
    prs.save(out)
    return out.getvalue()

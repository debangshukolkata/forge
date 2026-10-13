"""Copying package parts (TODO P2.13, D-319): a slide that holds a chart can be duplicated because the chart part, its embedded workbook
and its style parts are cloned under new names, so editing the copy never changes the original. Used by `duplicate_slide` and by
the import of slides from another deck (P2.14)."""

from __future__ import annotations

import re
from typing import Any

from forge.slides.open_deck import DeckError

# Parts that belong to one slide's content and are copied with it. A slide, layout, master or notes page is never cloned this way.
CLONED_KINDS = ("chart", "package", "chartStyle", "chartColorStyle", "themeOverride", "image")
CLONED_PARTS = (
    "/ppt/charts/",
    "/ppt/embeddings/",
    "/ppt/media/",
    "/ppt/drawings/",
    "/ppt/slideMasters/",
    "/ppt/slideLayouts/",
    "/ppt/theme/",
)


def _template(partname: str) -> str:
    """'/ppt/charts/chart3.xml' -> '/ppt/charts/chart%d.xml', for next_partname."""
    match = re.search(r"^(.*?)(\d*)(\.[A-Za-z0-9]+)$", partname)
    if match is None:
        raise DeckError(f"cannot copy the part {partname}")
    return f"{match.group(1)}%d{match.group(3)}"


def _free_partname(package: Any, template: str, memo: dict[str, Any]) -> Any:
    """The next unused name for the template. Parts cloned so far are not linked into the package yet, so they are tracked in `memo`."""
    from pptx.opc.packuri import PackURI

    used = memo.setdefault("names", {str(part.partname) for part in package.iter_parts()})
    number = 1
    while template % number in used:
        number += 1
    name = template % number
    used.add(name)
    return PackURI(name)


def clone_part(part: Any, package: Any, memo: dict[str, Any] | None = None) -> Any:
    """A copy of `part` and of everything it points to, under new part names in `package` (which may be another deck's package)."""
    from pptx.opc.package import PartFactory

    memo = {} if memo is None else memo
    key = str(part.partname)
    if key in memo:
        return memo[key]
    if not key.startswith(CLONED_PARTS):
        raise DeckError(f"the part {key} cannot be copied safely: add a new slide and build it again")
    partname = _free_partname(package, _template(key), memo)
    clone = PartFactory(partname, part.content_type, package, part.blob)
    memo[key] = clone
    from pptx.opc.package import _Relationship

    for relation in part.rels.values():
        target: Any = (
            relation.target_ref if relation.is_external else clone_part(relation.target_part, package, memo)
        )
        # the relationship id stays the same, because the part's XML refers to it
        clone.rels._rels[relation.rId] = _Relationship(
            clone.partname.baseURI, relation.rId, relation.reltype, relation._target_mode, target
        )
    return clone


NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
UNSUPPORTED_COPY = (
    "oleObject",
    "package",
    "video",
    "audio",
    "media",
    "diagramData",
)  # a chart is cloned instead


def copy_slide(
    source: Any,
    deck: Any,
    layout: Any,
    memo: dict[str, Any] | None = None,
    scale: tuple[float, float] = (1.0, 1.0),
) -> Any:
    """A new slide at the end of `deck` that looks like `source`, built on `layout` (a layout of `deck`). The source may belong to another
    deck: pictures and charts are then cloned into this one (once per picture, through `memo`). Returns the new slide, or raises
    DeckError naming what cannot be copied."""
    from copy import deepcopy

    same_package = source.part.package is deck.part.package
    memo = {} if memo is None else memo
    copy = deck.slides.add_slide(layout)
    try:
        for shape in list(copy.shapes):
            shape._element.getparent().remove(shape._element)
        tree = copy.shapes._spTree
        for element in source.shapes._spTree:
            if not element.tag.endswith(("}nvGrpSpPr", "}grpSpPr", "}extLst")):
                tree.append(deepcopy(element))
        if scale != (1.0, 1.0):
            _scale_top_level(tree, scale)
        for node in list(tree.iter()):
            for attribute in ("embed", "link", "id", "pict"):
                old = node.get(f"{{{NS_R}}}{attribute}")
                if old is None:
                    continue
                _carry_relationship(source, copy, node, attribute, old, same_package, deck.part.package, memo)
        background = source._element.cSld.find(f"{{{NS_P}}}bg")
        if background is not None:
            copy._element.cSld.insert(0, deepcopy(background))
            _carry_background(source, copy, background, same_package, deck.part.package, memo)
        if source.has_notes_slide:
            copy.notes_slide.notes_text_frame.text = source.notes_slide.notes_text_frame.text
    except DeckError:
        entries = deck.slides._sldIdLst
        last = list(entries)[-1]
        deck.part.drop_rel(last.rId)
        entries.remove(last)
        raise
    return copy


def _scale_top_level(tree: Any, scale: tuple[float, float]) -> None:
    """Moves and resizes the slide's own shapes for a deck of another slide size (text sizes are left alone)."""
    sx, sy = scale
    for transform in tree.xpath("./*/p:spPr/a:xfrm | ./p:graphicFrame/p:xfrm | ./p:grpSp/p:grpSpPr/a:xfrm"):
        offset = transform.find("{http://schemas.openxmlformats.org/drawingml/2006/main}off")
        extent = transform.find("{http://schemas.openxmlformats.org/drawingml/2006/main}ext")
        if offset is not None:
            offset.set("x", str(round(int(offset.get("x", "0")) * sx)))
            offset.set("y", str(round(int(offset.get("y", "0")) * sy)))
        if extent is not None:
            extent.set("cx", str(round(int(extent.get("cx", "0")) * sx)))
            extent.set("cy", str(round(int(extent.get("cy", "0")) * sy)))


def _carry_relationship(
    source: Any,
    copy: Any,
    node: Any,
    attribute: str,
    old: str,
    same_package: bool,
    package: Any,
    memo: dict[str, Any],
) -> None:
    relation = source.part.rels[old]
    kind = relation.reltype.rsplit("/", 1)[-1]
    key = f"{{{NS_R}}}{attribute}"
    if kind in UNSUPPORTED_COPY:
        raise DeckError(
            f"the slide holds a {kind}, which cannot be copied safely: add a new slide and build it again"
        )
    if relation.is_external:
        node.set(key, copy.part.relate_to(relation.target_ref, relation.reltype, is_external=True))
    elif kind == "chart" or (not same_package and kind == "image"):
        node.set(key, copy.part.relate_to(clone_part(relation.target_part, package, memo), relation.reltype))
    elif same_package:
        node.set(key, copy.part.relate_to(relation.target_part, relation.reltype))
    elif kind == "slide" and node.tag.endswith(
        "}hlinkClick"
    ):  # a jump to a slide of the other deck leads nowhere here
        node.getparent().remove(node)
    else:
        raise DeckError(
            f"the slide has a {kind} link that cannot be carried into another deck: add a new slide and build it again"
        )


def _carry_background(
    source: Any, copy: Any, background: Any, same_package: bool, package: Any, memo: dict[str, Any]
) -> None:
    """A picture used as the slide background is a relationship of its own."""
    key = f"{{{NS_R}}}embed"
    for node in background.iter():
        old = node.get(key)
        if old is None:
            continue
        relation = source.part.rels[old]
        target = relation.target_part if same_package else clone_part(relation.target_part, package, memo)
        copy._element.cSld.find(f"{{{NS_P}}}bg")  # the copied element is the one in the new slide
        for new_node in copy._element.cSld.find(f"{{{NS_P}}}bg").iter():
            if new_node.get(key) == old:
                new_node.set(key, copy.part.relate_to(target, relation.reltype))

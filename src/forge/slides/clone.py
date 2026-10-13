"""Copying package parts (TODO P2.13, D-319): a slide that holds a chart can be duplicated because the chart part, its embedded workbook
and its style parts are cloned under new names, so editing the copy never changes the original. Used by `duplicate_slide` and by
the import of slides from another deck (P2.14)."""

from __future__ import annotations

import re
from typing import Any

from forge.slides.open_deck import DeckError

# Parts that belong to one slide's content and are copied with it. A slide, layout, master or notes page is never cloned this way.
CLONED_KINDS = ("chart", "package", "chartStyle", "chartColorStyle", "themeOverride", "image")
CLONED_PARTS = ("/ppt/charts/", "/ppt/embeddings/", "/ppt/media/", "/ppt/drawings/")


def _template(partname: str) -> str:
    """'/ppt/charts/chart3.xml' -> '/ppt/charts/chart%d.xml', for next_partname."""
    match = re.search(r"^(.*?)(\d*)(\.[A-Za-z0-9]+)$", partname)
    if match is None:
        raise DeckError(f"cannot copy the part {partname}")
    return f"{match.group(1)}%d{match.group(3)}"


def clone_part(part: Any, package: Any, memo: dict[str, Any] | None = None) -> Any:
    """A copy of `part` and of everything it points to, under new part names in `package` (which may be another deck's package)."""
    from pptx.opc.package import PartFactory

    memo = {} if memo is None else memo
    key = str(part.partname)
    if key in memo:
        return memo[key]
    if not key.startswith(CLONED_PARTS):
        raise DeckError(f"the part {key} cannot be copied safely: add a new slide and build it again")
    partname = package.next_partname(_template(key))
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

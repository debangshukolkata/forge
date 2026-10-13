"""Package validator for finished .pptx files (TODO P1.8, D-277). PowerPoint refuses or "repairs" a file when its package
breaks a few structural rules; python-pptx rarely breaks them, but our own editing code (and a model's XML patches)
can. These checks are written from the Open Packaging Conventions and PresentationML rules, use only the standard
library, and name the part and the fix. They do not prove a file opens (only PowerPoint does); they catch the usual
causes of the repair prompt before the user ever sees it."""

from __future__ import annotations

import io
import posixpath
import re
import zipfile
from xml.etree import ElementTree as ET

CONTENT_TYPES = "[Content_Types].xml"
NS_CT = "{http://schemas.openxmlformats.org/package/2006/content-types}"
NS_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
NS_P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
NS_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
NS_C = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"
NS_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
MIN_SLIDE_ID = 256
MAX_FONT_HUNDREDTHS = 400_000  # 4000 pt, the schema limit for sz
MAX_PROBLEMS = 40


def _parse(data: bytes, name: str, problems: list[str]) -> ET.Element | None:
    try:
        return ET.fromstring(data)
    except ET.ParseError as error:
        problems.append(f"{name}: the XML is not well formed ({error})")
        return None


def _resolve(rels_name: str, target: str) -> str:
    """The part a relationship points to: targets are relative to the folder of the part that owns the rels file."""
    if target.startswith("/"):
        return target.lstrip("/")
    owner_folder = posixpath.dirname(posixpath.dirname(rels_name))
    return posixpath.normpath(posixpath.join(owner_folder, target))


def _check_content_types(names: set[str], archive: zipfile.ZipFile, problems: list[str]) -> None:
    if CONTENT_TYPES not in names:
        problems.append(f"{CONTENT_TYPES} is missing: PowerPoint cannot read the package")
        return
    root = _parse(archive.read(CONTENT_TYPES), CONTENT_TYPES, problems)
    if root is None:
        return
    defaults = {e.get("Extension", "").lower() for e in root.findall(f"{NS_CT}Default")}
    overrides = {e.get("PartName", "").lstrip("/") for e in root.findall(f"{NS_CT}Override")}
    for part in overrides:
        if part not in names:
            problems.append(f"{CONTENT_TYPES}: an override names the part {part}, which is not in the file")
    for name in sorted(names):
        if name == CONTENT_TYPES or name.endswith("/"):
            continue
        extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if name not in overrides and extension not in defaults:
            problems.append(f"{name}: has no content type (no Default for .{extension} and no Override)")


def _check_relationships(
    names: set[str], archive: zipfile.ZipFile, problems: list[str]
) -> dict[str, dict[str, str]]:
    """Every internal relationship target exists and ids are unique; returns rels file -> {id: target part}."""
    found: dict[str, dict[str, str]] = {}
    for name in sorted(n for n in names if n.endswith(".rels")):
        root = _parse(archive.read(name), name, problems)
        if root is None:
            continue
        ids: dict[str, str] = {}
        for rel in root.findall(f"{NS_REL}Relationship"):
            rel_id = rel.get("Id", "")
            if rel_id in ids:
                problems.append(f"{name}: the relationship id {rel_id} is used twice")
            if rel.get("TargetMode") == "External":
                ids[rel_id] = ""
                continue
            part = _resolve(name, rel.get("Target", ""))
            ids[rel_id] = part
            if part not in names:
                problems.append(f"{name}: relationship {rel_id} points to {part}, which is not in the file")
        found[name] = ids
    return found


def _rels_for(part: str) -> str:
    folder, base = posixpath.split(part)
    return posixpath.join(folder, "_rels", base + ".rels")


def _check_presentation(
    archive: zipfile.ZipFile, rels: dict[str, dict[str, str]], problems: list[str]
) -> list[str]:
    """The slide list; returns the slide parts in order."""
    name = "ppt/presentation.xml"
    if name not in archive.namelist():
        problems.append("ppt/presentation.xml is missing: this is not a PowerPoint package")
        return []
    root = _parse(archive.read(name), name, problems)
    if root is None:
        return []
    slide_rels = rels.get(_rels_for(name), {})
    seen: set[str] = set()
    slides: list[str] = []
    for item in root.iter(f"{NS_P}sldId"):
        slide_id, rel_id = item.get("id", ""), item.get(f"{NS_R}id", "")
        if not slide_id.isdigit() or int(slide_id) < MIN_SLIDE_ID:
            problems.append(f"{name}: slide id {slide_id!r} must be a number of at least {MIN_SLIDE_ID}")
        if slide_id in seen:
            problems.append(f"{name}: slide id {slide_id} is used twice")
        seen.add(slide_id)
        if rel_id not in slide_rels or not slide_rels[rel_id]:
            problems.append(f"{name}: a slide refers to relationship {rel_id}, which does not exist")
        else:
            slides.append(slide_rels[rel_id])
    return slides


def _check_slide(
    archive: zipfile.ZipFile, part: str, rels: dict[str, dict[str, str]], problems: list[str]
) -> None:
    root = _parse(archive.read(part), part, problems)
    if root is None:
        return
    ids: dict[str, int] = {}
    for element in root.iter(f"{NS_P}cNvPr"):
        shape_id = element.get("id", "")
        ids[shape_id] = ids.get(shape_id, 0) + 1
    for shape_id, count in ids.items():
        if count > 1:
            problems.append(
                f"{part}: the shape id {shape_id} is used by {count} shapes (ids must be unique per slide)"
            )
    own = rels.get(_rels_for(part), {})
    for tag in ("embed", "link", "id"):
        for element in root.iter():
            value = element.get(f"{NS_R}{tag}")
            if value and value not in own:
                problems.append(f"{part}: refers to relationship {value}, which the slide does not have")
    c_sld = root.find(f"{NS_P}cSld")
    if c_sld is None:
        problems.append(f"{part}: the slide has no p:cSld element")
    else:
        order = [child.tag for child in c_sld]
        if f"{NS_P}spTree" not in order:
            problems.append(f"{part}: the slide has no shape tree (p:spTree)")
        tree = c_sld.find(f"{NS_P}spTree")
        if tree is not None:
            first = [child.tag for child in tree][:2]
            if first != [f"{NS_P}nvGrpSpPr", f"{NS_P}grpSpPr"]:
                problems.append(f"{part}: p:spTree must start with p:nvGrpSpPr then p:grpSpPr")
    children = [child.tag for child in root]
    overlay, content = f"{NS_P}clrMapOvr", f"{NS_P}cSld"
    if overlay in children and content in children and children.index(overlay) < children.index(content):
        problems.append(f"{part}: p:clrMapOvr must come after p:cSld")
    for table in root.iter(f"{NS_A}tbl"):
        tags = [child.tag for child in table]
        if tags[:2] != [f"{NS_A}tblPr", f"{NS_A}tblGrid"] and f"{NS_A}tblGrid" not in tags:
            problems.append(f"{part}: a table has no a:tblGrid")
            continue
        columns = len(table.findall(f"{NS_A}tblGrid/{NS_A}gridCol"))
        for number, row in enumerate(table.findall(f"{NS_A}tr"), start=1):
            cells = len(row.findall(f"{NS_A}tc"))
            if cells != columns:
                problems.append(
                    f"{part}: table row {number} has {cells} cells but the grid has {columns} columns"
                )
    for paragraph in root.iter(f"{NS_A}p"):
        kids = [child.tag for child in paragraph]
        if f"{NS_A}pPr" in kids and kids.index(f"{NS_A}pPr") != 0:
            problems.append(f"{part}: a paragraph has a:pPr after its text; it must be first")
        if f"{NS_A}endParaRPr" in kids and kids.index(f"{NS_A}endParaRPr") != len(kids) - 1:
            problems.append(f"{part}: a paragraph has a:endParaRPr before its last run; it must be last")
    for properties in root.iter(f"{NS_A}rPr"):
        size = properties.get("sz")
        if size and (not size.isdigit() or not 100 <= int(size) <= MAX_FONT_HUNDREDTHS):
            problems.append(
                f"{part}: a text run has the font size {size}; sz is in hundredths of a point (100 to 400000)"
            )


def _check_chart(
    archive: zipfile.ZipFile, part: str, rels: dict[str, dict[str, str]], problems: list[str]
) -> None:
    root = _parse(archive.read(part), part, problems)
    if root is None:
        return
    if root.find(f"{NS_C}chart") is None:
        problems.append(f"{part}: the chart has no c:chart element")
        return
    plot_area = root.find(f"{NS_C}chart/{NS_C}plotArea")
    for plot in list(plot_area) if plot_area is not None else []:
        indexes = [
            idx.get("val")
            for series in plot.findall(f"{NS_C}ser")
            if (idx := series.find(f"{NS_C}idx")) is not None
        ]
        if len(indexes) != len(set(indexes)):
            problems.append(f"{part}: two series share the same c:idx")
    external = root.find(f"{NS_C}externalData")
    if external is not None:
        rel_id = external.get(f"{NS_R}id", "")
        if rel_id not in rels.get(_rels_for(part), {}):
            problems.append(f"{part}: the embedded workbook relationship {rel_id} is missing")


def validate_package(data: bytes) -> list[str]:
    """Faults that make PowerPoint refuse the file or offer to repair it; an empty list means none were found."""
    problems: list[str] = []
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return ["the file is not a zip package: it cannot be a .pptx"]
    with archive:
        raw_names = archive.namelist()
        names = set(raw_names)
        if len(raw_names) != len(names):
            problems.append("the package contains the same part name twice")
        _check_content_types(names, archive, problems)
        rels = _check_relationships(names, archive, problems)
        for slide in _check_presentation(archive, rels, problems):
            if slide in names:
                _check_slide(archive, slide, rels, problems)
        for name in sorted(n for n in names if re.fullmatch(r"ppt/charts/chart\d+\.xml", n)):
            _check_chart(archive, name, rels, problems)
        for name in sorted(
            n for n in names if n.endswith(".xml") and n.startswith("ppt/") and "/slides/" not in n
        ):
            _parse(archive.read(name), name, problems)
    return problems[:MAX_PROBLEMS]

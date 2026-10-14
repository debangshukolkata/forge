"""Structure validator for a finished Office file (D-345): the checks that catch the usual causes of the "repair" prompt.

Written from the Open Packaging Conventions (ECMA-376 part 2) with the standard library only. They do not prove the file opens (only the
Office program does); they name the part and the fix."""

from __future__ import annotations

import posixpath
import zipfile
from xml.etree import ElementTree as ET

from forge.ooxml.check import PackageError, kind_of, open_archive

CONTENT_TYPES = "[Content_Types].xml"
NS_CT = "{http://schemas.openxmlformats.org/package/2006/content-types}"
NS_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
NS_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
NS_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NS_S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
MAIN_CONTENT_TYPE = {
    "docx": "wordprocessingml.document.main+xml",
    "xlsx": "spreadsheetml.sheet.main+xml",
    "pptx": "presentationml.presentation.main+xml",
}
BAD_SHEET_CHARACTERS = "[]:*?/\\"
MAX_PROBLEMS = 40


def _parse(data: bytes, name: str, problems: list[str]) -> ET.Element | None:
    try:
        return ET.fromstring(data)
    except ET.ParseError as error:
        problems.append(f"{name}: the XML is not well formed ({error})")
        return None


def _resolve(rels_name: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    owner_folder = posixpath.dirname(posixpath.dirname(rels_name))
    return posixpath.normpath(posixpath.join(owner_folder, target))


def _content_types(names: set[str], archive: zipfile.ZipFile, kind: str, problems: list[str]) -> None:
    if CONTENT_TYPES not in names:
        problems.append(f"{CONTENT_TYPES} is missing: the Office program cannot read the package")
        return
    root = _parse(archive.read(CONTENT_TYPES), CONTENT_TYPES, problems)
    if root is None:
        return
    defaults = {e.get("Extension", "").lower() for e in root.findall(f"{NS_CT}Default")}
    overrides = {
        e.get("PartName", "").lstrip("/"): e.get("ContentType", "") for e in root.findall(f"{NS_CT}Override")
    }
    for name in sorted(names):
        if name == CONTENT_TYPES or name.endswith("/"):
            continue
        extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if name not in overrides and extension not in defaults:
            problems.append(f"{name}: has no content type (no Default for .{extension} and no Override)")
    for part in overrides:
        if part not in names:
            problems.append(f"{CONTENT_TYPES}: an Override names {part}, which is not in the file")
    wanted = MAIN_CONTENT_TYPE.get(kind)
    if wanted and not any(wanted in value for value in overrides.values()):
        problems.append(
            f"{CONTENT_TYPES}: the main part has no {wanted} content type "
            "(a template or macro file saved under the wrong extension?)"
        )


def _relationships(
    names: set[str], archive: zipfile.ZipFile, problems: list[str]
) -> dict[str, dict[str, str]]:
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


def _word(archive: zipfile.ZipFile, rels: dict[str, dict[str, str]], problems: list[str]) -> None:
    root = _parse(archive.read("word/document.xml"), "word/document.xml", problems)
    if root is None:
        return
    known = rels.get(_rels_for("word/document.xml"), {})
    for element in root.iter():
        for key, value in element.attrib.items():
            if key in (f"{NS_R}id", f"{NS_R}embed", f"{NS_R}link") and value not in known:
                problems.append(
                    f"word/document.xml: {key.rsplit('}', 1)[-1]}={value} has no relationship "
                    "(a missing picture or link target)"
                )
    body = root.find(f"{NS_W}body")
    if body is None:
        problems.append("word/document.xml: there is no body element")
    elif body.find(f"{NS_W}sectPr") is None:
        problems.append("word/document.xml: the body has no section properties (page size and margins)")


def _excel(
    archive: zipfile.ZipFile, rels: dict[str, dict[str, str]], names: set[str], problems: list[str]
) -> None:
    root = _parse(archive.read("xl/workbook.xml"), "xl/workbook.xml", problems)
    if root is None:
        return
    known = rels.get(_rels_for("xl/workbook.xml"), {})
    seen: set[str] = set()
    sheets = root.find(f"{NS_S}sheets")
    if sheets is None or not len(sheets):
        problems.append("xl/workbook.xml: the workbook has no sheets")
        return
    for sheet in sheets:
        title, rel_id = sheet.get("name", ""), sheet.get(f"{NS_R}id", "")
        if len(title) > 31 or any(c in title for c in BAD_SHEET_CHARACTERS):
            problems.append(
                f"xl/workbook.xml: the sheet name {title!r} is not allowed (31 characters, none of {BAD_SHEET_CHARACTERS})"
            )
        if title.lower() in seen:
            problems.append(f"xl/workbook.xml: two sheets are called {title!r}")
        seen.add(title.lower())
        if rel_id not in known:
            problems.append(f"xl/workbook.xml: sheet {title!r} has no relationship {rel_id}")
        elif known[rel_id] not in names:
            problems.append(
                f"xl/workbook.xml: sheet {title!r} points to {known[rel_id]}, which is not in the file"
            )


def validate_package(data: bytes) -> list[str]:
    """Faults that make Office refuse the file or offer to repair it; an empty list means none were found."""
    problems: list[str] = []
    try:
        archive = open_archive(data)
    except PackageError as error:
        return [str(error)]
    with archive:
        raw = archive.namelist()
        names = set(raw)
        if len(raw) != len(names):
            problems.append("the package contains the same part name twice")
        kind = kind_of(names)
        if kind == "unknown":
            problems.append(
                "the package has no main document part (word/document.xml, xl/workbook.xml or ppt/presentation.xml)"
            )
        _content_types(names, archive, kind, problems)
        rels = _relationships(names, archive, problems)
        if kind == "docx":
            _word(archive, rels, problems)
        elif kind == "xlsx":
            _excel(archive, rels, names, problems)
        for name in sorted(n for n in names if n.endswith(".xml") and n != CONTENT_TYPES):
            if name not in ("word/document.xml", "xl/workbook.xml"):
                _parse(archive.read(name), name, problems)
    return problems[:MAX_PROBLEMS]

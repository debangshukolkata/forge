"""Footnotes for python-docx, which has no footnote support of its own (D-344): the footnotes part is created on first use with the two
separator entries Word expects, then each footnote is a numbered entry whose reference mark is placed in the text."""

from __future__ import annotations

from typing import Any

from forge.documents.spec import DocumentError

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes"
CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"

EMPTY = (
    f'<w:footnotes xmlns:w="{W_NS}">'
    '<w:footnote w:type="separator" w:id="-1"><w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
    "<w:r><w:separator/></w:r></w:p></w:footnote>"
    '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
    "<w:r><w:continuationSeparator/></w:r></w:p></w:footnote>"
    "</w:footnotes>"
)


def _footnotes_part(document: Any) -> Any:
    from docx.opc.packuri import PackURI
    from docx.opc.part import XmlPart
    from docx.oxml import parse_xml

    main = document.part
    for relation in main.rels.values():
        if relation.reltype == REL_TYPE:
            return relation.target_part
    part = XmlPart(PackURI("/word/footnotes.xml"), CONTENT_TYPE, parse_xml(EMPTY), main.package)
    main.relate_to(part, REL_TYPE)
    return part


def _root(part: Any) -> Any:
    """The footnotes XML of `part`: a part made here has it as `element`; one loaded from a file is plain bytes, parsed once and kept."""
    from docx.oxml import parse_xml

    if hasattr(part, "element"):
        return part.element
    if not hasattr(part, "_forge_root"):
        part._forge_root = parse_xml(part.blob)
    return part._forge_root


def _store(part: Any, root: Any) -> None:
    if not hasattr(part, "element"):
        from lxml import etree  # type: ignore[import-untyped]

        part._blob = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def add_footnote(document: Any, paragraph: Any, text: str) -> int:
    """Put a footnote reference at the end of `paragraph` and return the footnote's number."""
    from docx.oxml import OxmlElement, parse_xml
    from docx.oxml.ns import qn

    if not text.strip():
        raise DocumentError("A footnote needs text")
    part = _footnotes_part(document)
    root = _root(part)
    ids = [int(n.get(qn("w:id"))) for n in root.findall(qn("w:footnote"))]
    number = max([0, *ids]) + 1
    note = parse_xml(
        f'<w:footnote xmlns:w="{W_NS}" w:id="{number}"><w:p><w:pPr><w:pStyle w:val="FootnoteText"/></w:pPr>'
        '<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/><w:vertAlign w:val="superscript"/></w:rPr><w:footnoteRef/></w:r>'
        '<w:r><w:t xml:space="preserve"> </w:t></w:r><w:r><w:t></w:t></w:r></w:p></w:footnote>'
    )
    note.findall(f".//{{{W_NS}}}t")[-1].text = text
    root.append(note)
    _store(part, root)
    run = OxmlElement("w:r")
    properties = OxmlElement("w:rPr")
    superscript = OxmlElement("w:vertAlign")
    superscript.set(qn("w:val"), "superscript")
    properties.append(superscript)
    run.append(properties)
    reference = OxmlElement("w:footnoteReference")
    reference.set(qn("w:id"), str(number))
    run.append(reference)
    paragraph._p.append(run)
    return number


def footnote_texts(data_document: Any) -> list[str]:
    """The texts of the document's footnotes, in order."""
    from docx.oxml.ns import qn

    for relation in data_document.part.rels.values():
        if relation.reltype == REL_TYPE:
            root = _root(relation.target_part)
            found = []
            for note in root.findall(qn("w:footnote")):
                if note.get(qn("w:type")) in ("separator", "continuationSeparator"):
                    continue
                found.append("".join(t.text or "" for t in note.iter(qn("w:t"))).strip())
            return found
    return []

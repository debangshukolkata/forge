"""The raw-file escape hatch (TODO P2.15, D-321): unpack a deck to its XML files, let the model edit them, validate, repack.

For what python-pptx cannot do (an odd master, SmartArt text, a custom animation, a field the library does not know). Only XML parts
(`.xml`, `.rels`) are written to the folder, pretty-printed so that a line-based edit works; pictures, workbooks and other binary parts
stay in the original file and are copied back at packing time. Packing starts from the original file, replaces the XML parts with the
folder's, adds files the folder gained, drops XML parts the folder lost, then runs the package validator.

Safety (an untrusted deck is a zip file full of XML):
- the archive is checked before anything is read: entry count, total size, compression ratio per entry, names (no absolute paths, no
  `..`, no drive letters), no encrypted entries;
- XML with a DOCTYPE or entity declaration is refused (entity expansion bombs, external entities);
- packing refuses macro projects and executables, and reports external links the edit added."""

from __future__ import annotations

import io
import posixpath
import re
import zipfile
from dataclasses import dataclass, field

from forge.slides.open_deck import DeckError
from forge.slides.validate import validate_package

MAX_ENTRIES = 5000
MAX_TOTAL_BYTES = 400 * 1024 * 1024
MAX_ENTRY_BYTES = 200 * 1024 * 1024
MAX_RATIO = 250  # uncompressed / compressed, per entry: a bomb is far above this, real decks far below
MANIFEST = "_unpacked.json"
XML_SUFFIXES = (".xml", ".rels")
FORBIDDEN_PARTS = re.compile(
    r"(vbaProject\.bin|vbaData\.xml|\.exe$|\.dll$|\.bat$|\.cmd$|\.ps1$|\.js$|\.vbs$|\.scr$)", re.I
)
UNSAFE_XML = re.compile(rb"<!\s*(DOCTYPE|ENTITY)", re.I)
EXTERNAL = re.compile(
    r'Target="([^"]+)"[^>]*TargetMode="External"|TargetMode="External"[^>]*Target="([^"]+)"'
)


@dataclass
class Unpacked:
    xml: dict[str, bytes] = field(default_factory=dict)  # part name -> pretty-printed XML
    binary: list[str] = field(default_factory=list)  # names left in the original file
    external: list[str] = field(default_factory=list)  # external relationship targets found


RESERVED_NAMES = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$", re.I)
BAD_CHARACTERS = re.compile(r'[\x00-\x1f<>:"|?*\\]')


def _unsafe_name(name: str) -> bool:
    """Absolute paths, parent folders, characters Windows treats specially (`:` makes an NTFS data stream), device names (CON, NUL, ...)
    and names ending in a dot or space are refused: unpacking writes these names to disk."""
    if name.startswith("/") or ".." in name.split("/") or BAD_CHARACTERS.search(name):
        return True
    return any(RESERVED_NAMES.match(part) or part != part.rstrip(". ") for part in name.split("/") if part)


def check_package(data: bytes) -> None:
    """The checks every deck gets before python-pptx reads it: the archive (bombs, names) and the XML (no DOCTYPE or entities)."""
    archive = check_archive(data)
    for info in archive.infolist():
        if info.filename.endswith(XML_SUFFIXES) and not info.is_dir():
            check_xml(info.filename, archive.read(info.filename))


def check_archive(data: bytes) -> zipfile.ZipFile:
    """Opens the zip after checking it against bombs and unsafe names; raises DeckError saying why."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as error:
        raise DeckError("the file is not a valid .pptx package (a zip file)") from error
    entries = archive.infolist()
    if len(entries) > MAX_ENTRIES:
        raise DeckError(f"the package has {len(entries)} entries (more than {MAX_ENTRIES}): it is refused")
    total = 0
    for info in entries:
        name = info.filename
        if _unsafe_name(name):
            raise DeckError(f"the package has an unsafe entry name {name!r}: it is refused")
        if info.flag_bits & 0x1:
            raise DeckError(
                "the package is encrypted or password-protected: ask the user for an unprotected copy"
            )
        if info.file_size > MAX_ENTRY_BYTES:
            raise DeckError(
                f"the entry {name} expands to {info.file_size // (1024 * 1024)} MB: it is refused"
            )
        if (
            info.compress_size
            and info.file_size / info.compress_size > MAX_RATIO
            and info.file_size > 1024 * 1024
        ):
            raise DeckError(
                f"the entry {name} expands {info.file_size // info.compress_size}x (a zip bomb?): it is refused"
            )
        total += info.file_size
    if total > MAX_TOTAL_BYTES:
        raise DeckError(f"the package expands to {total // (1024 * 1024)} MB: it is refused")
    return archive


def check_xml(name: str, data: bytes) -> None:
    if UNSAFE_XML.search(data[:4096]) or UNSAFE_XML.search(data):
        raise DeckError(
            f"{name} declares a DOCTYPE or an entity, which is not allowed in a deck: it is refused"
        )


def _pretty(data: bytes) -> bytes:
    """Indents XML that has no whitespace of its own (python-pptx output); other XML is kept byte for byte."""
    from lxml import etree  # type: ignore[import-untyped]

    try:
        root = etree.fromstring(
            data, etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
        )
    except etree.XMLSyntaxError:
        return data
    if any(node.text and not node.text.strip() for node in root.iter() if len(node) == 0):
        return data  # a text that is only spaces may matter (a space in a:t): leave the part untouched
    return bytes(
        etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8", standalone=True)
    )


def unpack(data: bytes) -> Unpacked:
    archive = check_archive(data)
    result = Unpacked()
    for info in archive.infolist():
        if info.is_dir():
            continue
        name = info.filename
        if FORBIDDEN_PARTS.search(name):
            raise DeckError(
                f"the package contains {name}: macros and executables are not handled; ask for a copy without it"
            )
        content = archive.read(name)
        if name.endswith(XML_SUFFIXES):
            check_xml(name, content)
            result.xml[name] = _pretty(content)
            result.external += [a or b for a, b in EXTERNAL.findall(content.decode("utf-8", "replace"))]
        else:
            result.binary.append(name)
    return result


def pack(original: bytes, folder_files: dict[str, bytes], original_xml: set[str]) -> tuple[bytes, list[str]]:
    """The deck with its XML parts replaced by `folder_files` (name -> bytes). `original_xml` are the XML names unpacked from the
    original: those missing from the folder are removed. Returns (package bytes, notes about new external links)."""
    archive = check_archive(original)
    before_external: set[str] = set()
    parts: dict[str, bytes] = {}
    for info in archive.infolist():
        if info.is_dir():
            continue
        name = info.filename
        if name.endswith(XML_SUFFIXES):
            before_external.update(
                a or b for a, b in EXTERNAL.findall(archive.read(name).decode("utf-8", "replace"))
            )
            continue
        parts[name] = archive.read(name)
    notes: list[str] = []
    for name, content in folder_files.items():
        clean = name.replace("\\", "/")
        if clean.startswith("/") or ".." in clean.split("/") or re.match(r"^[A-Za-z]:", clean):
            raise DeckError(f"{name!r} is not a valid part name")
        if FORBIDDEN_PARTS.search(clean):
            raise DeckError(f"{clean}: macros and executables cannot be added to a deck")
        if clean.endswith(XML_SUFFIXES):
            check_xml(clean, content)
        parts[clean] = content
    removed = [n for n in original_xml if n not in folder_files]
    if removed:
        notes.append("removed XML parts: " + ", ".join(sorted(removed)))
    after_external: set[str] = set()
    for name, content in parts.items():
        if name.endswith(XML_SUFFIXES):
            after_external.update(a or b for a, b in EXTERNAL.findall(content.decode("utf-8", "replace")))
    new_links = sorted(after_external - before_external)
    if new_links:
        notes.append("the edit added external links (tell the user): " + ", ".join(new_links))
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
        order = sorted(parts, key=lambda n: (n != "[Content_Types].xml", not n.startswith("_rels/"), n))
        for name in order:
            target.writestr(name, parts[name])
    faults = validate_package(output.getvalue())
    if faults:
        raise DeckError(
            "the repacked deck has structural faults, nothing was saved:\n"
            + "\n".join(f"- {f}" for f in faults)
        )
    return output.getvalue(), notes


def relative_name(folder: str, path: str) -> str:
    """The part name of a file inside the unpack folder."""
    return posixpath.relpath(path.replace("\\", "/"), folder.replace("\\", "/"))

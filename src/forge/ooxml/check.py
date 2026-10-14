"""The safety check for an Office file before any library reads it (D-345)."""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field

from forge.errors import ForgeError

MAX_ENTRIES = 5000
MAX_TOTAL_BYTES = 400 * 1024 * 1024
MAX_ENTRY_BYTES = 200 * 1024 * 1024
MAX_RATIO = 250  # uncompressed / compressed, per entry: a bomb is far above this, real files far below
RESERVED_NAMES = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$", re.I)
BAD_CHARACTERS = re.compile(r'[\x00-\x1f<>:"|?*\\]')
UNSAFE_XML = re.compile(rb"<!\s*(DOCTYPE|ENTITY)", re.I)
EXTERNAL = re.compile(
    r'Target="([^"]+)"[^>]*TargetMode="External"|TargetMode="External"[^>]*Target="([^"]+)"'
)
MACRO_PARTS = re.compile(r"(vbaProject\.bin|vbaData\.xml)$", re.I)
EXECUTABLE_PARTS = re.compile(r"\.(exe|dll|bat|cmd|ps1|js|vbs|scr|com|msi)$", re.I)


class PackageError(ForgeError):
    """The file is refused; the message says which entry and why."""


@dataclass
class PackageReport:
    kind: str  # "docx", "xlsx", "pptx" or "unknown"
    macros: bool = False
    executables: list[str] = field(default_factory=list)
    external_links: list[str] = field(default_factory=list)
    embedded_objects: list[str] = field(default_factory=list)
    activex: bool = False

    def notes(self) -> list[str]:
        found = []
        if self.macros:
            found.append(
                "it contains a macro project (never run by DebCraft and not kept when DebCraft saves)"
            )
        if self.executables:
            found.append("it contains program files: " + ", ".join(self.executables[:5]))
        if self.external_links:
            found.append(
                f"it links to {len(self.external_links)} outside address(es), not followed: "
                + ", ".join(self.external_links[:3])
            )
        if self.embedded_objects:
            found.append(f"it embeds {len(self.embedded_objects)} object(s), not opened")
        if self.activex:
            found.append("it has ActiveX controls (never run)")
        return found


def _unsafe_name(name: str) -> bool:
    """Absolute paths, parent folders, characters Windows treats specially and device names are refused: unpacking writes these names to disk."""
    if name.startswith("/") or ".." in name.split("/") or BAD_CHARACTERS.search(name):
        return True
    return any(RESERVED_NAMES.match(part) or part != part.rstrip(". ") for part in name.split("/") if part)


def open_archive(data: bytes) -> zipfile.ZipFile:
    """The zip, opened after the checks for bombs and unsafe names."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as error:
        raise PackageError(
            "the file is not a valid Office package (a zip file): it may be damaged, or an old .doc/.xls/.ppt"
        ) from error
    entries = archive.infolist()
    if len(entries) > MAX_ENTRIES:
        raise PackageError(f"the package has {len(entries)} entries (more than {MAX_ENTRIES}): it is refused")
    total = 0
    for info in entries:
        name = info.filename
        if _unsafe_name(name):
            raise PackageError(f"the package has an unsafe entry name {name!r}: it is refused")
        if info.flag_bits & 0x1:
            raise PackageError(
                "the package is encrypted or password-protected: ask the user for an unprotected copy"
            )
        if info.file_size > MAX_ENTRY_BYTES:
            raise PackageError(
                f"the entry {name} expands to {info.file_size // (1024 * 1024)} MB: it is refused"
            )
        if (
            info.compress_size
            and info.file_size / info.compress_size > MAX_RATIO
            and info.file_size > 1024 * 1024
        ):
            raise PackageError(
                f"the entry {name} expands {info.file_size // info.compress_size}x (a zip bomb?): it is refused"
            )
        total += info.file_size
    if total > MAX_TOTAL_BYTES:
        raise PackageError(f"the package expands to {total // (1024 * 1024)} MB: it is refused")
    return archive


def check_xml(name: str, data: bytes) -> None:
    """Refuses XML with a DOCTYPE or an entity declaration (expansion bombs, external entities)."""
    if UNSAFE_XML.search(data):
        raise PackageError(
            f"{name} declares a DOCTYPE or an entity, which is not allowed in an Office file: it is refused"
        )


def kind_of(names: set[str]) -> str:
    if "word/document.xml" in names:
        return "docx"
    if "xl/workbook.xml" in names:
        return "xlsx"
    if "ppt/presentation.xml" in names:
        return "pptx"
    return "unknown"


def check_package(data: bytes) -> PackageReport:
    """Refuses a hostile package (raises `PackageError`); otherwise says what the file carries."""
    archive = open_archive(data)
    names = {i.filename for i in archive.infolist()}
    report = PackageReport(kind_of(names))
    for info in archive.infolist():
        name = info.filename
        if info.is_dir():
            continue
        if MACRO_PARTS.search(name):
            report.macros = True
        elif EXECUTABLE_PARTS.search(name) and "/embeddings/" not in name:
            report.executables.append(name)
        if "/embeddings/" in name:
            report.embedded_objects.append(name)
        if "/activeX/" in name or "/ActiveX/" in name:
            report.activex = True
        if name.endswith((".xml", ".rels")):
            content = archive.read(name)
            check_xml(name, content)
            if name.endswith(".rels"):
                for match in EXTERNAL.finditer(content.decode("utf-8", errors="replace")):
                    target = match.group(1) or match.group(2)
                    if target and not target.startswith("mailto:"):
                        report.external_links.append(target)
    report.external_links = list(dict.fromkeys(report.external_links))
    return report

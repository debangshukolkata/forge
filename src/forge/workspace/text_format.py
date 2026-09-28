"""Detects and preserves a file's encoding, BOM and line endings (spec §9.1).

Forge edits text with "\\n" line endings internally and writes it back in the file's original format,
so a CRLF, BOM-prefixed or cp1252 file stays exactly that way.
"""

from __future__ import annotations

import codecs
from typing import Literal

from pydantic import BaseModel

Newline = Literal["lf", "crlf", "cr", "mixed", "none"]

_BOMS = [
    (codecs.BOM_UTF8, "utf-8"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
]
_NEWLINE_TEXT = {"crlf": "\r\n", "cr": "\r"}
BINARY_SNIFF_BYTES = 8192


class FileFormat(BaseModel):
    binary: bool = False
    encoding: str = "utf-8"
    bom: bool = False
    newline: Newline = "lf"


def detect_format(data: bytes) -> FileFormat:
    for bom, encoding in _BOMS:
        if data.startswith(bom):
            text = data[len(bom) :].decode(encoding, errors="replace")
            return FileFormat(encoding=encoding, bom=True, newline=detect_newline(text))
    if b"\x00" in data[:BINARY_SNIFF_BYTES]:
        return FileFormat(binary=True, encoding="", newline="none")
    for encoding in ("utf-8", "cp1252"):
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        return FileFormat(encoding=encoding, newline=detect_newline(text))
    # latin-1 decodes any byte sequence, so round-tripping is always exact.
    return FileFormat(encoding="latin-1", newline=detect_newline(data.decode("latin-1")))


def detect_newline(text: str) -> Newline:
    crlf = text.count("\r\n")
    lone_cr = text.count("\r") - crlf
    lone_lf = text.count("\n") - crlf
    kinds = [kind for kind, count in (("crlf", crlf), ("cr", lone_cr), ("lf", lone_lf)) if count]
    if not kinds:
        return "none"
    if len(kinds) > 1:
        return "mixed"
    return kinds[0]  # type: ignore[return-value]  # one of the three literals above


def decode_text(data: bytes, file_format: FileFormat) -> str:
    if file_format.binary:
        raise ValueError("binary file")
    body = data[len(_bom_bytes(file_format)) :] if file_format.bom else data
    text = body.decode(file_format.encoding)
    # Mixed endings are left untouched so an edit never silently rewrites unrelated lines.
    if file_format.newline in _NEWLINE_TEXT:
        text = text.replace(_NEWLINE_TEXT[file_format.newline], "\n")
    return text


def encode_text(text: str, file_format: FileFormat) -> bytes:
    if file_format.binary:
        raise ValueError("binary file")
    if file_format.newline in _NEWLINE_TEXT:
        text = text.replace("\r\n", "\n").replace("\n", _NEWLINE_TEXT[file_format.newline])
    data = text.encode(file_format.encoding)
    return _bom_bytes(file_format) + data if file_format.bom else data


def _bom_bytes(file_format: FileFormat) -> bytes:
    for bom, encoding in _BOMS:
        if encoding == file_format.encoding:
            return bom
    return b""

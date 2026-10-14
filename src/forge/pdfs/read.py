"""Read a PDF: text per page in reading layout, metadata, form fields, pictures, protection (D-343)."""

from __future__ import annotations

import contextlib
import importlib
import io
import logging
from dataclasses import dataclass, field
from typing import Any

from forge.errors import ForgeError

MAX_PAGES = 600


class PdfError(ForgeError):
    """The PDF cannot be read or changed; the message says what to do."""


def load_pypdf() -> Any:
    try:
        module = importlib.import_module("pypdf")
        logging.getLogger("pypdf").setLevel(
            logging.ERROR
        )  # its font warnings fill the terminal and tell the user nothing
        return module
    except ImportError as error:
        raise PdfError("pypdf is not installed: pip install pypdf (the forge[docs] extra)") from error


def open_pdf(data: bytes, password: str = "") -> Any:
    pypdf = load_pypdf()
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
    except Exception as error:
        raise PdfError(f"The file could not be read as a PDF ({type(error).__name__}); damaged?") from error
    if reader.is_encrypted:
        if not password:
            raise PdfError(
                "The PDF is password-protected: ask the user for the password (or an unprotected copy)."
            )
        if not reader.decrypt(password):
            raise PdfError("The password does not open this PDF.")
    return reader


@dataclass
class PdfInfo:
    pages: int
    title: str
    author: str
    encrypted: bool
    texts: list[str] = field(default_factory=list)
    form_fields: dict[str, str] = field(default_factory=dict)
    pictures: int = 0
    risky: list[str] = field(default_factory=list)  # JavaScript, launch actions, embedded files
    scanned: bool = False


def _risky(reader: Any) -> list[str]:
    found = []
    root = reader.trailer["/Root"]
    names = root.get("/Names", {}) if hasattr(root, "get") else {}
    if hasattr(names, "get_object"):
        names = names.get_object()
    if "/JavaScript" in names or "/OpenAction" in root or "/AA" in root:
        found.append("it has JavaScript or an action that runs on opening (never run by DebCraft)")
    if "/EmbeddedFiles" in names:
        found.append("it has embedded files (not opened)")
    return found


def read_pdf(data: bytes, password: str = "", layout: bool = True) -> PdfInfo:
    reader = open_pdf(data, password)
    metadata = reader.metadata
    pages = reader.pages[:MAX_PAGES]
    texts = []
    pictures = 0
    for page in pages:
        try:
            text = page.extract_text(extraction_mode="layout") if layout else page.extract_text()
        except Exception:
            text = page.extract_text()
        texts.append((text or "").rstrip())
        with contextlib.suppress(Exception):  # a damaged picture entry must not stop the text
            pictures += len(page.images)
    fields = {}
    try:
        for name, value in (reader.get_fields() or {}).items():
            fields[str(name)] = "" if value.get("/V") is None else str(value.get("/V"))
    except Exception:
        pass
    return PdfInfo(
        len(reader.pages),
        (metadata.title if metadata and metadata.title else "") or "",
        (metadata.author if metadata and metadata.author else "") or "",
        bool(reader.is_encrypted),
        texts,
        fields,
        pictures,
        _risky(reader),
        scanned=not any(t.strip() for t in texts),
    )


def describe_pdf(info: PdfInfo, name: str = "document", limit: int = 12000) -> str:
    lines = [
        f"{name}: {info.pages} page(s), title {info.title!r}, author {info.author!r}, {info.pictures} picture(s)"
        + (", protected (opened with the password given)" if info.encrypted else "")
    ]
    lines += [f"WARNING: {risk}" for risk in info.risky]
    if info.scanned:
        lines.append(
            "No text layer: this is a scan. Render its pages with pdf_render and read them with ocr_image (or view_image for layout)."
        )
    if info.form_fields:
        lines.append(
            "Form fields: " + "; ".join(f"{k} = {v!r}" for k, v in list(info.form_fields.items())[:60])
        )
    body = []
    for number, text in enumerate(info.texts, start=1):
        if text.strip():
            body.append(f"\n[page {number}]\n{text}")
    text = "\n".join(lines) + "\n" + "".join(body)
    return (
        text
        if len(text) <= limit
        else text[:limit] + f"\n... (cut at {limit} characters; ask for fewer pages)"
    )

"""Opening an existing .pptx (or a .potx template) for reading or editing (D-241)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any

from forge.errors import ForgeError
from forge.slides.build import SlidesUnavailable

MAX_BYTES = 80 * 1024 * 1024
TEMPLATE_TYPE = b"application/vnd.openxmlformats-officedocument.presentationml.template.main+xml"
PRESENTATION_TYPE = b"application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"


class DeckError(ForgeError):
    """The file cannot be opened or the change cannot be made; the message says what to do."""


def open_deck(path: Path) -> Any:
    """The python-pptx presentation of `path`. A template (.potx) opens as a new deck built on its layouts."""
    try:
        from pptx import Presentation
    except ImportError as error:
        raise SlidesUnavailable(
            "python-pptx is not installed here. Install it with: pip install python-pptx (or forge[slides])."
        ) from error
    suffix = path.suffix.lower()
    if suffix not in {".pptx", ".potx"}:
        raise DeckError(f"{path.name}: only .pptx and .potx files can be opened (not .ppt, .pptm or .key).")
    if path.stat().st_size > MAX_BYTES:
        raise DeckError(f"{path.name} is larger than {MAX_BYTES // (1024 * 1024)} MB.")
    data = path.read_bytes()
    try:
        if suffix == ".potx":  # python-pptx only knows the content type of a presentation
            data = _as_presentation(data)
        return Presentation(io.BytesIO(data))
    except Exception as error:  # a damaged or protected file: python-pptx raises many different errors
        raise DeckError(
            f"{path.name} could not be opened ({type(error).__name__}); is it damaged or password-protected?"
        ) from error


def _as_presentation(data: bytes) -> bytes:
    source = zipfile.ZipFile(io.BytesIO(data))
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            content = source.read(item.filename)
            if item.filename == "[Content_Types].xml":
                content = content.replace(TEMPLATE_TYPE, PRESENTATION_TYPE)
            target.writestr(item, content)
    return output.getvalue()


def save_deck(deck: Any) -> bytes:
    output = io.BytesIO()
    deck.save(output)
    return output.getvalue()

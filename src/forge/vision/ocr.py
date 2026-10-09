"""Reading text out of pixels with Tesseract (D-203), run on this computer: nothing is sent anywhere.

Used by the `ocr_image` tool and by the Environment drawer's test. Tesseract is optional: the user says on the
drawer whether it is installed (D-201) and Forge only offers the tool once the test has passed."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

WINDOWS_DEFAULT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
LAYOUTS = {"page": 3, "block": 6, "line": 7, "word": 8}  # Tesseract's page segmentation modes
SMALL_SIDE = 600  # an image shorter than this is enlarged first: Tesseract reads small type badly
ENLARGE = 3


class OcrError(RuntimeError):
    """A message safe to show the model: what went wrong and what to try."""


def candidate_locations() -> list[Path]:
    """Where Tesseract usually is when it is not on PATH. Per-user installs (no admin rights) go under the
    user's AppData or home folder rather than Program Files."""
    places = [
        WINDOWS_DEFAULT,
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Tesseract-OCR\tesseract.exe"),
    ]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        places += [
            Path(local) / "Programs" / "Tesseract-OCR" / "tesseract.exe",
            Path(local) / "Tesseract-OCR" / "tesseract.exe",
        ]
    places += [
        Path.home() / "scoop" / "apps" / "tesseract" / "current" / "tesseract.exe",
        Path.home() / "Tesseract-OCR" / "tesseract.exe",
    ]
    return places


def find_tesseract(configured: str | None = None) -> str | None:
    """`configured` is TESSERACT_CMD from the .env (a full path, or the folder holding tesseract.exe).
    It wins; then PATH; then the usual places."""
    chosen = (configured or "").strip().strip('"')
    if chosen:
        path = Path(chosen)
        path = path / "tesseract.exe" if path.is_dir() else path
        if path.exists():
            return str(path)
    found = shutil.which("tesseract")
    if found:
        return found
    return next((str(place) for place in candidate_locations() if place.exists()), None)


def _prepared(image: Image.Image) -> Image.Image:
    gray = image.convert("L")
    if min(gray.size) < SMALL_SIDE:
        gray = gray.resize((gray.width * ENLARGE, gray.height * ENLARGE), Image.Resampling.LANCZOS)
    return gray


def read_image(
    binary: str, image: Image.Image, language: str = "eng", layout: str = "page", timeout: float = 60.0
) -> str:
    """The text Tesseract reads in `image`. Raises OcrError when it cannot run or reports a failure."""
    if layout not in LAYOUTS:
        raise OcrError(f"layout must be one of {', '.join(LAYOUTS)}")
    if not language.replace("+", "").isalpha():
        raise OcrError("language must be Tesseract language codes such as 'eng' or 'eng+deu'")
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "page.png"
        _prepared(image).save(path)
        try:
            done = subprocess.run(
                [binary, str(path), "stdout", "-l", language, "--psm", str(LAYOUTS[layout])],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise OcrError(f"Tesseract took longer than {int(timeout)} seconds") from error
        except OSError as error:
            raise OcrError(f"Tesseract could not start: {error}") from error
    if done.returncode != 0:
        problem = (done.stderr or "").strip().splitlines()
        raise OcrError(
            "Tesseract failed: " + (problem[-1][:200] if problem else f"exit code {done.returncode}")
        )
    return done.stdout.strip()

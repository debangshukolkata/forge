"""A Word document as a PDF, made by Word itself or by LibreOffice (D-344), so the pages can be looked at and the file can be saved as PDF.
Windows with Word installed first; otherwise `soffice` when it is on the path. Paths go through environment variables, macros are force-disabled
and DebCraft's own variables are not passed on (D-202)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

from forge.toolkit.private_env import without_private

TIMEOUT_S = 180

WORD_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$wasRunning = [bool](Get-Process WINWORD -ErrorAction SilentlyContinue)
$app = New-Object -ComObject Word.Application
$app.Visible = $false
$app.DisplayAlerts = 0
$app.AutomationSecurity = 3  # force-disable macros: an untrusted document never runs code
try {
    $doc = $app.Documents.Open($env:DOC_FILE, $false, $true)
    try {
        $doc.Fields.Update() | Out-Null
        $doc.ExportAsFixedFormat($env:DOC_OUT, 17)
    } finally { $doc.Close(0) }
} finally { if (-not $wasRunning) { $app.Quit() } }
"""


class PreviewUnavailable(Exception):
    """Neither Word nor LibreOffice can be used here; the message says why."""


@lru_cache(maxsize=1)
def word_available() -> bool:
    if sys.platform != "win32":
        return False
    try:
        done = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "if ([type]::GetTypeFromProgID('Word.Application')) { exit 0 } else { exit 1 }",
            ],
            capture_output=True,
            timeout=30,
            check=False,
            env=without_private(os.environ),
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0


def libreoffice() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


def to_pdf(data: bytes, suffix: str = ".docx") -> bytes:
    """The document as PDF bytes."""
    with tempfile.TemporaryDirectory(prefix="debcraft-doc-") as folder:
        source = Path(folder) / f"in{suffix}"
        target = Path(folder) / "out.pdf"
        source.write_bytes(data)
        if word_available():
            environment = {**without_private(os.environ), "DOC_FILE": str(source), "DOC_OUT": str(target)}
            try:
                done = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", WORD_SCRIPT],
                    capture_output=True,
                    text=True,
                    timeout=TIMEOUT_S,
                    env=environment,
                    check=False,
                )
            except subprocess.TimeoutExpired as error:
                raise PreviewUnavailable(f"Word did not answer within {TIMEOUT_S} seconds.") from error
            if done.returncode == 0 and target.is_file():
                return target.read_bytes()
            reason = " ".join((done.stderr or done.stdout).strip().splitlines()[:2])[:300]
            raise PreviewUnavailable(f"Word could not export the document: {reason}")
        office = libreoffice()
        if office:
            try:
                subprocess.run(
                    [office, "--headless", "--convert-to", "pdf", "--outdir", folder, str(source)],
                    capture_output=True,
                    timeout=TIMEOUT_S,
                    check=False,
                    env=without_private(os.environ),
                )
            except subprocess.TimeoutExpired as error:
                raise PreviewUnavailable(f"LibreOffice did not answer within {TIMEOUT_S} seconds.") from error
            produced = Path(folder) / "in.pdf"
            if produced.is_file():
                return produced.read_bytes()
            raise PreviewUnavailable("LibreOffice could not convert the document.")
    raise PreviewUnavailable("Neither Microsoft Word nor LibreOffice is available on this computer.")

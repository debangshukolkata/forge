"""Converting a deck with PowerPoint itself (TODO P2.16, D-317): an old .ppt, .pps, .pot or .pptm to .pptx (so it can be read and edited),
and any deck to PDF. Windows with PowerPoint installed only, driven like the preview (PowerShell and COM, paths in environment
variables). The result is written next to a temporary folder and read back; the caller stores it through the workspace."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from forge.slides.powerpoint_lock import powerpoint_turn
from forge.slides.preview import PreviewUnavailable, available
from forge.toolkit.private_env import without_private

TIMEOUT_S = 240
FORMATS = {"pptx": 24, "pdf": 32}  # ppSaveAsOpenXMLPresentation, ppSaveAsPDF
OLD_FORMATS = {".ppt", ".pps", ".pot", ".pptm", ".ppsx", ".potx", ".odp"}

SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$wasRunning = [bool](Get-Process POWERPNT -ErrorAction SilentlyContinue)
$app = New-Object -ComObject PowerPoint.Application
try {
    $presentation = $app.Presentations.Open($env:DECK_FILE, -1, 0, 0)
    try { $presentation.SaveAs($env:DECK_OUT, [int]$env:DECK_FORMAT) }
    finally { $presentation.Close() }
} finally {
    if (-not $wasRunning) { $app.Quit() }
}
"""


def convert_deck(source: Path, kind: str) -> bytes:
    """The bytes of `source` saved as `kind` ('pptx' or 'pdf') by PowerPoint."""
    if kind not in FORMATS:
        raise PreviewUnavailable(f"cannot convert to {kind!r}: choose pptx or pdf")
    if not available():
        raise PreviewUnavailable("PowerPoint is not installed on this computer (or this is not Windows).")
    with tempfile.TemporaryDirectory(prefix="forge-convert-") as folder:
        target = Path(folder) / f"converted.{kind}"
        environment = {
            **without_private(os.environ),
            "DECK_FILE": str(source.resolve()),
            "DECK_OUT": str(target),
            "DECK_FORMAT": str(FORMATS[kind]),
        }
        try:
            with powerpoint_turn():
                done = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", SCRIPT],
                    capture_output=True,
                    text=True,
                    timeout=TIMEOUT_S,
                    env=environment,
                    check=False,
                )
        except subprocess.TimeoutExpired as error:
            raise PreviewUnavailable(f"PowerPoint did not answer within {TIMEOUT_S} seconds.") from error
        if done.returncode != 0 or not target.is_file():
            reason = (done.stderr or done.stdout).strip().splitlines()[:2]
            raise PreviewUnavailable("PowerPoint could not convert the file: " + " ".join(reason)[:300])
        return target.read_bytes()

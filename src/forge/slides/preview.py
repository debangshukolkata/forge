"""Pictures of the slides, made by PowerPoint itself (D-240), so the model can look at what it built and
fix it. Windows with PowerPoint installed only; anywhere else the caller gets a plain "not available" and
goes on with the layout warnings. PowerPoint is driven through PowerShell and COM, with the paths passed
as environment variables so no file name can become part of a command."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from forge.toolkit.private_env import without_private

TIMEOUT_S = 180
WIDTH, HEIGHT = 1600, 900

# Closes PowerPoint afterwards only when this script started it: the user's own open decks stay open.
SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$wasRunning = [bool](Get-Process POWERPNT -ErrorAction SilentlyContinue)
$app = New-Object -ComObject PowerPoint.Application
try {
    $presentation = $app.Presentations.Open($env:DECK_FILE, -1, 0, 0)
    try { $presentation.Export($env:DECK_OUT, 'PNG', [int]$env:DECK_W, [int]$env:DECK_H) }
    finally { $presentation.Close() }
} finally {
    if (-not $wasRunning) { $app.Quit() }
}
"""


class PreviewUnavailable(Exception):
    """PowerPoint cannot be used here; the message says why."""


def available() -> bool:
    if sys.platform != "win32":
        return False
    done = subprocess.run(
        ["reg", "query", r"HKCR\PowerPoint.Application"], capture_output=True, text=True, check=False
    )
    return done.returncode == 0


def export_slides(deck: Path, folder: Path) -> list[Path]:
    """PNG pictures of every slide of `deck`, written into `folder` as slide-1.png, slide-2.png, ..."""
    if not available():
        raise PreviewUnavailable("PowerPoint is not installed on this computer (or this is not Windows).")
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.png"):
        old.unlink()
    environment = {
        **without_private(os.environ),  # the usual Windows variables for PowerShell, none of Forge's (D-202)
        "DECK_FILE": str(deck.resolve()),
        "DECK_OUT": str(folder.resolve()),
        "DECK_W": str(WIDTH),
        "DECK_H": str(HEIGHT),
    }
    try:
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
    pictures = [p for p in folder.iterdir() if p.suffix.lower() == ".png"]
    if done.returncode != 0 or not pictures:
        reason = (done.stderr or done.stdout).strip().splitlines()[:2]
        raise PreviewUnavailable("PowerPoint could not export the slides: " + " ".join(reason)[:300])
    numbered: dict[int, Path] = {}
    for picture in pictures:
        number = int("".join(c for c in picture.stem if c.isdigit()) or 0)
        target = folder / f"slide-{number}.png"
        picture.replace(target)  # PowerPoint names them Slide1.PNG, Slide2.PNG, ...
        numbered[number] = target
    return [numbered[n] for n in sorted(numbered)]

"""Have Excel itself calculate a workbook and report the cells that show errors (D-339). Windows with Excel installed only; anywhere
else the caller gets `ExcelUnavailable` and uses the static check. Paths go through environment variables, macros are force-disabled
and DebCraft's own variables are not passed on (D-202)."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

from forge.toolkit.private_env import without_private

TIMEOUT_S = 120

SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$app = New-Object -ComObject Excel.Application
$app.Visible = $false
$app.DisplayAlerts = $false
$app.AutomationSecurity = 3  # force-disable macros: an untrusted workbook never runs code
try {
    $book = $app.Workbooks.Open($env:BOOK_FILE, 0, $false)
    try {
        $app.CalculateFull()
        foreach ($sheet in $book.Worksheets) {
            try { $errors = $sheet.UsedRange.SpecialCells(-4123, 16) } catch { continue }
            foreach ($cell in $errors.Cells) { Write-Output ("ERR|" + $sheet.Name + "|" + $cell.Address($false, $false) + "|" + $cell.Text) }
        }
        if ($env:BOOK_SAVE_AS) { $book.SaveAs($env:BOOK_SAVE_AS, 51) }
    } finally { $book.Close($false) }
} finally { $app.Quit() }
"""


class ExcelUnavailable(Exception):
    """Excel cannot be used here; the message says why."""


@lru_cache(maxsize=1)
def available() -> bool:
    if sys.platform != "win32":
        return False
    try:
        done = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "if ([type]::GetTypeFromProgID('Excel.Application')) { exit 0 } else { exit 1 }",
            ],
            capture_output=True,
            timeout=30,
            check=False,
            env=without_private(os.environ),
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0


def recalculate(data: bytes) -> tuple[list[tuple[str, str, str]], bytes | None]:
    """(cells showing an error as (sheet, cell, text), the workbook as calculated and saved by Excel)."""
    if not available():
        raise ExcelUnavailable("Excel is not installed on this computer (or this is not Windows).")
    with tempfile.TemporaryDirectory(prefix="debcraft-xlsx-") as folder:
        source = Path(folder) / "in.xlsx"
        saved = Path(folder) / "out.xlsx"
        source.write_bytes(data)
        environment = {**without_private(os.environ), "BOOK_FILE": str(source), "BOOK_SAVE_AS": str(saved)}
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
            raise ExcelUnavailable(f"Excel did not answer within {TIMEOUT_S} seconds.") from error
        if done.returncode != 0:
            reason = (done.stderr or done.stdout).strip().splitlines()[:2]
            raise ExcelUnavailable("Excel could not calculate the workbook: " + " ".join(reason)[:300])
        errors = []
        for line in done.stdout.splitlines():
            parts = line.strip().split("|")
            if len(parts) == 4 and parts[0] == "ERR":
                errors.append((parts[1], parts[2], parts[3]))
        return errors, saved.read_bytes() if saved.is_file() else None


PDF_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$app = New-Object -ComObject Excel.Application
$app.Visible = $false
$app.DisplayAlerts = $false
$app.AutomationSecurity = 3  # force-disable macros: an untrusted workbook never runs code
try {
    $book = $app.Workbooks.Open($env:BOOK_FILE, 0, $true)
    try { $app.CalculateFull(); $book.ExportAsFixedFormat(0, $env:BOOK_PDF) } finally { $book.Close($false) }
} finally { $app.Quit() }
"""


def to_pdf(data: bytes) -> bytes:
    """The workbook as PDF bytes, printed by Excel (every sheet, its own page setup), so the pages can be looked at."""
    if not available():
        raise ExcelUnavailable("Excel is not installed on this computer (or this is not Windows).")
    with tempfile.TemporaryDirectory(prefix="debcraft-xlsx-") as folder:
        source, target = Path(folder) / "in.xlsx", Path(folder) / "out.pdf"
        source.write_bytes(data)
        environment = {**without_private(os.environ), "BOOK_FILE": str(source), "BOOK_PDF": str(target)}
        try:
            done = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", PDF_SCRIPT],
                capture_output=True,
                text=True,
                timeout=TIMEOUT_S,
                env=environment,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise ExcelUnavailable(f"Excel did not answer within {TIMEOUT_S} seconds.") from error
        if done.returncode != 0 or not target.is_file():
            reason = " ".join((done.stderr or done.stdout).strip().splitlines()[:2])[:300]
            raise ExcelUnavailable(f"Excel could not print the workbook: {reason}")
        return target.read_bytes()

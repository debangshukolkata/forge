"""A guided script for steps only the human can do (TODO C21, D-310). When `request_user_action` has several steps, DebCraft also writes a
small PowerShell script that walks the user through them one at a time: it shows each step, waits, and offers to run the check command
(after showing it) so the result is verified, then saves a short result file. It prints no secrets and stores none: step text and the check
command pass through the redactor, and the script never reads or prints environment variables or files by itself. Safety invariant 6:
hand over what DebCraft cannot or must not do, in a form the user can actually follow."""

from __future__ import annotations

import re
from pathlib import Path

from forge.safety.redact import default_redactor

MIN_STEPS = 3  # shorter lists are fine as a card; a script helps with a longer walk-through
FOLDER = ".forge/handoff"


def slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40] or "action"


def _block(text: str) -> str:
    """Text for a single-quoted here-string: nothing in it can end the string early."""
    return default_redactor.redact(text).replace("\r", "").replace("\n'@", "\n' @").replace("'@", "' @")


def build_script(title: str, steps: list[str], verify_command: str | None) -> str:
    safe_title = _block(title).replace('"', "'").replace("\n", " ")
    lines = [
        f"# Guided steps from DebCraft: {safe_title}",
        "# It shows each step, waits for you, and (if there is one) offers to run the check after showing it.",
        "# It prints no secrets and stores none; the result goes to a small text file next to this script.",
        "$ErrorActionPreference = 'Continue'",
        "$results = @()",
        f'Write-Host "{safe_title}" -ForegroundColor Cyan',
    ]
    total = len(steps)
    for number, step in enumerate(steps, start=1):
        lines += [
            'Write-Host ""',
            f'Write-Host "Step {number} of {total}" -ForegroundColor Cyan',
            "Write-Host @'",
            _block(step),
            "'@",
            '$answer = Read-Host "Enter when done, s to skip, c if you cannot do it"',
            f"$results += 'Step {number}: ' + $(if ($answer -eq 's') {{ 'skipped' }} elseif ($answer -eq 'c') {{ 'cannot' }} else {{ 'done' }})",
        ]
    if verify_command:
        lines += [
            'Write-Host ""',
            'Write-Host "DebCraft would like to check the result with this command:" -ForegroundColor Cyan',
            "Write-Host @'",
            _block(verify_command),
            "'@",
            '$run = Read-Host "Run the check? (Enter = yes, n = no)"',
            "if ($run -ne 'n') {",
            "  try {",
            "    $output = Invoke-Expression @'",
            _block(verify_command),
            "'@ 2>&1 | Out-String",
            "    Write-Host $output",
            "    $results += 'Check: ran (see the output above)'",
            "  } catch {",
            '    Write-Host "The check failed to run: $($_.Exception.Message)" -ForegroundColor Yellow',
            "    $results += 'Check: failed to run'",
            "  }",
            "} else { $results += 'Check: not run' }",
        ]
    name = slug(title)
    lines += [
        'Write-Host ""',
        f"$file = Join-Path $PSScriptRoot '{name}-result.txt'",
        "$results | Set-Content -Path $file -Encoding UTF8",
        'Write-Host "Done. Answer done / skip / can\'t in the DebCraft card; a short summary is in $file" -ForegroundColor Green',
    ]
    return "\r\n".join(lines) + "\r\n"


def write_script(forge_dir: Path, title: str, steps: list[str], verify_command: str | None) -> str | None:
    """Writes the script under `.forge/handoff/` and returns its path relative to the workspace root; None when the list is short."""
    if len(steps) < MIN_STEPS:
        return None
    target = forge_dir / "handoff" / f"{slug(title)}.ps1"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        build_script(title, steps, verify_command), encoding="utf-8-sig"
    )  # a BOM so PowerShell 5.1 reads UTF-8
    return f"{FOLDER}/{target.name}"

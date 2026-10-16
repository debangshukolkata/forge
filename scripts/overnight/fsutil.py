"""Removing an old run folder for real.

`shutil.rmtree(path, ignore_errors=True)` leaves the files it cannot delete and says nothing; on Windows that is every read-only file (git objects, caches) and every file a program still holds. The second run of a job
then found the first run's `.forge` folder and refused to start ("workspace already has .forge", office laptop, 2026-10-16, D-450). `remove_tree` clears the read-only flag and retries; a folder that still
cannot be deleted is renamed out of the way, so the job always starts on an empty folder."""

from __future__ import annotations

import contextlib
import os
import shutil
import stat
import sys
import time
from pathlib import Path
from typing import Any


def _clear_read_only(function: Any, path: str, _error: object) -> None:
    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    function(path)


def remove_tree(path: Path) -> None:
    """Delete the folder, or move it aside as `<name>.stale-<time>` when it cannot be deleted. Raises only if both fail."""
    if not path.exists():
        return
    for _attempt in range(3):  # a program that has just exited may hold a file for a moment
        with contextlib.suppress(OSError):
            if sys.version_info >= (3, 12):
                shutil.rmtree(path, onexc=_clear_read_only)
            else:
                shutil.rmtree(path, onerror=_clear_read_only)
        if not path.exists():
            return
        time.sleep(2)
    aside = path.with_name(f"{path.name}.stale-{time.strftime('%H%M%S')}")
    path.rename(aside)  # a folder that cannot even be renamed is a real problem: let it show

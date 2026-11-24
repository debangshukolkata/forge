"""SQLite: one file beside the package (or RECQA_DB)."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def connect() -> sqlite3.Connection:
    path = os.environ.get("RECQA_DB") or str(Path(__file__).resolve().parent.parent / "recqa.db")
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection

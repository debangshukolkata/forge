"""The target laptop is offline, so the o200k_base encoding must load from the package (D-015)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import forge

VENDORED_DIR = Path(forge.__file__).parent / "data" / "tiktoken"


def test_encoding_file_is_vendored() -> None:
    files = list(VENDORED_DIR.iterdir())
    assert any(f.stat().st_size > 1_000_000 for f in files)


def test_encoding_loads_with_network_blocked() -> None:
    env = dict(os.environ)
    env["TIKTOKEN_CACHE_DIR"] = str(VENDORED_DIR)
    # An unreachable proxy makes any download attempt fail fast.
    env["HTTP_PROXY"] = env["HTTPS_PROXY"] = "http://127.0.0.1:9"
    code = "import tiktoken; print(len(tiktoken.get_encoding('o200k_base').encode('hello world')))"

    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "2"

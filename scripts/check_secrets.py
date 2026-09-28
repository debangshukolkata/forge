"""Scan files for leaked secrets (DECISIONS D-016).

Checks two things:
1. The exact values of secrets in `.env` (keys named *KEY*, *SECRET*, *PASSWORD*, *TOKEN*, and
   passwords embedded in *_URL connection strings) appearing in any scanned file.
2. Generic secret shapes: JWTs, connection strings with passwords, private key blocks.

Never prints a secret value — only file:line and the rule that matched.
Usage: python scripts/check_secrets.py [extra paths to scan...]
Exit code 0 = clean, 1 = findings.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MIN_SECRET_LENGTH = 8
SECRET_NAME = re.compile(r"(KEY|SECRET|PASSWORD|TOKEN)", re.IGNORECASE)
URL_PASSWORD = re.compile(r"://[^:/\s@]+:([^@\s]+)@")

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "tiktoken",
    "test-artifacts",  # local live-run evidence (gitignored); holds captured test output
}
SKIP_FILE_PREFIXES = (".env",)
# Fixture files hold deliberately fake credentials so Forge's secret handling can be tested.
# Lines carrying the marker comment "check_secrets: fake" hold deliberately fake test values.
FAKE_MARKERS = (
    "fixture-not-a-real",
    "not-real",
    "example-password",
    "test-jwt-secret",
    "check_secrets: fake",
)

PATTERNS = {
    "jwt": re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "connection-string-password": URL_PASSWORD,
    "private-key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}


def is_placeholder(match: re.Match[str]) -> bool:
    """`postgresql://user:<password>@host` in docs is not a leak."""
    captured = match.group(1) if match.groups() else ""
    # Regex source code (e.g. the redaction patterns themselves) is not a credential either.
    return captured.startswith(("<", "{", "$", "*")) or any(char in captured for char in r"[]\()")


def load_secret_values(env_file: Path) -> dict[str, str]:
    """Returns {variable name: secret value} for values worth scanning for."""
    secrets: dict[str, str] = {}
    if not env_file.exists():
        return secrets
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = (part.strip() for part in line.split("=", 1))
        value = value.strip("'\"")
        if SECRET_NAME.search(name) and len(value) >= MIN_SECRET_LENGTH:
            secrets[name] = value
        url_password = URL_PASSWORD.search(value)
        if url_password and len(url_password.group(1)) >= MIN_SECRET_LENGTH:
            secrets[f"{name} (password)"] = url_password.group(1)
    return secrets


def iter_text_files(root: Path) -> Iterator[Path]:
    for path in root.rglob("*"):
        if any(
            part in SKIP_DIRS or part.startswith(".venv") or part == "site-packages" for part in path.parts
        ):
            continue
        if not path.is_file() or path.name.startswith(SKIP_FILE_PREFIXES):
            continue
        yield path


def scan_file(path: Path, secrets: dict[str, str]) -> Iterator[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return
    for line_number, line in enumerate(text.splitlines(), start=1):
        for name, value in secrets.items():
            if value in line:
                yield f"{path}:{line_number}: value of {name}"
        if any(marker in line for marker in FAKE_MARKERS):
            continue
        for rule, pattern in PATTERNS.items():
            match = pattern.search(line)
            if match and not is_placeholder(match):
                yield f"{path}:{line_number}: {rule}"


def find_leaks(scan_roots: list[Path], env_file: Path) -> list[str]:
    secrets = load_secret_values(env_file)
    findings: list[str] = []
    for root in scan_roots:
        files = [root] if root.is_file() else iter_text_files(root)
        for path in files:
            findings.extend(scan_file(path, secrets))
    return findings


def main(argv: list[str]) -> int:
    scan_roots = [REPO_ROOT, *(Path(arg) for arg in argv)]
    findings = find_leaks(scan_roots, REPO_ROOT / ".env")
    for finding in findings:
        print(finding)
    print(f"check_secrets: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

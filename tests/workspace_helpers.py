"""Builds a realistic 'original repository' for workspace tests: the fixture repo plus awkward files."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from forge.safety.paths import os_path
from tests.conftest import FIXTURE_REPO

CRLF_FILE = "backend/claims_app/legacy_crlf.py"
BOM_FILE = "backend/claims_app/bom_utf8.py"
CP1252_FILE = "backend/docs_cp1252.txt"
BIG_FILE = "backend/data/big.bin"
LONG_DIR_PARTS = ["very_long_directory_name_for_testing_windows_limits_" + str(i) for i in range(5)]


def long_file_relative() -> str:
    return "/".join(["backend", *LONG_DIR_PARTS, "deep_module.py"])


def copy_fixture(destination: Path) -> Path:
    shutil.copytree(
        FIXTURE_REPO,
        destination,
        ignore=shutil.ignore_patterns("venv", "__pycache__", ".pytest_cache", "*.db"),
    )
    return destination


def add_awkward_files(repo: Path) -> None:
    (repo / CRLF_FILE).write_bytes(b'"""Old module."""\r\n\r\nVALUE = 1\r\n')
    (repo / BOM_FILE).write_bytes(b'\xef\xbb\xbf"""BOM module."""\nNAME = "claims"\n')
    (repo / CP1252_FILE).write_bytes(b"Caf\xe9 claims guide\nSecond line\n")
    (repo / "backend/data").mkdir()
    (repo / BIG_FILE).write_bytes(b"\x00" * (2 * 1024 * 1024))
    (repo / "backend/logs").mkdir()
    (repo / "backend/logs/app.log").write_text("log line\n", encoding="utf-8")
    (repo / "backend/claims.db").write_bytes(b"sqlite")  # ignored by backend/.gitignore (*.db)
    (repo / ".gitignore").write_text("*.tmp\n", encoding="utf-8")  # applies to backend/ from above
    (repo / "backend/notes.tmp").write_text("scratch\n", encoding="utf-8")
    long_file = repo / long_file_relative()
    os.makedirs(os_path(long_file.parent, force=True), exist_ok=True)
    with open(os_path(long_file, force=True), "w", encoding="utf-8") as handle:
        handle.write("DEEP = True\n")


def create_venv(app_dir: Path) -> Path:
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(app_dir / "venv")], check=True)
    return app_dir / "venv"


def make_junction(link: Path, target: Path) -> bool:
    """Directory junction on Windows (no admin needed), symlink elsewhere. False if not possible."""
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True
            )
            return result.returncode == 0
        link.symlink_to(target, target_is_directory=True)
        return True
    except OSError:
        return False


def build_original_repo(destination: Path, outside_dir: Path) -> Path:
    repo = copy_fixture(destination)
    add_awkward_files(repo)
    create_venv(repo / "backend")
    outside_dir.mkdir(parents=True, exist_ok=True)
    (outside_dir / "secret.txt").write_text("outside the repository\n", encoding="utf-8")
    make_junction(repo / "backend" / "linked_outside", outside_dir)
    return repo


def site_packages(venv: Path) -> Path:
    if sys.platform == "win32":
        return venv / "Lib" / "site-packages"
    return next((venv / "lib").glob("python3*/site-packages"))


def tree_bytes(root: Path, skip: set[str]) -> dict[str, bytes]:
    """Every file under root (repo-relative POSIX path -> bytes), skipping directories named in skip."""
    files = {}
    for directory, subdirectories, filenames in os.walk(os_path(root, force=True)):
        subdirectories[:] = [d for d in subdirectories if d not in skip]
        for name in filenames:
            full = os.path.join(directory, name)
            relative = Path(os.path.relpath(full, os_path(root, force=True))).as_posix()
            with open(full, "rb") as handle:
                files[relative] = handle.read()
    return files

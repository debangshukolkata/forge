"""Copies the app folder of the user's repository into the workspace and records the baseline."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from pathlib import Path

from pydantic import BaseModel, Field

from forge.safety.paths import WriteJail, os_path
from forge.workspace.ignore import IgnoreRules
from forge.workspace.manifest import BaselineManifest, ManifestEntry, sha256_of
from forge.workspace.text_format import detect_format

ProgressCallback = Callable[[int, str], None]  # (files copied so far, current relative path)


class CopyReport(BaseModel):
    files: int = 0
    bytes: int = 0
    skipped_large: list[str] = Field(default_factory=list)
    skipped_links: list[str] = Field(default_factory=list)
    secret_files: list[str] = Field(default_factory=list)


def iter_source_files(
    repo_root: Path, app_subfolder: str, rules: IgnoreRules
) -> Iterator[tuple[str, Path, bool]]:
    """Yields (repo-relative POSIX path, source path, is_link) for every file that should be copied."""
    walk_root = os_path(repo_root / app_subfolder, force=True)
    prefix = os_path(repo_root, force=True)
    for directory, subdirectories, filenames in os.walk(walk_root, topdown=True, followlinks=False):
        relative_dir = Path(os.path.relpath(directory, prefix)).as_posix()
        kept = []
        for name in sorted(subdirectories):
            full = os.path.join(directory, name)
            relative = f"{relative_dir}/{name}"
            if _is_link(full):
                yield relative, Path(full), True
            elif not rules.is_ignored(relative, is_dir=True):
                kept.append(name)
        subdirectories[:] = kept  # prune ignored directories so os.walk never enters them
        for name in sorted(filenames):
            relative = f"{relative_dir}/{name}"
            if rules.is_ignored(relative, is_dir=False):
                continue
            full = os.path.join(directory, name)
            yield relative, Path(full), _is_link(full)


def copy_app_folder(
    repo_root: Path,
    app_subfolder: str,
    destination_root: Path,
    rules: IgnoreRules,
    jail: WriteJail,
    max_file_bytes: int,
    on_progress: ProgressCallback | None = None,
) -> tuple[CopyReport, BaselineManifest]:
    report = CopyReport()
    manifest = BaselineManifest.empty()
    for relative, source, is_link in iter_source_files(repo_root, app_subfolder, rules):
        if is_link:
            # A link could point anywhere (even outside the repo); the user copies such files by hand.
            report.skipped_links.append(relative)
            continue
        size = os.path.getsize(source)
        if size > max_file_bytes:
            report.skipped_large.append(relative)
            continue
        data = Path(source).read_bytes()
        target = jail.check(destination_root / relative)
        os.makedirs(os_path(target.parent, force=True), exist_ok=True)
        with open(os_path(target), "wb") as handle:
            handle.write(data)
        mtime = os.path.getmtime(source)
        os.utime(os_path(target), (mtime, mtime))
        secret = rules.is_secret(relative)
        if secret:
            report.secret_files.append(relative)
        manifest.files[relative] = ManifestEntry(
            sha256=sha256_of(data), size=len(data), mtime=mtime, format=detect_format(data), secret=secret
        )
        report.files += 1
        report.bytes += len(data)
        if on_progress is not None:
            on_progress(report.files, relative)
    return report, manifest


def _is_link(path: str) -> bool:
    isjunction = getattr(os.path, "isjunction", None)  # Python 3.12+
    return os.path.islink(path) or bool(isjunction and isjunction(path))

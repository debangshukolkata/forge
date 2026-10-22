"""Archive tool (D-461): `archive` (list or extract) for .zip, .tar, .tar.gz/.tgz, .tar.bz2 and .tar.xz.

An uploaded archive lands in .forge/inputs/ like any attachment. These tools open it without a shell: every
entry name is checked (no absolute paths, no `..`, no drive letters, no links), the number of entries and the
real number of bytes written are capped (a zip bomb lies about its sizes, so the bytes are counted as they are
copied), secret files are skipped, and everything is written through the workspace jail.
"""

from __future__ import annotations

import asyncio
import re
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import IO, Literal

from pydantic import Field

from forge.errors import ForgeError
from forge.safety.paths import real_path
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools.vision import image_path

ARCHIVE_SUFFIXES = (".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz")
MAX_ARCHIVE_BYTES = 200 * 1024 * 1024
MAX_ENTRIES = 5000
MAX_TOTAL_BYTES = 1024 * 1024 * 1024
MAX_FILE_BYTES = 300 * 1024 * 1024
LISTED_LIMIT = 200
CHUNK = 1024 * 1024
WINDOWS_RESERVED = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$", re.IGNORECASE)
WINDOWS_BAD_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')


class ArchiveError(ForgeError):
    """An archive that cannot be opened or that is not safe to unpack."""


def is_archive_name(name: str) -> bool:
    return name.lower().endswith(ARCHIVE_SUFFIXES)


@dataclass
class Entry:
    name: str  # cleaned relative path, forward slashes
    size: int
    is_dir: bool
    problem: str = ""  # non-empty: the entry is skipped, and this says why


def clean_entry_name(raw: str) -> str:
    """The safe relative form of an entry name, or ArchiveError. Rejects every way out of the target folder."""
    name = raw.replace("\\", "/")
    if not name or name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        raise ArchiveError(f"absolute path in archive: {raw!r}")
    parts = [part for part in PurePosixPath(name).parts if part not in ("", ".")]
    if not parts or ".." in parts:
        raise ArchiveError(f"path leaves the folder: {raw!r}")
    for part in parts:
        if WINDOWS_BAD_CHARS.search(part) or WINDOWS_RESERVED.match(part) or part.endswith((" ", ".")):
            raise ArchiveError(f"name not allowed on Windows: {raw!r}")
    return "/".join(parts)


class _Reader:
    """One interface over zip and tar so listing and extraction are written once."""

    def __init__(self, path: Path, password: str) -> None:
        self._password = password.encode("utf-8") if password else None
        self._zip: zipfile.ZipFile | None = None
        self._tar: tarfile.TarFile | None = None
        try:
            if zipfile.is_zipfile(path):
                self._zip = zipfile.ZipFile(path)
            elif is_archive_name(path.name) and not path.name.lower().endswith(".zip"):
                self._tar = tarfile.open(path)  # noqa: SIM115 - closed in close()
            else:
                raise ArchiveError(f"{path.name} is not a zip or tar archive.")
        except (zipfile.BadZipFile, tarfile.TarError, OSError, EOFError) as error:
            raise ArchiveError(f"{path.name} could not be opened: {error}") from error

    def close(self) -> None:
        if self._zip:
            self._zip.close()
        if self._tar:
            self._tar.close()

    def entries(self) -> list[Entry]:
        found: list[Entry] = []
        if self._zip:
            for info in self._zip.infolist():
                found.append(
                    self._classify(info.filename, info.file_size, info.is_dir(), self._zip_problem(info))
                )
        elif self._tar:
            for member in self._tar.getmembers():
                problem = ""
                if member.issym() or member.islnk():
                    problem = "link (skipped)"
                elif not (member.isfile() or member.isdir()):
                    problem = "special file (skipped)"
                found.append(self._classify(member.name, member.size, member.isdir(), problem))
        return found

    @staticmethod
    def _zip_problem(info: zipfile.ZipInfo) -> str:
        mode = info.external_attr >> 16
        if (mode & 0o170000) == 0o120000:
            return "link (skipped)"
        return ""

    @staticmethod
    def _classify(raw: str, size: int, is_dir: bool, problem: str) -> Entry:
        try:
            return Entry(clean_entry_name(raw), size, is_dir, problem)
        except ArchiveError as error:
            return Entry(raw, size, is_dir, f"unsafe, skipped: {error}")

    def open_entry(self, raw_name: str) -> IO[bytes]:
        if self._zip:
            try:
                return self._zip.open(raw_name, pwd=self._password)
            except RuntimeError as error:  # zipfile reports a missing or wrong password this way
                raise ArchiveError(f"{raw_name}: {error}. Ask the user for the password.") from error
            except NotImplementedError as error:
                raise ArchiveError(f"{raw_name}: this encryption or compression is not supported.") from error
        assert self._tar is not None
        stream = self._tar.extractfile(raw_name)
        if stream is None:
            raise ArchiveError(f"{raw_name} cannot be read.")
        return stream

    def raw_names(self) -> list[str]:
        if self._zip:
            return [info.filename for info in self._zip.infolist()]
        assert self._tar is not None
        return [member.name for member in self._tar.getmembers()]


def describe_entries(entries: list[Entry], limit: int = LISTED_LIMIT) -> str:
    files = [entry for entry in entries if not entry.is_dir]
    total = sum(entry.size for entry in files)
    lines = [f"{len(files)} file(s), {total:,} bytes unpacked."]
    for entry in entries[:limit]:
        marker = "/" if entry.is_dir else ""
        note = f"  <- {entry.problem}" if entry.problem else ""
        lines.append(f"  {entry.name}{marker}" + ("" if entry.is_dir else f"  ({entry.size:,} bytes)") + note)
    if len(entries) > limit:
        lines.append(f"  ... and {len(entries) - limit} more")
    return "\n".join(lines)


def _open_archive(context: ToolContext, path: str, password: str) -> tuple[_Reader, Path]:
    file = image_path(context, path)
    if not file.is_file():
        raise ArchiveError(f"No file at {path}.")
    if file.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ArchiveError(f"{path} is larger than {MAX_ARCHIVE_BYTES // (1024 * 1024)} MB.")
    return _Reader(file, password), file


def list_entries(context: ToolContext, path: str, password: str = "") -> list[Entry]:
    reader, _ = _open_archive(context, path, password)
    try:
        return reader.entries()
    finally:
        reader.close()


def _default_destination(archive: Path) -> str:
    stem = archive.name
    for suffix in sorted(ARCHIVE_SUFFIXES, key=len, reverse=True):
        if stem.lower().endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-.") or "archive"
    return f".forge/inputs/{clean}"


def _destination_folder(context: ToolContext, destination: str) -> Path:
    normalised = destination.replace("\\", "/").strip("/")
    if not normalised or ".." in normalised.split("/"):
        raise ArchiveError(f"Destination {destination!r} must be a folder inside the workspace.")
    if normalised.startswith(".forge/"):
        if normalised.split("/")[1] not in ("inputs", "scratch_images"):
            raise ArchiveError("Inside .forge/ only inputs/ and scratch_images/ can be used.")
        return context.workspace.jail.check(context.workspace.root / normalised)
    return context.workspace.jail.check(context.workspace.path_of(normalised))


def extract(
    context: ToolContext, path: str, destination: str, password: str = ""
) -> tuple[list[str], list[str]]:
    """Unpacks into destination; returns (written relative paths, skipped notes). Raises ArchiveError on a hard limit."""
    reader, archive = _open_archive(context, path, password)
    try:
        entries = reader.entries()
        if len(entries) > MAX_ENTRIES:
            raise ArchiveError(f"{len(entries)} entries; the limit is {MAX_ENTRIES}.")
        if sum(entry.size for entry in entries if not entry.is_dir) > MAX_TOTAL_BYTES:
            raise ArchiveError(f"Unpacked size is over {MAX_TOTAL_BYTES // (1024 * 1024)} MB.")
        target_root = _destination_folder(context, destination or _default_destination(archive))
        target_root.mkdir(parents=True, exist_ok=True)
        written: list[str] = []
        skipped: list[str] = []
        total = 0
        raw_names = reader.raw_names()
        for entry, raw in zip(entries, raw_names, strict=True):
            if entry.problem:
                skipped.append(f"{entry.name}: {entry.problem}")
                continue
            target = context.workspace.jail.check(target_root / entry.name)
            if entry.is_dir:
                target.mkdir(parents=True, exist_ok=True)
                continue
            inside_forge = target_root.is_relative_to(real_path(context.workspace.forge_dir))
            base = real_path(context.workspace.root if inside_forge else context.workspace.repo_dir)
            relative = target.relative_to(base).as_posix()  # the form write_bytes and the readers expect
            if context.workspace.is_secret(relative if not inside_forge else entry.name):
                skipped.append(f"{entry.name}: secret file (skipped)")
                continue
            limit = min(MAX_FILE_BYTES, MAX_TOTAL_BYTES - total)
            if inside_forge:
                target.parent.mkdir(parents=True, exist_ok=True)
                total += _copy_limited(reader, raw, target, limit)
            else:  # delivered work: the normal write gate (baseline, checkpoint, change log)
                data = _read_limited(reader, raw, limit)
                context.workspace.write_bytes(relative, data, f"unpacked from {path}")
                total += len(data)
            written.append(relative)
        return written, skipped
    finally:
        reader.close()


def _read_limited(reader: _Reader, raw_name: str, limit: int) -> bytes:
    pieces: list[bytes] = []
    copied = 0
    try:
        with reader.open_entry(raw_name) as source:
            while chunk := source.read(CHUNK):
                copied += len(chunk)
                if copied > limit:
                    raise ArchiveError(f"{raw_name} unpacks to more than the size limit; stopped.")
                pieces.append(chunk)
    except (OSError, EOFError, zipfile.BadZipFile, tarfile.TarError) as error:
        raise ArchiveError(f"{raw_name} could not be unpacked: {error}") from error
    return b"".join(pieces)


def _copy_limited(reader: _Reader, raw_name: str, target: Path, limit: int) -> int:
    """Copies one entry counting real bytes, so an entry that lies about its size still hits the cap."""
    copied = 0
    try:
        with reader.open_entry(raw_name) as source, target.open("wb") as sink:
            while chunk := source.read(CHUNK):
                copied += len(chunk)
                if copied > limit:
                    raise ArchiveError(f"{raw_name} unpacks to more than the size limit; stopped.")
                sink.write(chunk)
    except ArchiveError:
        target.unlink(missing_ok=True)
        raise
    except (OSError, EOFError, zipfile.BadZipFile, tarfile.TarError) as error:
        target.unlink(missing_ok=True)
        raise ArchiveError(f"{raw_name} could not be unpacked: {error}") from error
    return copied


class Archive(Tool):
    name = "archive"
    read_only = False
    description = (
        "Open a .zip, .tar, .tar.gz/.tgz, .tar.bz2 or .tar.xz file (an uploaded attachment such as "
        "@.forge/inputs/<file>, or a file in the workspace). action=list shows names, sizes and the entries that would "
        "be skipped as unsafe, without unpacking: do this first. action=extract unpacks into .forge/inputs/<archive name>/ "
        "by default, where read_pdf, read_document, read_file and the other readers can open the files; give `destination` "
        "(a folder inside the workspace) to put them elsewhere, for example when they are to become part of the delivered "
        "work. Unsafe paths, links and secret files are skipped and reported; size and entry-count limits apply."
    )

    class Args(ToolArgs):
        action: Literal["list", "extract"]
        path: str = Field(description="The archive, e.g. .forge/inputs/<file>.zip")
        destination: str = Field(
            default="",
            description="extract only: workspace folder to unpack into; empty = .forge/inputs/<archive name>",
        )
        password: str = Field(default="", description="Only a password the user gave for this file")

    def summary(self, args: Archive.Args) -> str:
        return f"{args.action} archive {args.path}"

    async def run(self, args: Archive.Args, context: ToolContext) -> ToolResult:
        try:
            if args.action == "list":
                entries = await asyncio.to_thread(list_entries, context, args.path, args.password)
                return ToolResult(ok=True, content=describe_entries(entries))
            written, skipped = await asyncio.to_thread(
                extract, context, args.path, args.destination, args.password
            )
        except (ForgeError, OSError) as error:
            return ToolResult(ok=False, content=str(error))
        if args.destination and not args.destination.replace("\\", "/").startswith(".forge/"):
            context.last_edit_step = context.step
        lines = [f"Unpacked {len(written)} file(s)."]
        lines += [f"  {name}" for name in written[:LISTED_LIMIT]]
        if len(written) > LISTED_LIMIT:
            lines.append(f"  ... and {len(written) - LISTED_LIMIT} more")
        if skipped:
            lines.append(f"Skipped {len(skipped)}:")
            lines += [f"  {note}" for note in skipped[:50]]
        return ToolResult(ok=True, content="\n".join(lines))


def archive_tools() -> list[Tool]:
    return [Archive()]

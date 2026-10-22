"""D-461: list_archive / extract_archive open zip and tar attachments safely."""

from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from forge.toolkit.base import ToolContext
from forge.tools import archive
from forge.tools.archive import Archive, ArchiveError, clean_entry_name
from forge.workspace.create import create_workspace


def make_context(original_repo: Path, tmp_path: Path) -> ToolContext:
    return ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))


def put_input(context: ToolContext, name: str, data: bytes) -> str:
    inputs = context.workspace.forge_dir / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    (inputs / name).write_bytes(data)
    return f".forge/inputs/{name}"


def zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as handle:
        for name, data in files.items():
            handle.writestr(name, data)
    return buffer.getvalue()


@pytest.mark.parametrize(
    "raw", ["../x.txt", "a/../../x", "/etc/passwd", "C:/x.txt", "a\\..\\..\\x", "con.txt", "a:b"]
)
def test_unsafe_entry_names_are_rejected(raw: str) -> None:
    with pytest.raises(ArchiveError):
        clean_entry_name(raw)


def test_ordinary_names_are_kept() -> None:
    assert clean_entry_name("docs\\a/b.pdf") == "docs/a/b.pdf"
    assert clean_entry_name("./top.txt") == "top.txt"


async def test_a_zip_is_listed_and_unpacked_where_the_readers_can_open_it(
    original_repo: Path, tmp_path: Path
) -> None:
    context = make_context(original_repo, tmp_path)
    path = put_input(context, "20261022-notes.zip", zip_bytes({"a/one.txt": b"hello", "two.md": b"# two"}))
    listed = await Archive().run(Archive.Args(action="list", path=path), context)
    assert listed.ok and "a/one.txt" in listed.content and "2 file(s)" in listed.content
    done = await Archive().run(Archive.Args(action="extract", path=path), context)
    assert done.ok, done.content
    root = context.workspace.forge_dir / "inputs" / "20261022-notes"
    assert (root / "a" / "one.txt").read_bytes() == b"hello"
    assert (root / "two.md").read_text() == "# two"


async def test_path_traversal_entries_are_skipped_and_nothing_escapes(
    original_repo: Path, tmp_path: Path
) -> None:
    context = make_context(original_repo, tmp_path)
    path = put_input(context, "evil.zip", zip_bytes({"../escape.txt": b"x", "ok.txt": b"fine"}))
    done = await Archive().run(Archive.Args(action="extract", path=path), context)
    assert done.ok and "unsafe" in done.content
    assert not (context.workspace.forge_dir / "inputs" / "escape.txt").exists()
    assert not (context.workspace.forge_dir / "escape.txt").exists()
    assert (context.workspace.forge_dir / "inputs" / "evil" / "ok.txt").is_file()


async def test_a_secret_file_inside_the_archive_is_not_unpacked(original_repo: Path, tmp_path: Path) -> None:
    context = make_context(original_repo, tmp_path)
    path = put_input(context, "s.zip", zip_bytes({".env": b"KEY=1", "ok.txt": b"ok"}))
    done = await Archive().run(Archive.Args(action="extract", path=path, destination="unpacked"), context)
    assert done.ok and "secret file" in done.content
    assert not (context.workspace.repo_dir / "unpacked" / ".env").exists()


async def test_a_destination_outside_the_workspace_is_refused(original_repo: Path, tmp_path: Path) -> None:
    context = make_context(original_repo, tmp_path)
    path = put_input(context, "a.zip", zip_bytes({"ok.txt": b"ok"}))
    for bad in ("../outside", ".forge/memory"):
        refused = await Archive().run(Archive.Args(action="extract", path=path, destination=bad), context)
        assert not refused.ok


async def test_a_destination_in_the_workspace_goes_through_the_write_gate(
    original_repo: Path, tmp_path: Path
) -> None:
    context = make_context(original_repo, tmp_path)
    path = put_input(context, "a.zip", zip_bytes({"data/ok.txt": b"ok"}))
    done = await Archive().run(Archive.Args(action="extract", path=path, destination="unpacked"), context)
    assert done.ok, done.content
    assert (context.workspace.repo_dir / "unpacked" / "data" / "ok.txt").read_bytes() == b"ok"


async def test_a_zip_that_lies_about_its_size_stops_at_the_cap(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(archive, "MAX_FILE_BYTES", 1000)
    context = make_context(original_repo, tmp_path)
    path = put_input(context, "bomb.zip", zip_bytes({"big.bin": b"0" * 50_000}))
    refused = await Archive().run(Archive.Args(action="extract", path=path), context)
    assert not refused.ok and "size limit" in refused.content
    assert not (context.workspace.forge_dir / "inputs" / "bomb" / "big.bin").exists()


async def test_too_many_entries_are_refused(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(archive, "MAX_ENTRIES", 2)
    context = make_context(original_repo, tmp_path)
    path = put_input(context, "many.zip", zip_bytes({f"f{n}.txt": b"x" for n in range(5)}))
    refused = await Archive().run(Archive.Args(action="extract", path=path), context)
    assert not refused.ok and "limit" in refused.content


async def test_tar_gz_unpacks_and_links_are_skipped(original_repo: Path, tmp_path: Path) -> None:
    context = make_context(original_repo, tmp_path)
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as handle:
        info = tarfile.TarInfo("dir/file.txt")
        info.size = 3
        handle.addfile(info, io.BytesIO(b"abc"))
        link = tarfile.TarInfo("dir/link")
        link.type = tarfile.SYMTYPE
        link.linkname = "/etc/passwd"
        handle.addfile(link)
    path = put_input(context, "bundle.tar.gz", buffer.getvalue())
    done = await Archive().run(Archive.Args(action="extract", path=path), context)
    assert done.ok and "link (skipped)" in done.content
    root = context.workspace.forge_dir / "inputs" / "bundle"
    assert (root / "dir" / "file.txt").read_bytes() == b"abc"
    assert not (root / "dir" / "link").exists()


async def test_a_file_that_is_not_an_archive_is_reported(original_repo: Path, tmp_path: Path) -> None:
    context = make_context(original_repo, tmp_path)
    path = put_input(context, "fake.zip", b"not a zip at all")
    result = await Archive().run(Archive.Args(action="list", path=path), context)
    assert not result.ok and "not a zip" in result.content


def test_mode_b_folders_outside_project_are_named_through_the_harness(tmp_path: Path) -> None:
    """A live Mode B run failed here with a ValueError: the target was in _harness/, not project/ (D-464)."""
    from types import SimpleNamespace

    root = tmp_path / "ws"
    for folder in ("project", "_harness", ".forge"):
        (root / folder).mkdir(parents=True)
    workspace = SimpleNamespace(
        root=root, repo_dir=root / "project", harness_dir=root / "_harness", forge_dir=root / ".forge"
    )
    context = SimpleNamespace(workspace=workspace)
    assert archive._workspace_relative(context, root / "project" / "a" / "b.py", False) == "a/b.py"  # type: ignore[arg-type]
    assert (
        archive._workspace_relative(context, root / "_harness" / "ref" / "c.py", False) == "_harness/ref/c.py"
    )  # type: ignore[arg-type]
    assert archive._workspace_relative(context, root / ".forge" / "inputs" / "x", True) == ".forge/inputs/x"  # type: ignore[arg-type]
    with pytest.raises(ArchiveError):
        archive._workspace_relative(context, tmp_path / "elsewhere" / "z", False)  # type: ignore[arg-type]

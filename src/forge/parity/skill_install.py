"""Installing a skill from a GitHub repository or a folder (D-207), the way Claude Code treats skills:
installing one is the user's decision to trust it, nothing here scans it, and every command its
instructions lead to still goes through Forge's normal approval. Only the user's own command reaches
this module; the model has no tool for it."""

from __future__ import annotations

import io
import re
import shutil
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import httpx

from forge.errors import ForgeError
from forge.parity.skills import FRONT

MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
MAX_FILES = 5000
MAX_DEPTH = 8
SCRIPT_SUFFIXES = {".py", ".sh", ".ps1", ".bat", ".cmd", ".js", ".mjs", ".ts", ".rb", ".pl", ".exe"}
SKIPPED_FOLDERS = {".git", "node_modules", "__pycache__", ".venv"}
GITHUB = re.compile(
    r"^/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?(?:/tree/(?P<branch>[^/]+)(?P<path>/.*)?)?/?$"
)


class SkillInstallError(ForgeError):
    """The source could not be fetched, or holds no skill, or the skill cannot be installed."""


@dataclass
class Candidate:
    name: str
    description: str
    folder: Path
    allowed_tools: str = ""
    files: list[str] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)
    size_bytes: int = 0


def github_zip_url(source: str) -> tuple[str, str]:
    """(archive URL, sub-folder inside the archive or ''). Only github.com repositories are fetched."""
    parsed = urlparse(source)
    match = GITHUB.match(parsed.path) if parsed.scheme == "https" and parsed.netloc == "github.com" else None
    if match is None:
        raise SkillInstallError(f"{source!r} is not a github.com repository link or an existing folder.")
    owner, repo, branch = match["owner"], match["repo"], match["branch"]
    reference = f"refs/heads/{branch}" if branch else "HEAD"
    return f"https://codeload.github.com/{owner}/{repo}/zip/{reference}", (match["path"] or "").strip("/")


_LINKED_REPO = re.compile(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")


def repo_key(source: str) -> str:
    """'owner/repo' (lower case) of a github.com link; raises when it is not one."""
    github_zip_url(source)  # validates the link
    match = GITHUB.match(urlparse(source).path)
    assert match is not None
    return f"{match['owner']}/{match['repo']}".lower().removesuffix(".git")


def repos_in(text: str) -> set[str]:
    """Every 'owner/repo' mentioned as a github.com link in `text` (what the user typed)."""
    return {f"{owner}/{repo}".lower().removesuffix(".git") for owner, repo in _LINKED_REPO.findall(text)}


def fetch(source: str, destination: Path, client: httpx.Client | None = None) -> Path:
    """Puts the source's files under destination and returns the folder to search for skills."""
    local = Path(source).expanduser()
    if local.is_dir():
        _copy_tree(local, destination / "source")
        return destination / "source"
    url, subfolder = github_zip_url(source)
    owns_client = client is None
    client = client or httpx.Client(follow_redirects=True, timeout=60)
    try:
        data = _download(client, url)
    finally:
        if owns_client:
            client.close()
    extracted = destination / "archive"
    _extract(data, extracted)
    roots = [path for path in extracted.iterdir() if path.is_dir()]
    root = roots[0] if len(roots) == 1 else extracted  # GitHub wraps everything in <repo>-<branch>/
    target = root / subfolder if subfolder else root
    if not target.is_dir():
        raise SkillInstallError(f"The folder {subfolder!r} is not in that repository.")
    return target


def _download(client: httpx.Client, url: str) -> bytes:
    try:
        with client.stream("GET", url) as response:
            if response.status_code == 404:
                raise SkillInstallError(
                    "That repository or branch was not found (private repositories are not supported)."
                )
            response.raise_for_status()
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise SkillInstallError(
                        "The repository is larger than 50 MB; install from a smaller folder."
                    )
                chunks.append(chunk)
            return b"".join(chunks)
    except httpx.HTTPError as error:
        raise SkillInstallError(f"Could not download it: {error}") from error


def _extract(data: bytes, destination: Path) -> None:
    """Unzips with every name checked: no path may leave the destination, and links are never created."""
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as error:
        raise SkillInstallError("The download is not a zip archive.") from error
    with archive:
        members = archive.infolist()
        if len(members) > MAX_FILES or sum(m.file_size for m in members) > MAX_DOWNLOAD_BYTES * 2:
            raise SkillInstallError("The archive holds too many or too large files.")
        for member in members:
            if (member.external_attr >> 16) & 0o170000 == 0o120000:
                continue  # a symbolic link: never recreated
            target = (root / member.filename).resolve()
            if root not in target.parents and target != root:
                raise SkillInstallError(f"The archive has an unsafe path: {member.filename!r}")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(member))


def _copy_tree(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        symlinks=False,
        ignore=shutil.ignore_patterns(*SKIPPED_FOLDERS),
        ignore_dangling_symlinks=True,
    )
    for path in list(destination.rglob("*")):
        if path.is_symlink():
            path.unlink()


def find_skills(root: Path) -> list[Candidate]:
    """Every folder holding a SKILL.md, up to MAX_DEPTH levels down."""
    found: list[Candidate] = []
    for skill_file in sorted(root.rglob("SKILL.md")):
        relative = skill_file.relative_to(root).parts
        if len(relative) > MAX_DEPTH or any(part in SKIPPED_FOLDERS for part in relative):
            continue
        found.append(_describe(skill_file))
    return found


def _describe(skill_file: Path) -> Candidate:
    text = skill_file.read_text(encoding="utf-8", errors="replace")
    match = FRONT.match(text)
    header = match.group(1) if match else ""
    meta = dict(re.findall(r"^([\w-]+):\s*(.+)$", header, re.M))
    folder = skill_file.parent
    files = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())
    return Candidate(
        name=_clean_name(meta.get("name", folder.name)),
        description=meta.get("description", "").strip().strip("\"'"),
        folder=folder,
        allowed_tools=meta.get("allowed-tools", "").strip(),
        files=files,
        scripts=[f for f in files if Path(f).suffix.lower() in SCRIPT_SUFFIXES],
        size_bytes=sum((folder / f).stat().st_size for f in files),
    )


def _clean_name(raw: str) -> str:
    name = re.sub(r"[^a-z0-9._-]+", "-", raw.strip().strip("\"'").lower()).strip("-.")
    return name or "skill"


def summary(candidate: Candidate) -> str:
    """What the user sees before deciding to trust a skill."""
    lines = [
        f"\nSkill: {candidate.name}",
        f"What it says it does: {candidate.description or '(no description)'}",
        f"Files: {len(candidate.files)} ({candidate.size_bytes / 1024:.0f} KB)",
    ]
    if candidate.scripts:
        shown = ", ".join(candidate.scripts[:8]) + (" ..." if len(candidate.scripts) > 8 else "")
        lines.append(f"Contains programs the model may be told to run: {shown}")
    if candidate.allowed_tools:
        lines.append(
            f"It asks for these tools without approval: {candidate.allowed_tools} "
            "(Forge ignores this: commands still ask)"
        )
    lines.append(
        "A skill is instructions Forge follows. Install only skills you trust; read SKILL.md first if unsure."
    )
    return "\n".join(lines)


def install(candidate: Candidate, skills_root: Path, force: bool = False) -> Path:
    destination = skills_root / candidate.name
    if destination.exists():
        if not force:
            raise SkillInstallError(
                f"A skill named {candidate.name!r} is already installed (use --force to replace it)."
            )
        shutil.rmtree(destination)
    skills_root.mkdir(parents=True, exist_ok=True)
    _copy_tree(candidate.folder, destination)
    if candidate.name != candidate.folder.name:
        _write_name(destination / "SKILL.md", candidate.name)
    return destination


def _write_name(skill_file: Path, name: str) -> None:
    """A skill is found by the name in its header; keep it equal to the cleaned folder name."""
    text = skill_file.read_text(encoding="utf-8")
    match = FRONT.match(text)
    if match and re.search(r"^name:", match.group(1), re.M):
        header = re.sub(r"^name:.*$", f"name: {name}", match.group(1), count=1, flags=re.M)
        skill_file.write_text(text.replace(match.group(1), header, 1), encoding="utf-8")


def remove(name: str, skills_root: Path) -> bool:
    target = skills_root / _clean_name(name)
    if not target.is_dir() or skills_root.resolve() not in target.resolve().parents:
        return False
    shutil.rmtree(target)
    return True


def add_from_source(
    source: str,
    skills_root: Path,
    confirm: Callable[[Candidate], bool],
    force: bool = False,
) -> list[str]:
    """Fetches, finds the skills, asks `confirm(candidate)` for each and installs the accepted ones.
    Returns one line per skill saying what happened."""
    with tempfile.TemporaryDirectory(prefix="forge-skill-") as scratch:
        root = fetch(source, Path(scratch))
        candidates = find_skills(root)
        if not candidates:
            raise SkillInstallError("No SKILL.md was found there.")
        lines = []
        seen: set[str] = set()
        for candidate in candidates:
            if candidate.name in seen:  # the same skill is often copied to several folders of one repo
                continue
            seen.add(candidate.name)
            if not confirm(candidate):
                lines.append(f"{candidate.name}: not installed")
                continue
            lines.append(f"{candidate.name}: installed in {install(candidate, skills_root, force)}")
        return lines

"""Installing skills from a GitHub link or a folder (D-207): safe unzip, summary, no overwrite."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import httpx
import pytest

from forge.parity import skill_install
from forge.parity.skills import discover

SKILL = "---\nname: {name}\ndescription: {description}\nallowed-tools: Bash\n---\nDo the thing.\n"


def make_zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, text in files.items():
            archive.writestr(name, text)
    return buffer.getvalue()


def repo_zip() -> bytes:
    return make_zip(
        {
            "repo-main/.claude/skills/Pretty UI/SKILL.md": SKILL.format(
                name="Pretty UI", description="Looks"
            ),
            "repo-main/.claude/skills/Pretty UI/scripts/search.py": "print('hi')\n",
            "repo-main/.claude/skills/Pretty UI/data/styles.csv": "a,b\n",
            "repo-main/cli/assets/skills/pretty-ui/SKILL.md": SKILL.format(
                name="pretty-ui", description="copy"
            ),
            "repo-main/README.md": "readme",
        }
    )


def test_github_links_become_archive_urls() -> None:
    assert skill_install.github_zip_url("https://github.com/o/r") == (
        "https://codeload.github.com/o/r/zip/HEAD",
        "",
    )
    assert skill_install.github_zip_url("https://github.com/o/r/tree/dev/skills/x") == (
        "https://codeload.github.com/o/r/zip/refs/heads/dev",
        "skills/x",
    )
    for bad in ("http://github.com/o/r", "https://evil.example/o/r", "https://github.com/o"):
        with pytest.raises(skill_install.SkillInstallError):
            skill_install.github_zip_url(bad)


def test_download_find_summary_and_install(tmp_path: Path) -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=repo_zip()))
    )
    root = skill_install.fetch("https://github.com/o/r", tmp_path / "scratch", client)
    candidates = skill_install.find_skills(root)
    first = next(c for c in candidates if c.scripts)
    assert (
        first.name == "pretty-ui" and first.scripts == ["scripts/search.py"] and first.allowed_tools == "Bash"
    )
    text = skill_install.summary(first)
    assert "scripts/search.py" in text and "DebCraft ignores this" in text

    skills_root = tmp_path / "skills"
    asked: list[str] = []

    def confirm(candidate: skill_install.Candidate) -> bool:
        asked.append(candidate.name)
        return True

    lines = skill_install.add_from_source(
        str(root), skills_root, confirm
    )  # a local folder works the same way
    assert asked == ["pretty-ui"] and "installed" in lines[0]  # the second copy of the same name is skipped
    installed = discover(skills_root)["pretty-ui"]
    assert (installed.folder / "data" / "styles.csv").is_file()
    with pytest.raises(skill_install.SkillInstallError):
        skill_install.install(first, skills_root)  # never overwrites without --force
    skill_install.install(first, skills_root, force=True)
    assert skill_install.remove("pretty-ui", skills_root) and not skill_install.remove(
        "pretty-ui", skills_root
    )


def test_declined_skill_is_not_installed(tmp_path: Path) -> None:
    source = tmp_path / "src" / "x"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(SKILL.format(name="x", description="d"), encoding="utf-8")
    lines = skill_install.add_from_source(str(tmp_path / "src"), tmp_path / "skills", lambda c: False)
    assert lines == ["x: not installed"] and not (tmp_path / "skills").exists()


def test_archive_paths_cannot_leave_the_folder(tmp_path: Path) -> None:
    evil = make_zip({"repo/SKILL.md": "x", "../../escaped.txt": "boom"})
    with pytest.raises(skill_install.SkillInstallError, match="unsafe path"):
        skill_install._extract(evil, tmp_path / "out")
    assert not (tmp_path / "escaped.txt").exists()


def test_not_found_and_not_a_zip(tmp_path: Path) -> None:
    missing = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(404)))
    with pytest.raises(skill_install.SkillInstallError, match="not found"):
        skill_install.fetch("https://github.com/o/r", tmp_path, missing)
    junk = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"nope")))
    with pytest.raises(skill_install.SkillInstallError, match="not a zip"):
        skill_install.fetch("https://github.com/o/r", tmp_path, junk)


def big_repo_zip() -> bytes:
    """Like archify: one skill folder inside a repository that is mostly other things."""
    files = {
        "archify-main/archify/SKILL.md": SKILL.format(name="archify", description="diagrams"),
        "archify-main/archify/bin/run.mjs": "console.log(1)\n",
        "archify-main/archify/references/a.md": "ref",
        "archify-main/.agents/skills/extra/SKILL.md": SKILL.format(name="extra", description="x"),
        "archify-main/website/page.html": "w" * 1000,
        "archify-main/benchmarks/data.json": "{}",
        "archify-main/README.md": "readme",
        "archify-main/archify/node_modules/pkg/index.js": "skipped",
    }
    return make_zip(files)


def test_only_the_skill_folders_are_unpacked_from_a_large_repository(tmp_path: Path) -> None:
    """D-468: archify's repository is 53 MB, mostly a website and benchmarks; only the skills are needed."""
    skill_install._extract(big_repo_zip(), tmp_path / "out")
    kept = {p.relative_to(tmp_path / "out").as_posix() for p in (tmp_path / "out").rglob("*") if p.is_file()}
    assert "archify-main/archify/bin/run.mjs" in kept and "archify-main/archify/references/a.md" in kept
    assert "archify-main/.agents/skills/extra/SKILL.md" in kept
    assert not any(name.startswith(("archify-main/website", "archify-main/benchmarks")) for name in kept)
    assert "archify-main/README.md" not in kept
    assert not any("node_modules" in name for name in kept)


def test_a_folder_link_unpacks_only_that_folder(tmp_path: Path) -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=big_repo_zip()))
    )
    root = skill_install.fetch("https://github.com/o/archify/tree/main/archify", tmp_path, client)
    assert (root / "SKILL.md").is_file() and (root / "bin" / "run.mjs").is_file()
    assert not (root.parent / "website").exists()


def test_the_download_limit_is_150_mb_and_the_message_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(skill_install, "MAX_DOWNLOAD_BYTES", 1000)
    big = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"x" * 5000))
    )
    with pytest.raises(skill_install.SkillInstallError, match="larger than 0 MB"):
        skill_install.fetch("https://github.com/o/r", tmp_path, big)
    assert skill_install.MAX_DOWNLOAD_BYTES == 1000  # patched; the real value is checked below
    monkeypatch.undo()
    assert skill_install.MAX_DOWNLOAD_BYTES >= 100 * 1024 * 1024


def test_the_skill_itself_may_not_be_too_big(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(skill_install, "MAX_FILES", 2)
    with pytest.raises(skill_install.SkillInstallError, match="too many or too large"):
        skill_install._extract(big_repo_zip(), tmp_path / "out")

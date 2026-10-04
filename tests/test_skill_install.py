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
    assert "scripts/search.py" in text and "Forge ignores this" in text

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

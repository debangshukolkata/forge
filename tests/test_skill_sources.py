"""Known skill sources (D-562): skills that are not part of DebCraft are downloaded on first use, after one approval."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from forge.parity import skill_install
from forge.parity.skill_sources import available, index_lines, load_sources
from forge.parity.skills import discover, header_fields, index_text
from forge.toolkit.base import ToolContext
from forge.tools.deferred import DEFERRED_GROUPS, GROUP_OF
from forge.tools.parity import LoadSkill
from forge.workspace.create import create_workspace

SKILL = "---\nname: pretty-ui\ndescription: Makes screens pretty\n---\n\nUse nice colours.\n"
USER_FILE = """sources:
  - name: pretty-ui
    source: https://github.com/acme/ui/tree/main/pretty-ui
    use_when: Use for pretty screens.
    needs: Node; its checker starts Chrome itself.
    tools: [pictures, find_font]
    own_design: true
  - name: unslop
    source: https://github.com/heydamir/unslop
    enabled: false
  - source: https://github.com/acme/no-name
"""


@pytest.fixture
def fake_repo(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The network fetch is replaced by a folder that holds one skill; everything after it is real."""
    fetched: list[str] = []

    def fetch(source: str, destination: Path, client: Any = None) -> Path:
        fetched.append(source)
        folder = destination / "repo" / "pretty-ui"
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text(SKILL, encoding="utf-8")
        return destination / "repo"

    monkeypatch.setattr(skill_install, "fetch", fetch)
    return fetched


def _context(original_repo: Path, tmp_path: Path, reply: str | None, asked: list[str]) -> ToolContext:
    async def ask(question: str, context: str, options: list[Any], recommended: str | None) -> str:
        asked.append(question + "\n" + context)
        return reply or ""

    context = ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))
    if reply is not None:
        context.ask_user = ask
    return context


def test_the_built_in_list_names_five_pinned_github_folders(isolated_forge_home: Path) -> None:
    sources, problems = load_sources(isolated_forge_home)
    assert problems == []
    assert set(sources) == {
        "impeccable",
        "design-taste-frontend",
        "unslop",
        "extract-design",
        "playwright-cli",
    }
    for entry in sources.values():
        url, subfolder = skill_install.github_zip_url(entry.source)
        assert url.rsplit("/", 1)[1].isalnum() and len(url.rsplit("/", 1)[1]) == 40, entry.name  # a commit id
        assert "refs/heads" not in url and subfolder, entry.name
        assert entry.use_when
        for tool in entry.tools:
            assert tool in DEFERRED_GROUPS or tool in GROUP_OF, (entry.name, tool)


def test_a_branch_link_still_downloads_the_branch() -> None:
    url, subfolder = skill_install.github_zip_url("https://github.com/acme/ui/tree/main/skills/x")
    assert url.endswith("/zip/refs/heads/main") and subfolder == "skills/x"


def test_the_users_file_adds_replaces_and_hides_entries(isolated_forge_home: Path) -> None:
    (isolated_forge_home / "skill_sources.yaml").write_text(USER_FILE, encoding="utf-8")
    sources, problems = load_sources(isolated_forge_home)
    assert "pretty-ui" in sources and "unslop" not in sources and "impeccable" in sources
    assert len(problems) == 1 and "name" in problems[0]  # the entry without a name is reported, the rest load

    (isolated_forge_home / "skill_sources.yaml").write_text("sources: [", encoding="utf-8")
    sources, problems = load_sources(isolated_forge_home)
    assert "impeccable" in sources and problems  # a broken file never takes the built-in list away


def test_a_folded_description_is_read_as_text() -> None:
    header = (
        "name: taste\ndescription: >-\n  first line\n  second line\nhooks:\n  Stop:\n    - x\nlicense: MIT"
    )
    fields = header_fields(header)
    assert fields == {"name": "taste", "description": "first line second line", "license": "MIT"}


def test_the_index_lists_what_can_be_downloaded_until_it_is_installed(isolated_forge_home: Path) -> None:
    installed = discover(isolated_forge_home / "skills")
    text = index_text(installed, index_lines(available(isolated_forge_home, installed))) or ""
    assert "Skills not on this machine yet" in text and "- impeccable: " in text
    assert text.index("- debugging: ") < text.index("Skills not on this machine yet")

    folder = isolated_forge_home / "skills" / "impeccable"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text("---\nname: impeccable\ndescription: x\n---\nbody\n", encoding="utf-8")
    installed = discover(isolated_forge_home / "skills")
    waiting = index_lines(available(isolated_forge_home, installed))
    assert "- impeccable: " not in waiting and "- unslop: " in waiting


async def test_loading_a_listed_skill_downloads_it_once_after_the_user_approves(
    isolated_forge_home: Path, original_repo: Path, tmp_path: Path, fake_repo: list[str]
) -> None:
    (isolated_forge_home / "skill_sources.yaml").write_text(USER_FILE, encoding="utf-8")
    asked: list[str] = []
    changed: list[int] = []
    context = _context(original_repo, tmp_path, "The user chose: Install", asked)
    context.skills_changed = lambda: changed.append(1)

    result = await LoadSkill().run(LoadSkill.Args(name="pretty-ui"), context)
    assert result.ok and "Use nice colours." in result.content
    assert len(asked) == 1 and "Download the skill pretty-ui" in asked[0] and "pretty-ui" in asked[0]
    assert fake_repo[0] == "https://github.com/acme/ui/tree/main/pretty-ui"
    assert (isolated_forge_home / "skills" / "pretty-ui" / "SKILL.md").is_file() and changed == [1]
    # What the list adds to the skill's own text: its needs, the browser note, its tools, the gate standing aside.
    assert "[DebCraft note on this skill]" in result.content and "DevTools pipe error" in result.content
    assert result.meta["attach_tools"] == ["pictures", "find_font"]
    assert context.design_exempt

    again = await LoadSkill().run(LoadSkill.Args(name="pretty-ui"), context)
    assert again.ok and len(asked) == 1  # installed now: no second question, no second download
    assert len(fake_repo) == 2  # the look before the card and the install after it, both from the first load


async def test_a_declined_download_installs_nothing(
    isolated_forge_home: Path, original_repo: Path, tmp_path: Path, fake_repo: list[str]
) -> None:
    (isolated_forge_home / "skill_sources.yaml").write_text(USER_FILE, encoding="utf-8")
    asked: list[str] = []
    context = _context(original_repo, tmp_path, "The user chose: Don't install", asked)
    result = await LoadSkill().run(LoadSkill.Args(name="pretty-ui"), context)
    assert (
        not result.ok and "did not approve" in result.content and "do not ask for it again" in result.content
    )
    assert not (isolated_forge_home / "skills" / "pretty-ui").exists() and not context.design_exempt


async def test_without_a_user_to_ask_nothing_is_downloaded(
    isolated_forge_home: Path, original_repo: Path, tmp_path: Path, fake_repo: list[str]
) -> None:
    (isolated_forge_home / "skill_sources.yaml").write_text(USER_FILE, encoding="utf-8")
    context = _context(original_repo, tmp_path, None, [])
    result = await LoadSkill().run(LoadSkill.Args(name="pretty-ui"), context)
    assert not result.ok and "Cannot ask the user" in result.content and fake_repo == []


async def test_a_name_that_is_on_no_list_is_still_refused(
    isolated_forge_home: Path, original_repo: Path, tmp_path: Path, fake_repo: list[str]
) -> None:
    asked: list[str] = []
    context = _context(original_repo, tmp_path, "The user chose: Install", asked)
    result = await LoadSkill().run(LoadSkill.Args(name="made-up-skill"), context)
    assert not result.ok and "install_skill" in result.content and asked == [] and fake_repo == []

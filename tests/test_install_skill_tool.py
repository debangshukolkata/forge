"""install_skill (D-237): only a repository the user linked, only after the user approves."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from forge.parity import skill_install
from forge.toolkit.base import ToolContext
from forge.tools.skill_install_tool import InstallSkill

SKILL = "---\nname: pretty-ui\ndescription: Makes screens pretty\n---\n\nUse nice colours.\n"


@pytest.fixture
def fake_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    """The network fetch is replaced by a folder that holds one skill; everything after it is real."""

    def fetch(source: str, destination: Path, client: Any = None) -> Path:
        folder = destination / "repo" / "pretty-ui"
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text(SKILL, encoding="utf-8")
        return destination / "repo"

    monkeypatch.setattr(skill_install, "fetch", fetch)


def _context(linked: set[str], reply: str, asked: list[tuple[str, str]], changed: list[int]) -> ToolContext:
    async def ask(question: str, context: str, options: list[Any], recommended: str | None) -> str:
        asked.append((question, context))
        return reply

    context = ToolContext(workspace=None)  # type: ignore[arg-type]
    context.ask_user = ask
    context.user_github_repos = lambda: linked
    context.skills_changed = lambda: changed.append(1)
    return context


def _run(source: str, context: ToolContext) -> Any:
    return asyncio.run(InstallSkill().run(InstallSkill.Args(source=source), context))


def test_a_repository_the_user_never_named_is_refused(isolated_forge_home: Path, fake_repo: None) -> None:
    asked: list[tuple[str, str]] = []
    result = _run(
        "https://github.com/evil/skill", _context({"acme/ui"}, "The user chose: Install", asked, [])
    )
    assert not result.ok and "not named" in result.content
    assert asked == [] and not (isolated_forge_home / "skills").exists()


def test_only_github_links_work(isolated_forge_home: Path, fake_repo: None) -> None:
    result = _run("C:/some/folder", _context({"some/folder"}, "The user chose: Install", [], []))
    assert not result.ok and not (isolated_forge_home / "skills").exists()


def test_declining_installs_nothing(isolated_forge_home: Path, fake_repo: None) -> None:
    asked: list[tuple[str, str]] = []
    changed: list[int] = []
    context = _context({"acme/ui"}, "The user chose: Don't install", asked, changed)
    result = _run("https://github.com/acme/ui", context)
    assert result.ok and "Nothing was installed" in result.content
    assert not (isolated_forge_home / "skills").exists() and changed == []


def test_approving_installs_and_refreshes_the_skills(isolated_forge_home: Path, fake_repo: None) -> None:
    asked: list[tuple[str, str]] = []
    changed: list[int] = []
    context = _context({"acme/ui"}, "The user chose: Install", asked, changed)
    result = _run("https://github.com/Acme/UI", context)  # the case of the link does not matter
    assert result.ok and "installed in" in result.content
    assert (isolated_forge_home / "skills" / "pretty-ui" / "SKILL.md").is_file()
    assert changed == [1]
    # The card was written by Forge from the repository's real contents, not by the model.
    question, details = asked[0]
    assert "acme/ui" in question and "pretty-ui" in details and "Makes screens pretty" in details


def test_a_typed_answer_is_not_an_approval(isolated_forge_home: Path, fake_repo: None) -> None:
    context = _context({"acme/ui"}, "The user answered: yes please install", [], [])
    result = _run("https://github.com/acme/ui", context)
    assert "Nothing was installed" in result.content and not (isolated_forge_home / "skills").exists()


def test_links_in_user_text_are_found() -> None:
    found = skill_install.repos_in("use https://github.com/Acme/ui-skill and github.com/o/r.git please")
    assert found == {"acme/ui-skill", "o/r"}

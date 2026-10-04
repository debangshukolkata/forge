"""Read-only access outside the workspace that the user opens up (D-208): who can grant, what it covers."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.engine.slash_commands import SlashCommandHandler
from forge.parity.mentions import expand
from forge.safety.paths import JailViolationError
from forge.toolkit.base import ToolContext
from forge.tools.files import ReadFile
from forge.tools.search import Glob, Grep, ListDir
from forge.workspace.read_grants import ReadGrantError, ReadGrants
from forge.workspace.workspace import Workspace
from tests.test_parity import workspace  # noqa: F401  (fixture)


@pytest.fixture
def library(tmp_path: Path) -> Path:
    folder = tmp_path / "notes"
    (folder / "deep" / "er").mkdir(parents=True)
    (folder / "spec.md").write_text("alpha\nbeta\n", encoding="utf-8")
    (folder / "deep" / "er" / "more.txt").write_text("needle here\n", encoding="utf-8")
    (folder / ".env").write_text("TOKEN=hunter2\n", encoding="utf-8")
    return folder


@pytest.fixture
def granting(workspace: Workspace, isolated_forge_home: Path) -> Workspace:  # noqa: F811
    workspace.read_grants = ReadGrants.for_workspace(workspace.root, isolated_forge_home)
    return workspace


def test_nothing_is_readable_until_the_user_grants(granting: Workspace, library: Path) -> None:
    assert granting.resolve_readable(str(library / "spec.md")) is None
    granting.read_grants.grant(str(library))
    assert granting.resolve_readable(str(library / "deep" / "er" / "more.txt")) is not None
    assert granting.resolve_readable(str(library.parent / "other.txt")) is None


def test_grants_are_per_project_and_survive_a_reopen(
    granting: Workspace, library: Path, isolated_forge_home: Path, tmp_path: Path
) -> None:
    granting.read_grants.grant(str(library))
    again = ReadGrants.for_workspace(granting.root, isolated_forge_home)
    assert again.allows(library.resolve())
    elsewhere = ReadGrants.for_workspace(tmp_path / "another-project", isolated_forge_home)
    assert not elsewhere.allows(library.resolve())
    assert granting.root not in (isolated_forge_home / "read_grants").parents  # outside what a tool can write


def test_installed_skills_are_always_readable(granting: Workspace, isolated_forge_home: Path) -> None:
    skill = isolated_forge_home / "skills" / "x" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: x\n---\nbody", encoding="utf-8")
    assert granting.resolve_readable(str(skill)) is not None


def test_too_broad_or_forges_own_folder_cannot_be_granted(
    granting: Workspace, isolated_forge_home: Path, tmp_path: Path
) -> None:
    for refused in (Path(tmp_path.anchor), Path.home(), isolated_forge_home, isolated_forge_home / "memory"):
        refused.mkdir(parents=True, exist_ok=True)
        with pytest.raises(ReadGrantError):
            granting.read_grants.grant(str(refused))
    with pytest.raises(ReadGrantError, match="does not exist"):
        granting.read_grants.grant(str(tmp_path / "missing"))
    with pytest.raises(ReadGrantError, match="full path"):
        granting.read_grants.grant("relative/path")


async def test_file_tools_read_a_granted_folder_but_never_write_to_it(
    granting: Workspace, library: Path
) -> None:
    context = ToolContext(workspace=granting)
    with pytest.raises(JailViolationError):  # the agent loop turns this into a tool error
        await ReadFile().run(ReadFile.Args(path=str(library / "spec.md")), context)
    granting.read_grants.grant(str(library))

    read = await ReadFile().run(ReadFile.Args(path=str(library / "spec.md")), context)
    assert read.ok and "alpha" in read.content
    secret = await ReadFile().run(ReadFile.Args(path=str(library / ".env")), context)
    assert (
        "hunter2" not in secret.content and "TOKEN" in secret.content
    )  # key names only, as in the workspace
    listing = await ListDir().run(ListDir.Args(path=str(library)), context)
    assert "spec.md" in listing.content and "deep/" in listing.content
    found = await Glob().run(Glob.Args(pattern="*.txt", path=str(library)), context)
    assert "more.txt" in found.content
    hits = await Grep().run(Grep.Args(pattern="needle", path=str(library), output_mode="content"), context)
    assert "needle here" in hits.content and "hunter2" not in hits.content

    with pytest.raises(JailViolationError):  # the write jail is untouched by a read grant
        granting.jail.check(library / "spec.md")


def test_the_shell_may_read_a_granted_folder_and_still_blocks_other_places(
    granting: Workspace, library: Path, tmp_path: Path
) -> None:
    from dataclasses import replace

    from forge.safety.shell_classifier import classify
    from forge.toolkit.shell import ShellSession

    other = tmp_path / "other"
    other.mkdir()
    (other / "x.txt").write_text("x", encoding="utf-8")
    read_spec = f'type "{library / "spec.md"}"'
    session = ShellSession(granting, sandbox="off")
    assert classify(read_spec, session.scope()).level == "ask"  # Mode A: reading outside always asks
    strict_before = replace(session.scope(), strict=True)  # Mode B: blocked
    assert classify(read_spec, strict_before).level == "blocked"

    granting.read_grants.grant(str(library))
    strict = replace(session.scope(), strict=True)
    assert classify(read_spec, strict).level == "safe"
    assert classify(f'type "{other / "x.txt"}"', strict).level == "blocked"
    assert classify(f'del "{library / "spec.md"}"', strict).level == "blocked"  # reading only


def test_typed_and_mentioned_paths_grant_only_with_the_users_own_words(
    granting: Workspace, library: Path
) -> None:
    quiet = expand(f"the build wrote {library}", granting)
    assert quiet.grants == [] and granting.resolve_readable(str(library)) is None  # no read request

    asked = expand(f"please read {library} and summarise it", granting)
    assert len(asked.grants) == 1 and "everything under it" in asked.grants[0]
    assert granting.resolve_readable(str(library / "spec.md")) is not None
    assert expand(f"read {library} again", granting).grants == []  # already allowed: nothing new to announce


def test_an_at_mention_of_an_absolute_file_attaches_it(granting: Workspace, library: Path) -> None:
    result = expand(f"explain @{library / 'spec.md'}", granting)
    assert "alpha" in result.text and result.grants


def test_a_long_paste_never_grants(granting: Workspace, library: Path) -> None:
    result = expand("read " + f"{library} " + "filler " * 3000, granting)
    assert result.grants == [] and granting.resolve_readable(str(library)) is None


async def test_slash_commands_list_grant_and_revoke(granting: Workspace, library: Path) -> None:
    said: list[str] = []

    class Host:
        workspace = granting

        class bus:
            @staticmethod
            async def publish(kind: object, data: dict[str, str]) -> None:
                said.append(data["text"])

    handler = SlashCommandHandler(Host())  # type: ignore[arg-type]
    await handler.handle(f"/allow-read {library}")
    assert "may now read" in said[-1] and granting.read_grants.allows(library.resolve())
    await handler.handle("/allow-read")
    assert str(library.resolve()) in said[-1]
    await handler.handle(f"/revoke-read {library}")
    assert said[-1] == "Removed." and not granting.read_grants.allows(library.resolve())
    await handler.handle(f"/allow-read {Path.home()}")
    assert "whole profile" in said[-1]

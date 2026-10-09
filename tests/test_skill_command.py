from __future__ import annotations

import asyncio
from pathlib import Path

from forge.engine.skill_command import run_skill_command


def _source(tmp_path: Path) -> Path:
    folder = tmp_path / "source" / "pretty-ui"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(
        "---\nname: pretty-ui\ndescription: Make UIs pretty\n---\nBody\n", encoding="utf-8"
    )
    return folder.parent


def _run(rest: str, root: Path) -> tuple[bool, str]:
    said: list[str] = []

    async def say(text: str) -> None:
        said.append(text)

    changed = asyncio.run(run_skill_command(rest, root, say))
    return changed, "\n".join(said)


def test_add_without_yes_only_shows_what_the_source_holds(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    changed, text = _run(f'add "{_source(tmp_path)}"', root)
    assert not changed and "pretty-ui" in text and "--yes" in text
    assert not (root / "pretty-ui").exists()


def test_add_with_yes_installs_then_list_and_remove(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    changed, _ = _run(f'add "{_source(tmp_path)}" --yes', root)
    assert changed and (root / "pretty-ui" / "SKILL.md").is_file()
    assert "pretty-ui: Make UIs pretty" in _run("list", root)[1]
    assert _run("remove pretty-ui", root)[0] and not (root / "pretty-ui").exists()


def test_bad_input_prints_the_usage(tmp_path: Path) -> None:
    assert "Usage: /skill add" in _run("", tmp_path)[1]
    assert "Could not add the skill" in _run(f'add "{tmp_path / "missing"}" --yes', tmp_path / "s")[1]

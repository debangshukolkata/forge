"""Skills installed together are listed as one pack line in the index (D-480)."""

from __future__ import annotations

from pathlib import Path

from forge.parity import skill_install
from forge.parity.skills import discover, index_text, set_pack


def make_skill(root: Path, name: str, description: str = "does a thing") -> Path:
    folder = root / name
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\nbody of {name}\n", encoding="utf-8"
    )
    return folder


def test_pack_of_three_or_more_becomes_one_line(tmp_path: Path) -> None:
    for name in ("alpha", "beta", "gamma"):
        set_pack(make_skill(tmp_path, name, f"{name} description"), "taste")
    make_skill(tmp_path, "solo", "stays on its own line")
    text = index_text(discover(tmp_path)) or ""
    assert "- taste (pack of 3 skills: alpha, beta, gamma)" in text
    assert "- solo: stays on its own line" in text
    assert "alpha description" not in text


def test_small_pack_is_listed_one_by_one(tmp_path: Path) -> None:
    for name in ("alpha", "beta"):
        set_pack(make_skill(tmp_path, name), "taste")
    text = index_text(discover(tmp_path)) or ""
    assert "- alpha: does a thing" in text and "pack of" not in text


def test_pack_name_never_hides_a_skill_with_that_name(tmp_path: Path) -> None:
    for name in ("alpha", "beta", "gamma"):
        set_pack(make_skill(tmp_path, name), "solo")
    make_skill(tmp_path, "solo")
    assert "pack of" not in (index_text(discover(tmp_path)) or "")


def test_group_command_and_header_line(tmp_path: Path) -> None:
    make_skill(tmp_path, "one")
    two = make_skill(tmp_path, "two")
    text = (
        (two / "SKILL.md")
        .read_text(encoding="utf-8")
        .replace("description:", "pack: from-header\ndescription:")
    )
    (two / "SKILL.md").write_text(text, encoding="utf-8")
    assert discover(tmp_path)["two"].pack == "from-header"
    assert skill_install.group(["one", "nope"], "My Pack", tmp_path) == ["nope"]
    assert discover(tmp_path)["one"].pack == "my-pack"
    skill_install.group(["one"], "", tmp_path)
    assert discover(tmp_path)["one"].pack == ""


def test_install_writes_the_pack_from_the_folder_name(tmp_path: Path) -> None:
    source = tmp_path / "taste-skill"
    for name in ("a", "b", "c"):
        make_skill(source, name)
    skill_install.add_from_source(str(source), tmp_path / "home", lambda candidate: True)
    assert {s.pack for s in discover(tmp_path / "home").values() if s.name in "abc"} == {"taste-skill"}


def test_install_summary_warns_about_a_description_that_would_route_badly(tmp_path: Path) -> None:
    from forge.parity.skill_install import Candidate, description_warnings, summary

    vague = Candidate("x", "Elite UX engineer. " + "Very fancy. " * 30, tmp_path)
    assert len(description_warnings(vague)) == 3
    assert "Description check" in summary(vague)
    good = Candidate(
        "y", "Restyle a page in a minimalist look. Use when the user asks for a clean, flat design.", tmp_path
    )
    assert description_warnings(good) == []
    assert "Description check" not in summary(good)
    assert description_warnings(Candidate("z", "", tmp_path))


async def test_a_skill_with_its_own_style_guide_lifts_the_page_design_gate_once_loaded(
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path
) -> None:
    from forge.toolkit.base import ToolContext
    from forge.tools.files import design_gate
    from forge.tools.parity import LoadSkill
    from forge.workspace.create import create_workspace

    folder = make_skill(isolated_forge_home / "skills", "drawer")
    text = (
        (folder / "SKILL.md")
        .read_text(encoding="utf-8")
        .replace("description:", "own_design: true\ndescription:")
    )
    (folder / "SKILL.md").write_text(text, encoding="utf-8")
    make_skill(isolated_forge_home / "skills", "plain")
    context = ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))
    assert discover(isolated_forge_home / "skills")["drawer"].own_design

    await LoadSkill().run(LoadSkill.Args(name="plain"), context)
    assert "DESIGN.md" in design_gate(context, "diagram.html")  # an ordinary skill changes nothing
    context.design_gate_rounds = 0
    await LoadSkill().run(LoadSkill.Args(name="drawer"), context)
    assert design_gate(context, "diagram.html") == ""


async def test_a_forked_skill_is_not_loaded_into_the_conversation_but_pointed_to_a_subagent(
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path
) -> None:
    """C12 c (D-515): `context: fork` in the front matter keeps the skill's long text out of the main conversation; load_skill says how to run it."""
    from forge.toolkit.base import ToolContext
    from forge.tools.parity import LoadSkill
    from forge.workspace.create import create_workspace

    folder = make_skill(isolated_forge_home / "skills", "noisy")
    (folder / "SKILL.md").write_text(
        "---\nname: noisy\ncontext: fork\ndescription: Use when a long scan is needed\n---\nTHE LONG SECRET BODY\n", encoding="utf-8"
    )
    make_skill(isolated_forge_home / "skills", "plain")
    assert discover(isolated_forge_home / "skills")["noisy"].fork
    assert not discover(isolated_forge_home / "skills")["plain"].fork
    context = ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))
    result = await LoadSkill().run(LoadSkill.Args(name="noisy"), context)
    assert result.ok and 'agent "skill:noisy"' in result.content and "LONG SECRET BODY" not in result.content
    assert "body of plain" in (await LoadSkill().run(LoadSkill.Args(name="plain"), context)).content

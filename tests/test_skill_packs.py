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

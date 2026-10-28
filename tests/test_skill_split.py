"""D-520: the conditional sections of the ui-design-quality skill live in files of their own and SKILL.md points to every one of them by its exact path."""

from __future__ import annotations

import re
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / "src" / "forge" / "skills" / "ui-design-quality"


def test_every_moved_section_has_its_file_and_is_pointed_to() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    pointed = set(re.findall(r"`(recipes/skill-[a-z-]+\.md)`", text))
    assert len(pointed) >= 6, pointed
    for relative in pointed:
        moved = SKILL / relative
        assert moved.is_file() and moved.stat().st_size > 400, relative
    on_disk = {f"recipes/{p.name}" for p in (SKILL / "recipes").glob("skill-*.md")}
    assert on_disk == pointed  # no moved file that nothing points to


def test_the_core_stays_in_the_skill_and_the_skill_stays_smaller_than_before() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    for heading in (
        "## 0e. The design ladder",
        "## 0g. Typography",
        "## 0h. Compose the page",
        "## 5. The look-and-fix loop",
        "## Gotchas",
    ):
        assert heading in text, heading
    assert len(text) < 52_000  # it was 58,790 characters before the split (D-520)

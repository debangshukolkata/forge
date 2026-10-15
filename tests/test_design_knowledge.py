"""DIE3: the design knowledge base keeps references and recent design choices in the profile folder and finds them by words."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge.config import Secrets
from forge.toolkit.base import ToolContext
from forge.tools import design_knowledge as kb
from forge.workspace.create import create_workspace

NL = chr(10)
DESIGN = (
    "---" + NL + "name: Kiln" + NL + "composition: lay-editorial-split" + NL + "colors:" + NL + '  primary: "#B5532B"' + NL + '  neutral: "#FAF6F0"' + NL
    + "typography:" + NL + "  display:" + NL + "    fontFamily: Fraunces, serif" + NL + "  body:" + NL + "    fontFamily: Inter, sans-serif" + NL + "---" + NL
)  # fmt: skip


@pytest.fixture(autouse=True)
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("FORGE_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def test_a_design_md_gives_its_use_record_without_names() -> None:
    use = kb.use_from_design_md(DESIGN)
    assert use is not None
    assert (
        use["primary"] == "#B5532B"
        and use["fonts"] == ["Fraunces", "Inter"]
        and use["composition"] == "lay-editorial-split"
    )
    assert "Kiln" not in json.dumps(use)
    assert kb.use_from_design_md("no front matter") is None


def test_a_use_is_recorded_once_and_the_last_ones_are_listed() -> None:
    kb.record_use(DESIGN)
    kb.record_use(DESIGN)  # the same design again is not a second use
    kb.record_use(DESIGN.replace("#B5532B", "#1F6F5B"))
    assert [u["primary"] for u in kb.recent_uses()] == ["#B5532B", "#1F6F5B"]


def test_references_are_found_by_industry_and_mood_first() -> None:
    kb.add_reference(
        {
            "id": "a",
            "title": "Kiln Co",
            "industry": "pottery studio",
            "mood": "warm handmade",
            "layout": "split hero",
            "principles": ["big serif"],
        }
    )
    kb.add_reference(
        {
            "id": "b",
            "title": "Ledger",
            "industry": "accounting software",
            "mood": "calm precise",
            "layout": "dashboard",
            "principles": ["tabular numbers"],
        }
    )
    found = kb.search_references("warm pottery studio with a split hero")
    assert [r["id"] for r in found] == ["a"]
    assert kb.search_references("zzz") == []
    assert "big serif" in kb.describe_reference(found[0])


async def test_the_tools_keep_a_looked_at_page_and_search_it(original_repo: Path, tmp_path: Path) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace, secrets=Secrets({}, None))
    base = workspace.root / kb.INSPIRATION
    base.mkdir(parents=True)
    (base / "kiln-1.styles.json").write_text(
        json.dumps(
            {
                "title": "Kiln Co",
                "backgrounds": [["rgb(250, 246, 240)", 900]],
                "texts": [["rgb(29, 26, 23)", 400]],
                "fonts": ["Fraunces"],
                "sections": [{"heading": "Pots"}],
            }
        ),
        encoding="utf-8",
    )
    (base / "kiln-1.design.md").write_text("Source: https://kiln.example/", encoding="utf-8")
    (base / "kiln-1.png").write_bytes(b"png")
    missing = await kb.DesignKbAdd().run(
        kb.DesignKbAdd.Args(slug="nope", industry="x", mood="y", layout="z", principles=["p"]), context
    )
    assert not missing.ok
    added = await kb.DesignKbAdd().run(
        kb.DesignKbAdd.Args(
            slug="kiln-1",
            industry="pottery studio",
            mood="warm handmade",
            layout="split hero",
            principles=["one big serif headline"],
        ),
        context,
    )
    assert added.ok
    searched = await kb.DesignKbSearch().run(kb.DesignKbSearch.Args(query="pottery warm"), context)
    assert (
        "one big serif headline" in searched.content
        and "https://kiln.example/" in searched.content
        and "kiln-1.png" in searched.content
    )

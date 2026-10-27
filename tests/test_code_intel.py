"""find_definition, find_references and list_symbols: jedi-backed lookups, and the clear message when jedi is missing."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.toolkit.base import ToolContext
from forge.tools import code_intel
from forge.tools.code_intel import FindDefinition, FindReferences, ListSymbols
from forge.workspace.create import create_workspace

HELPERS = '''"""Helpers."""


class Store:
    def add(self, item):
        return item


def compute_total(values):
    return sum(values)
'''

MAIN = """from pkg.helpers import Store, compute_total


def report(values):
    store = Store()
    store.add(1)
    return compute_total(values)


def again(values):
    return compute_total(values) + 1
"""


def _context(original_repo: Path, tmp_path: Path) -> ToolContext:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    root = workspace.path_of(".")
    (root / "pkg").mkdir(exist_ok=True)
    (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "pkg" / "helpers.py").write_text(HELPERS, encoding="utf-8")
    (root / "pkg" / "main.py").write_text(MAIN, encoding="utf-8")
    return ToolContext(workspace=workspace)


async def test_find_definition_follows_an_import_to_the_other_file(
    original_repo: Path, tmp_path: Path
) -> None:
    pytest.importorskip("jedi")
    context = _context(original_repo, tmp_path)
    # line 7 of main.py: "    return compute_total(values)", column 13 is inside the name
    result = await FindDefinition().run(FindDefinition.Args(path="pkg/main.py", line=7, column=13), context)
    assert result.ok, result.content
    assert "pkg/helpers.py:9" in result.content and "def compute_total" in result.content


async def test_find_references_lists_both_uses_and_the_definition(
    original_repo: Path, tmp_path: Path
) -> None:
    pytest.importorskip("jedi")
    context = _context(original_repo, tmp_path)
    result = await FindReferences().run(
        FindReferences.Args(path="pkg/helpers.py", line=9, column=6), context
    )
    assert result.ok, result.content
    assert "pkg/main.py:7" in result.content and "pkg/main.py:11" in result.content
    assert "pkg/helpers.py:9" in result.content


async def test_list_symbols_lists_a_files_classes_and_functions_and_searches_the_project(
    original_repo: Path, tmp_path: Path
) -> None:
    pytest.importorskip("jedi")
    context = _context(original_repo, tmp_path)
    listing = await ListSymbols().run(ListSymbols.Args(path="pkg/helpers.py"), context)
    assert listing.ok, listing.content
    assert (
        "class Store" in listing.content
        and "function add" in listing.content
        and "function compute_total" in listing.content
    )
    found = await ListSymbols().run(ListSymbols.Args(query="compute_total"), context)
    assert found.ok and "pkg/helpers.py:9" in found.content
    nothing = await ListSymbols().run(ListSymbols.Args(), context)
    assert not nothing.ok


async def test_a_missing_file_is_reported_not_raised(original_repo: Path, tmp_path: Path) -> None:
    pytest.importorskip("jedi")
    context = _context(original_repo, tmp_path)
    result = await FindDefinition().run(FindDefinition.Args(path="pkg/nowhere.py", line=1, column=1), context)
    assert not result.ok


async def test_without_jedi_every_tool_returns_the_install_hint(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _context(original_repo, tmp_path)
    monkeypatch.setattr(code_intel, "_load_jedi", lambda: None)
    for result in (
        await FindDefinition().run(FindDefinition.Args(path="pkg/main.py", line=7, column=13), context),
        await FindReferences().run(FindReferences.Args(path="pkg/main.py", line=7, column=13), context),
        await ListSymbols().run(ListSymbols.Args(path="pkg/main.py"), context),
        await ListSymbols().run(ListSymbols.Args(query="Store"), context),
    ):
        assert not result.ok
        assert "pip install jedi" in result.content and "code_outline" in result.content

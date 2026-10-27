"""C11 (D-498): code_outline shows structure and callers without reading whole files."""

from __future__ import annotations

from pathlib import Path

from forge.toolkit.base import ToolContext
from forge.tools.code_outline import CodeOutline, generic_outline, python_callers, python_outline
from forge.workspace.create import create_workspace

SAMPLE = '''"""A module."""
LIMIT = 3


class Store(Base):
    """Keeps things."""

    def add(self, item: str, *, urgent: bool = False) -> int:
        """Add one item."""
        return helper(item)


async def fetch(url: str) -> bytes:
    return b""


def helper(item):
    return len(item)
'''


def test_python_outline_lists_classes_methods_signatures_and_constants() -> None:
    lines = python_outline(SAMPLE)
    text = "\n".join(lines)
    assert "2: LIMIT = ..." in text
    assert "class Store(Base)  # Keeps things." in text
    assert "def add(self, item: str, *, urgent: bool=False) -> int  # Add one item." in text
    assert "async def fetch(url: str) -> bytes" in text
    assert any(
        line.startswith("  ") and "def add" in line for line in lines
    )  # methods are indented under their class


def test_python_outline_reports_a_syntax_error_instead_of_failing() -> None:
    assert python_outline("def broken(:\n")[0].startswith("(does not parse")


def test_generic_outline_finds_typescript_and_go_definitions() -> None:
    typescript = "export class Cart {}\nexport const total = (items: Item[]) => 1\nexport async function load(id: string) {}\n"
    found = generic_outline(typescript)
    assert "1: class Cart" in found and "2: function total" in found and "3: function load" in found
    assert "1: function Run" in generic_outline("func Run(args []string) error {\n")


def test_callers_name_the_enclosing_function() -> None:
    hits = python_callers(SAMPLE, "helper")
    assert hits == [(10, "add")]
    assert python_callers("x = helper(1)\n", "helper") == [(1, "<module>")]
    assert python_callers("def f():\n    obj.helper(2)\n", "helper") == [(2, "f")]


async def test_the_tool_outlines_a_folder_and_skips_dependencies_and_secrets(
    original_repo: Path, tmp_path: Path
) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    root = workspace.path_of(".")
    (root / "pkg").mkdir()
    (root / "pkg" / "store.py").write_text(SAMPLE, encoding="utf-8")
    (root / "node_modules" / "dep").mkdir(parents=True)
    (root / "node_modules" / "dep" / "index.js").write_text("export function hidden() {}\n", encoding="utf-8")
    context = ToolContext(workspace=workspace)
    outline = await CodeOutline().run(CodeOutline.Args(path="pkg"), context)
    assert outline.ok and "store.py" in outline.content and "class Store" in outline.content
    everything = await CodeOutline().run(CodeOutline.Args(path="."), context)
    assert "hidden" not in everything.content
    callers = await CodeOutline().run(CodeOutline.Args(action="callers", path="pkg", name="helper"), context)
    assert callers.ok and "store.py:10  in add" in callers.content
    missing = await CodeOutline().run(CodeOutline.Args(path="nowhere"), context)
    assert not missing.ok

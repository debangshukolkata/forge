"""C3: every code block marked `# runnable` in a Python recipe really runs, so the recipes cannot rot."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

RECIPES = sorted(
    (Path(__file__).resolve().parents[1] / "src/forge/skills/python-project/assets/recipe").glob("*.md")
)
BLOCK = re.compile(r"```python\n(# runnable\n.*?)```", re.S)


def test_there_are_recipes_and_each_has_a_runnable_example() -> None:
    assert len(RECIPES) >= 12
    for recipe in RECIPES:
        assert BLOCK.search(recipe.read_text(encoding="utf-8")), f"{recipe.name} has no runnable block"


@pytest.mark.parametrize("recipe", RECIPES, ids=lambda path: path.stem)
def test_runnable_blocks_run(recipe: Path, tmp_path: Path) -> None:
    for number, code in enumerate(BLOCK.findall(recipe.read_text(encoding="utf-8")), 1):
        script = tmp_path / f"block{number}.py"
        script.write_text(code, encoding="utf-8")
        run = subprocess.run(
            [sys.executable, str(script)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=300,
        )
        assert run.returncode == 0, f"{recipe.name} block {number} failed:\n{run.stderr[-1500:]}"

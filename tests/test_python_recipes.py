"""C3: every code block marked `# runnable` in a Python recipe really runs, so the recipes cannot rot."""

from __future__ import annotations

import os
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
        text = recipe.read_text(encoding="utf-8")
        # a recipe about a package that is not installed here says so in `tested:` and shows its example unexecuted
        if re.search(r"^tested:.*not executed", text, re.M):
            continue
        assert BLOCK.search(text), f"{recipe.name} has no runnable block"


@pytest.mark.parametrize("recipe", RECIPES, ids=lambda path: path.stem)
def test_runnable_blocks_run(recipe: Path, tmp_path: Path) -> None:
    for number, code in enumerate(BLOCK.findall(recipe.read_text(encoding="utf-8")), 1):
        script = tmp_path / f"block{number}.py"
        script.write_text(code, encoding="utf-8")
        # A recipe's own example test uses pytest's tmp_path, so the nested pytest creates and prunes folders in the system Temp area that the outer workers
        # (and the browser tests) use at the same time; a folder that vanishes mid-scan is a FileNotFoundError that has nothing to do with the recipe. The nested
        # run gets a private temp folder, and that one error is still retried as a second guard.
        private_temp = tmp_path / "nested-temp"
        private_temp.mkdir(exist_ok=True)
        for _attempt in range(3):
            run = subprocess.run(
                [sys.executable, str(script)],
                cwd=tmp_path,
                # the outer pytest-xdist worker's variables would leak into the nested pytest run
                env={
                    **{
                        key: value
                        for key, value in os.environ.items()
                        if not key.startswith(("PYTEST_", "XDIST_"))
                    },
                    "TEMP": str(private_temp),
                    "TMP": str(private_temp),
                },
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=300,
            )
            if run.returncode == 0 or "FileNotFoundError" not in run.stdout:
                break
        assert run.returncode == 0, (
            f"{recipe.name} block {number} failed:\n{run.stdout[-1800:]}\n{run.stderr[-1500:]}"
        )

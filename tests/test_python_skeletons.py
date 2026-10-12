"""C5: every Python skeleton is a working project: on a fresh copy ruff, mypy --strict and pytest all pass."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from forge.toolkit.base import ToolContext
from forge.tools.assets import AddAsset
from forge.workspace.create import create_workspace

SKELETONS = ["skel-python-package", "skel-python-cli", "skel-async-worker", "skel-fastapi-service"]


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


@pytest.mark.parametrize("skeleton", SKELETONS)
async def test_skeleton_passes_its_own_checks(skeleton: str, tmp_path: Path, original_repo: Path) -> None:
    context = ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))
    added = await AddAsset().run(
        AddAsset.Args(
            id=skeleton,
            project_dir="demo",
            variables={"package": "inventory_tool", "description": "Keeps track of stock"},
        ),
        context,
    )
    assert added.ok, added.content
    project = tmp_path / "copy"
    shutil.copytree(context.workspace.repo_dir / "demo", project)
    assert (project / "src" / "inventory_tool" / "__init__.py").is_file()
    assert "{{" not in "".join(
        p.read_text(encoding="utf-8") for p in project.rglob("*") if p.is_file() and p.suffix != ".yml"
    )

    for command in (
        ["ruff", "check", "."],
        ["ruff", "format", "--check", "."],
        ["mypy"],
        ["pytest", "-p", "no:cacheprovider"],
    ):
        result = _run(command, project)
        assert result.returncode == 0, (
            f"{' '.join(command)} failed:\n{result.stdout[-2500:]}{result.stderr[-800:]}"
        )


async def test_missing_placeholder_values_are_reported(tmp_path: Path, original_repo: Path) -> None:
    context = ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))
    result = await AddAsset().run(AddAsset.Args(id="skel-python-package"), context)
    assert not result.ok and "description" in result.content and "package" in result.content

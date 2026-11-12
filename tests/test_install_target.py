"""KP8 (D-574): libraries installed to run the application do not go into the repository copy."""

# ruff: noqa: F811  (the `shop` fixture is imported from another test module)
from __future__ import annotations

from pathlib import Path

from forge.toolkit.shell import install_into_copy, libraries_folder
from forge.workspace.create import create_workspace
from tests.test_knowledge_structure import shop  # noqa: F401  (shop is a fixture)


def test_a_pip_target_inside_the_copy_is_refused_and_a_target_outside_it_is_allowed(
    isolated_forge_home: Path, shop: Path, tmp_path: Path
) -> None:
    workspace = create_workspace(shop, tmp_path / "ws", "")
    here = workspace.repo_dir
    for command in (
        "python -m pip install --target .vendor requests",
        "pip install -t .vendor requests",
        'python -m pip install --target="./.vendor" requests',
        f'pip3 install --target "{here / "libs"}" requests',
    ):
        refusal = install_into_copy(workspace, command, here)
        assert refusal and "inside the repository copy" in refusal, command
        assert str(libraries_folder(workspace)) in refusal

    libs = libraries_folder(workspace)
    assert install_into_copy(workspace, f'python -m pip install --target "{libs}" requests', here) is None
    assert install_into_copy(workspace, "python -m pip install requests", here) is None
    assert install_into_copy(workspace, "pytest -t something", here) is None  # -t of another program
    assert not libs.is_relative_to(workspace.repo_dir)

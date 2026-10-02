"""Mode B stub-package plumbing: keeps the host stubs from hiding the new code (moved from modeb/workspace.py
so verify can call it without depending on modeb)."""

from __future__ import annotations

from forge.workspace.workspace import Workspace

EXTEND_PATH_LINE = '__path__ = __import__("pkgutil").extend_path(__path__, __name__)'


def ensure_shared_stub_packages(workspace: Workspace) -> list[str]:
    """Every stub package that project/ also has must extend its __path__, or the stub hides the new code
    ("cannot import name 'x_service' from 'pkg.services'", seen live, the agent losing tasks to it). This is
    plumbing, not a design choice, so Forge does it before each test run. Returns the fixed files."""
    stubs = workspace.harness_dir / "host_stubs"
    fixed = []
    for init in sorted(stubs.rglob("__init__.py")) if stubs.is_dir() else []:
        package = init.parent.relative_to(stubs)
        if not (workspace.repo_dir / package).is_dir():
            continue
        text = init.read_text(encoding="utf-8")
        if "extend_path" in text:
            continue
        relative = f"_harness/host_stubs/{package.as_posix()}/__init__.py"
        workspace.write_text(
            relative, EXTEND_PATH_LINE + "\n" + text, reason="share the package with project/"
        )
        fixed.append(package.as_posix())
    return fixed

"""D-437: add_ui_component installs a Magic UI component by name and a component the user chose by a link they typed; nothing else."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import pytest

from forge.toolkit.base import ToolContext, ToolResult
from forge.tools import shadcn
from forge.tools.shadcn import AddUiComponent, classify_source
from forge.workspace.create import create_workspace

TYPED = {"https://21st.dev/r/some-author/hero-block"}


def test_a_magic_ui_name_is_allowed_and_an_untyped_or_unknown_address_is_refused() -> None:
    assert classify_source("@magicui/marquee", set()) == ("@magicui/marquee", "MIT (Magic UI)")
    assert isinstance(classify_source("@other/thing", set()), str)  # not a registry we know
    assert "has not typed" in str(classify_source("https://21st.dev/r/a/b", set()))
    assert "not one of the registries" in str(
        classify_source("https://evil.example/r/x", {"https://evil.example/r/x"})
    )
    target, terms = classify_source(
        'npx shadcn@latest add "https://21st.dev/r/some-author/hero-block"', TYPED
    )  # type: ignore[misc]
    assert target == "https://21st.dev/r/some-author/hero-block" and "author's own licence" in terms


async def test_the_tool_runs_the_cli_once_and_records_the_terms(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []

    async def fake_execute(context: Any, command: str, timeout: int, cwd: str) -> ToolResult:
        seen.append(command)
        return ToolResult(ok=True, content="added components/ui/marquee.tsx")

    monkeypatch.setattr(shadcn, "execute", fake_execute)
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace)
    context.shell = object()  # type: ignore[assignment]
    context.user_urls = lambda: TYPED
    missing = await AddUiComponent().run(AddUiComponent.Args(source="@magicui/marquee"), context)
    assert not missing.ok and "shadcn_setup" in missing.content  # no components.json yet
    workspace.write_text("components.json", "{}", "stub")
    added = await AddUiComponent().run(AddUiComponent.Args(source="@magicui/marquee"), context)
    assert added.ok and seen == ['npx --yes shadcn@latest add "@magicui/marquee" -y']
    chosen = await AddUiComponent().run(
        AddUiComponent.Args(source="https://21st.dev/r/some-author/hero-block"), context
    )
    assert chosen.ok and "check it" in chosen.content
    notices, _ = workspace.read_text("NOTICES.md")
    assert "@magicui/marquee" in notices and "21st.dev/r/some-author/hero-block" in notices
    refused = await AddUiComponent().run(
        AddUiComponent.Args(source="https://21st.dev/r/another/found-it-myself"), context
    )
    assert not refused.ok and len(seen) == 2


@pytest.mark.skipif(
    os.environ.get("FORGE_NETWORK_TESTS") != "1" or shutil.which("npm") is None,
    reason="set FORGE_NETWORK_TESTS=1 (needs npm and the internet, takes minutes)",
)
async def test_a_real_magic_ui_component_on_a_new_project(tmp_path: Path, original_repo: Path) -> None:
    from forge.toolkit.shell import ShellSession

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace)
    context.shell = ShellSession(workspace, sandbox="off")  # type: ignore[arg-type]
    setup = await shadcn.ShadcnSetup().run(shadcn.ShadcnSetup.Args(project_dir="web"), context)
    assert setup.ok, setup.content
    added = await AddUiComponent().run(
        AddUiComponent.Args(source="@magicui/marquee", project_dir="web"), context
    )
    assert added.ok, added.content
    assert any("marquee" in p.name for p in (workspace.repo_dir / "web" / "src").rglob("*.tsx"))

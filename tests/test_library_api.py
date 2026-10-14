"""D-372: library_api answers from the installed code: signatures, docstrings, the nearest real names for an invented one."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from forge.tools.library_api import INTROSPECT, LibraryApi, render


def introspect(package: str, symbol: str = "-", query: str = "-") -> dict[str, Any]:
    done = subprocess.run(
        [sys.executable, "-I", "-c", INTROSPECT, package, symbol, query],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(done.stdout.strip().splitlines()[-1])  # type: ignore[no-any-return]


def test_a_real_function_is_described_with_its_signature_and_docstring() -> None:
    data = introspect("json", "json.loads")
    assert data["kind"] == "function" and "s" in data["signature"] and "JSON" in data["doc"]
    text = render(data)
    assert "json.loads(s" in text and "[function]" in text


def test_an_invented_name_gets_the_nearest_real_ones() -> None:
    data = introspect("json", "json.lodas")
    assert "does not exist" in data["error"] and "loads" in data["nearest"]
    text = render(data)
    assert "NOT FOUND" in text and "Nearest real names" in text and "loads" in text


def test_a_missing_package_and_a_search_are_answered() -> None:
    assert "cannot import" in introspect("no_such_package_xyz")["error"]
    data = introspect("json", "-", "decode")
    names = [row[0] for row in data["matches"]]
    assert "JSONDecodeError" in names and "decoder" in names  # a class and a submodule


def test_a_class_lists_its_public_methods() -> None:
    data = introspect("pathlib", "pathlib.Path")
    members = {row[0] for row in data["members"]}
    assert data["kind"] == "class" and {"read_text", "write_text", "exists"} <= members


async def test_the_tool_runs_through_the_apps_shell(original_repo: Path, tmp_path: Path) -> None:
    from forge.toolkit.base import ToolContext
    from forge.toolkit.shell import ShellSession
    from forge.workspace.create import create_workspace

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace, shell=ShellSession(workspace, sandbox="off"))
    found = await LibraryApi().run(LibraryApi.Args(package="json", symbol="json.dumps"), context)
    assert found.ok, found.content
    assert "dumps" in found.content and "indent" in found.content
    wrong = await LibraryApi().run(LibraryApi.Args(package="json", symbol="json.dump_all"), context)
    assert wrong.ok and "NOT FOUND" in wrong.content and "dumps" in wrong.content

"""D-642: versions of a library and what a name looks like in any of them, read from the wheel without running it."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any

import httpx
import pytest

from forge.deps import published as published_module
from forge.deps.published import WheelCode, fetch_published, pick_release
from forge.toolkit.base import ToolContext
from forge.tools import library_versions
from forge.tools.library_versions import LibraryVersions, overview
from forge.workspace.create import create_workspace


def wheel(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, text in files.items():
            archive.writestr(name, text)
    return buffer.getvalue()


OLD = wheel(
    {
        "demo/__init__.py": "",
        "demo/agents/__init__.py": "class AgentExecutor:\n    def run(self, x: int) -> str: ...\n",
    }
)
NEW = wheel(
    {
        "demo/__init__.py": "raise SystemExit('never run')\n",
        "demo/agents/__init__.py": "from demo.agents.factory import create_agent\nfrom .old import make\n"
        "from other.place import Thing\n__all__ = ['create_agent', 'lazy']\n",
        "demo/agents/factory.py": "def create_agent(model: str, *, middleware: list = ()) -> int:\n    '''Makes it.'''\n",
        "demo/agents/old.py": "@deprecated('use create_agent')\ndef make(model): ...\n",
    }
)
RELEASES = {
    "0.3.1": [
        {
            "filename": "demo-0.3.1-py3-none-any.whl",
            "url": "https://files.test/old.whl",
            "upload_time": "2025-01-01T",
        }
    ],
    "1.0.0": [
        {
            "filename": "demo-1.0.0-py3-none-any.whl",
            "url": "https://files.test/new.whl",
            "upload_time": "2025-10-01T",
            "requires_python": ">=3.11",
        }
    ],
    "1.1.0rc1": [{"filename": "x-none-any.whl", "url": "https://files.test/rc.whl"}],
    "1.2.0": [{"filename": "y-none-any.whl", "url": "https://files.test/bad.whl", "yanked": True}],
}


def client() -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/pypi/demo/json":
            return httpx.Response(
                200, json={"releases": RELEASES, "info": {"requires_dist": ["langgraph<1.3"]}}
            )
        if request.url.host == "files.test":
            return httpx.Response(200, content=OLD if request.url.path == "/old.whl" else NEW)
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture
def pypi(monkeypatch: pytest.MonkeyPatch) -> None:
    library_versions._wheels.clear()
    monkeypatch.setattr(library_versions, "fetch_published", lambda name: fetch_published(name, client))
    monkeypatch.setattr(
        library_versions, "fetch_wheel", lambda url: published_module.fetch_wheel(url, client)
    )


def test_releases_leave_out_pre_releases_and_a_yanked_one_is_not_the_latest() -> None:
    found = fetch_published("demo", client)
    assert [r.version for r in found.releases] == ["0.3.1", "1.0.0", "1.2.0"]
    for wanted, version in {"latest": "1.0.0", "0.3": "0.3.1", "1.0.0": "1.0.0"}.items():
        release = pick_release(found, wanted)
        assert release is not None and release.version == version
    assert pick_release(found, "9") is None
    with pytest.raises(ValueError, match="not a package name"):
        fetch_published("demo/../x", client)


def test_a_name_is_followed_through_its_re_exports_and_nothing_is_run() -> None:
    code = WheelCode(NEW)
    found = code.describe("demo.agents.create_agent")
    assert "demo.agents.factory.create_agent(model: str, *, middleware: list=()) -> int" in found
    assert "DEPRECATED" in code.describe("demo.agents.make")
    assert "another package" in code.describe("demo.agents.Thing")
    assert "loaded lazily" in code.describe("demo.agents.lazy")
    assert "DOES NOT EXIST" in code.describe("demo.agents.AgentExecutor")
    assert "NOT IN THIS PACKAGE" in code.describe("elsewhere.x")
    assert "run(self, x: int) -> str" in WheelCode(OLD).describe("demo.agents.AgentExecutor")


def test_the_overview_names_the_gap_between_installed_and_latest() -> None:
    text = overview("demo", ["0.3.1 (requirements.txt)"], "0.3.1", fetch_published("demo", client), "")
    assert "installed in the project's environment: 0.3.1" in text and "latest: 1.0.0" in text
    assert "major version differs" in text and "langgraph<1.3" in text


async def test_the_tool_compares_versions_and_reports_what_the_project_declares(
    pypi: None, original_repo: Path, tmp_path: Path
) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace)
    tool = LibraryVersions()
    compared = await tool.run(
        tool.Args(
            action="api", packages=["demo"], symbol="demo.agents.create_agent", versions=["0.3", "latest"]
        ),
        context,
    )
    assert compared.ok and "## demo 0.3.1" in compared.content and "DOES NOT EXIST" in compared.content
    assert "## demo 1.0.0" in compared.content and "middleware" in compared.content
    seen = await tool.run(tool.Args(packages=["demo", "langgraph"]), context)
    assert "latest: 1.0.0" in seen.content
    assert "1.2.12 (" in seen.content  # langgraph, declared in the fixture's requirements.txt
    assert "PyPI could not be read" in seen.content  # langgraph is not on this test's PyPI


@pytest.mark.parametrize("packages", [["a b"], ["../x"], []])
async def test_only_names_and_versions_leave_the_machine(packages: list[str]) -> None:
    tool = LibraryVersions()
    context: Any = ToolContext(workspace=None)  # type: ignore[arg-type]
    assert not (await tool.run(tool.Args(packages=packages), context)).ok

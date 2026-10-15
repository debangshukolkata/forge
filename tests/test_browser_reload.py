"""D-391: a screenshot after edits reloads the page, so the audit judges the files as they are now, not as they were when the page was opened."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge.toolkit.base import ToolContext
from forge.tools.browser import BrowserScreenshot, BrowserSession
from forge.workspace.create import create_workspace


class StubPage:
    url = "http://127.0.0.1:1/index.html"

    def __init__(self) -> None:
        self.reloads = 0

    async def reload(self, **_: Any) -> None:
        self.reloads += 1

    async def screenshot(self, path: str, **_: Any) -> None:
        Path(path).write_bytes(b"png" + bytes([self.reloads]))

    async def evaluate(self, *_: Any) -> dict[str, Any]:
        return {"findings": []}

    async def set_viewport_size(self, *_: Any) -> None:
        return None


async def test_a_screenshot_reloads_the_page_only_when_files_changed_since_it_loaded(
    tmp_path: Path, original_repo: Path
) -> None:
    context = ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))
    session = BrowserSession()
    page = StubPage()
    session.page = page
    session.loaded_step = 2
    context.browser = session

    context.step = 3
    first = await BrowserScreenshot().run(BrowserScreenshot.Args(), context)
    assert page.reloads == 0 and "reloaded" not in first.content

    context.step = 5
    context.last_edit_step = 5  # a stylesheet was edited after the page was loaded
    second = await BrowserScreenshot().run(BrowserScreenshot.Args(), context)
    assert page.reloads == 1 and "The page was reloaded first" in second.content

    context.step = 6
    third = await BrowserScreenshot().run(BrowserScreenshot.Args(), context)
    assert page.reloads == 1 and "reloaded" not in third.content  # the edit is in the page now

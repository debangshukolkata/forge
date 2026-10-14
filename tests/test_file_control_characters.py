"""D-379: a write that would put control characters into a text file is refused with the place and the fix (seen live: an en dash arrived as U+0013, the file then held NULs
and every later write failed with 'is a binary file')."""

from __future__ import annotations

from pathlib import Path

from forge.toolkit.base import ToolContext
from forge.tools.files import EditFile, WriteFile, control_character_problem
from forge.workspace.create import create_workspace


def test_the_problem_names_the_place_and_ignores_normal_whitespace() -> None:
    text = "<title>Pulse \x13 Home</title>\n<p>You\x19re in</p>"
    message = control_character_problem(text)
    assert (
        message
        and "2 control character(s)" in message
        and "U+0013 at line 1" in message
        and "&ndash;" in message
    )
    assert control_character_problem("tab\there\r\nand a newline\n") is None
    assert control_character_problem("a – b ’ c") is None  # real dashes and quotes are fine
    assert (
        control_character_problem("old \x13", before="old \x13") is None
    )  # a file that already had it is not blocked for keeping it


async def test_write_and_edit_refuse_new_control_characters(original_repo: Path, tmp_path: Path) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace, design_first=False)
    bad = await WriteFile().run(
        WriteFile.Args(path="page.html", content="<h1>Pulse \x13 Home</h1>\n"), context
    )
    assert not bad.ok and "control character" in bad.content and not workspace.path_of("page.html").exists()
    good = await WriteFile().run(WriteFile.Args(path="page.html", content="<h1>Pulse – Home</h1>\n"), context)
    assert good.ok
    broken = await EditFile().run(
        EditFile.Args(path="page.html", old_string="Home", new_string="Ho\x00me"), context
    )
    assert not broken.ok and "U+0000" in broken.content
    assert "Pulse – Home" in workspace.path_of("page.html").read_text(encoding="utf-8")

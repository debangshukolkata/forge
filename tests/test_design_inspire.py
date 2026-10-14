"""D-349: a DESIGN.md draft from a project's styles or a page's computed styles, and the import of a user's file or typed link."""

from __future__ import annotations

import http.server
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from forge.designsystem.extract import css_from_project, draft_design_md, from_computed, from_css
from forge.designsystem.lint import lint_text
from forge.designsystem.spec import DesignMdError, parse_design_md
from forge.toolkit.base import ToolContext
from forge.tools.design_inspire import DesignInspire, DesignMdFromProject, DesignMdImport
from forge.tools.web_guard import WebPolicy
from forge.workspace.create import create_workspace

THEME = """
@theme {
  --color-primary: #0F766E;
  --color-background: #FAFAF9;
  --color-foreground: #1C1917;
  --color-muted: #57534E;
  --color-surface: #F0EFEA;
  --color-border: #D6D3D1;
  --color-error: #B91C1C;
  --font-display: "Fraunces", serif;
  --font-body: "Inter", system-ui, sans-serif;
  --radius-md: 12px;
  --radius-sm: 6px;
}
"""
PAGE = """<!doctype html><html><head><title>Acme Roasters</title><style>
body { margin:0; background:#FFF8F0; color:#2B1D14; font-family: Georgia, serif; }
h1 { font-size: 56px; font-family: 'Playfair Display', Georgia, serif; margin: 40px; }
p { font-size: 18px; margin: 0 40px; }
.card { background:#F3E3D3; margin:40px; padding:24px; border-radius:16px; }
a.btn { display:inline-block; background:#C2410C; color:#FFFFFF; padding:12px 24px; border-radius:999px; margin:0 40px; text-decoration:none; }
</style></head><body><h1>Small-batch coffee</h1><p>Roasted on Tuesdays and shipped the same day.</p>
<div class="card"><p>Our story</p></div><a class="btn" href="#">Order a bag</a></body></html>"""


@pytest.fixture
def server() -> Iterator[str]:
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = (
                PAGE.encode()
                if self.path in ("/", "/index.html")
                else (THEME_DESIGN.encode() if self.path == "/DESIGN.md" else b"")
            )
            self.send_response(200 if body else 404)
            self.send_header("Content-Type", "text/html" if self.path != "/DESIGN.md" else "text/markdown")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


THEME_DESIGN = draft_design_md(from_css(THEME), "Acme", "a test")


def test_css_tokens_become_a_draft_that_passes_the_linter() -> None:
    found = from_css(THEME)
    assert (
        found.colors["primary"] == "#0F766E"
        and found.colors["neutral"] == "#FAFAF9"
        and found.colors["ink"] == "#1C1917"
    )
    assert (
        found.fonts[:2] == ["Fraunces", "Inter"]
        and found.radii == [6.0, 12.0]
        and found.colors["error"] == "#B91C1C"
    )
    draft = draft_design_md(found, "Acme design system", "the project's own style files")
    assert [f for f in lint_text(draft) if f.severity in ("error", "warning")] == []
    system = parse_design_md(draft)
    assert system.typography["display"]["fontFamily"] == "Fraunces" and system.rounded["sm"] == "6px"
    with pytest.raises(DesignMdError, match="No design tokens"):
        css_from_project({"a.css": "body { color: red; }"})


def test_a_faint_text_colour_is_corrected_and_the_gap_is_stated() -> None:
    found = from_computed(
        {
            "backgrounds": [["rgb(255, 255, 255)", 900000]],
            "texts": [["rgb(200, 200, 200)", 500]],
            "accents": [["rgb(194, 65, 12)", 2000]],
            "fonts": ['Georgia, "Times New Roman", serif'],
            "sizes": ["16", "18", "56"],
            "radii": ["16", "999"],
        }
    )
    draft = draft_design_md(found, "Faint", "a test page")
    assert [f for f in lint_text(draft) if f.severity == "error"] == []
    assert "too faint" in draft and "Known Gaps" in draft


async def test_a_draft_is_made_from_the_projects_own_styles(original_repo: Path, tmp_path: Path) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    workspace.write_text("web/src/theme.css", THEME, "x")
    context = ToolContext(workspace=workspace)
    made = await DesignMdFromProject().run(DesignMdFromProject.Args(folder="web", name="Acme"), context)
    assert made.ok, made.content
    assert "Acme design system" in workspace.path_of("DESIGN.md").read_text(encoding="utf-8")
    again = await DesignMdFromProject().run(DesignMdFromProject.Args(folder="web", name="Acme"), context)
    assert not again.ok and "exists already" in again.content
    empty = await DesignMdFromProject().run(
        DesignMdFromProject.Args(folder="backend", output="X.md"), context
    )
    assert not empty.ok


async def test_import_takes_a_file_or_only_a_link_the_user_typed(
    original_repo: Path, tmp_path: Path, server: str
) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace, web_policy=WebPolicy(allow_hosts=("127.0.0.1",)))
    workspace.write_text("docs/brand/DESIGN.md", THEME_DESIGN, "x")
    local = await DesignMdImport().run(DesignMdImport.Args(source="docs/brand/DESIGN.md"), context)
    assert local.ok and workspace.path_of("DESIGN.md").is_file()
    blocked = await DesignMdImport().run(
        DesignMdImport.Args(source=f"{server}/DESIGN.md", output="two.md"), context
    )
    assert not blocked.ok and "has not typed" in blocked.content
    context.user_urls = lambda: {f"{server}/DESIGN.md"}
    fetched = await DesignMdImport().run(
        DesignMdImport.Args(source=f"{server}/DESIGN.md", output="two.md"), context
    )
    assert fetched.ok, fetched.content
    exists = await DesignMdImport().run(DesignMdImport.Args(source="docs/brand/DESIGN.md"), context)
    assert not exists.ok and "exists already" in exists.content
    context.web_policy = WebPolicy()  # the default guard refuses an address on this computer
    context.user_urls = lambda: {f"{server}/DESIGN.md"}
    refused = await DesignMdImport().run(
        DesignMdImport.Args(source=f"{server}/DESIGN.md", output="three.md"), context
    )
    assert not refused.ok and "not fetched" in refused.content


async def test_inspire_captures_a_picture_and_reads_the_styles(
    original_repo: Path, tmp_path: Path, server: str
) -> None:
    pytest.importorskip("playwright.async_api")
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace, web_policy=WebPolicy(allow_hosts=("127.0.0.1",)))
    blocked = await DesignInspire().run(DesignInspire.Args(urls=[server]), ToolContext(workspace=workspace))
    assert not blocked.ok and "not opened" in blocked.content
    result = await DesignInspire().run(DesignInspire.Args(urls=[server]), context)
    if not result.ok and "could not be captured" in result.content:
        pytest.skip(result.content)
    assert result.ok, result.content
    folder = workspace.root / ".forge" / "inspiration"
    drafts = list(folder.glob("*.design.md"))
    assert drafts and list(folder.glob("*.png"))
    draft = drafts[0].read_text(encoding="utf-8")
    assert "#C2410C" in draft.upper() and "Playfair Display" in draft
    assert [f for f in lint_text(draft) if f.severity == "error"] == []
    assert "view_image" in result.content and "Acme Roasters" in result.content

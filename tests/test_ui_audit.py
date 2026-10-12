"""D-245: browser_screenshot audits the rendered page; a UI task needs a look (and a clean audit) before done."""

from __future__ import annotations

import functools
import http.server
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from forge.toolkit.base import ToolContext
from forge.tools.browser import BrowserClose, BrowserOpen, BrowserScreenshot
from forge.workspace.create import create_workspace

UNSTYLED = """<!doctype html><html><body>
<h1>Donate Blood</h1><p>Join our drive.</p>
<div class="flex gap-4 p-6 rounded-xl bg-red-600 text-white"><span class="px-4 py-2 rounded-full">A</span>
<span class="px-4 py-2 rounded-full">B</span></div>
<div class="flex gap-4 p-6 rounded-xl bg-red-600"><span class="px-4 py-2">C</span></div>
<a href="#">Register</a><button>Go</button></body></html>"""

STYLED = """<!doctype html><html><head><style>
body{margin:0;font-family:Inter,Arial,sans-serif;color:#1f2937;background:#fff}
h1{font-size:48px;margin:0 0 16px}p{font-size:18px;line-height:1.5}
main{max-width:960px;margin:0 auto;padding:64px 24px}
.btn{display:inline-block;padding:12px 20px;border-radius:12px;background:#b91c1c;color:#fff;
text-decoration:none;border:0;font-size:16px}
small{font-size:14px;color:#4b5563}
</style></head><body><main><h1>Donate Blood</h1><p>Join our drive.</p>
<a class="btn" href="#">Register</a> <small>9:00 - 17:00</small></main></body></html>"""


@pytest.fixture
def site(tmp_path: Path) -> Iterator[str]:
    root = tmp_path / "site"
    root.mkdir()
    (root / "unstyled.html").write_text(UNSTYLED, encoding="utf-8")
    (root / "styled.html").write_text(STYLED, encoding="utf-8")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.mark.e2e
async def test_the_audit_flags_a_page_whose_css_framework_produced_nothing(
    site: str, tmp_path: Path, original_repo: Path
) -> None:
    pytest.importorskip("playwright.async_api")
    context = ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))
    context.step = 3
    try:
        assert (await BrowserOpen().run(BrowserOpen.Args(url=f"{site}/unstyled.html"), context)).ok
        shot = await BrowserScreenshot().run(BrowserScreenshot.Args(), context)
        assert shot.ok and "BLOCKER" in shot.content and "no effect" in shot.content
        assert context.ui_audit_blocked and context.last_screenshot_step == 3
        assert "view_image" in shot.content
    finally:
        await BrowserClose().run(BrowserClose.Args(), context)


@pytest.mark.e2e
async def test_the_audit_passes_a_styled_page_and_can_switch_to_a_phone_width(
    site: str, tmp_path: Path, original_repo: Path
) -> None:
    pytest.importorskip("playwright.async_api")
    context = ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))
    try:
        assert (await BrowserOpen().run(BrowserOpen.Args(url=f"{site}/styled.html"), context)).ok
        desktop = await BrowserScreenshot().run(BrowserScreenshot.Args(), context)
        assert "BLOCKER" not in desktop.content and not context.ui_audit_blocked, desktop.content
        phone = await BrowserScreenshot().run(BrowserScreenshot.Args(width=375), context)
        assert "375x800" in phone.content, phone.content
    finally:
        await BrowserClose().run(BrowserClose.Args(), context)


def _vite_project(root: Path, tailwind: str, extra_deps: dict[str, str], css: str, vite_config: str) -> None:
    import json

    (root / "frontend" / "src").mkdir(parents=True, exist_ok=True)
    deps = {"tailwindcss": tailwind, **extra_deps}
    (root / "frontend" / "package.json").write_text(json.dumps({"devDependencies": deps}), encoding="utf-8")
    (root / "frontend" / "src" / "index.css").write_text(css, encoding="utf-8")
    (root / "frontend" / "vite.config.ts").write_text(vite_config, encoding="utf-8")


def test_tailwind_v4_without_the_import_or_plugin_is_reported(tmp_path: Path) -> None:
    from forge.tools.ui_audit import tailwind_setup_problem

    _vite_project(tmp_path, "^4.1.0", {}, "@tailwind base;\n@tailwind utilities;\n", "export default {}")
    assert "@tailwindcss/vite" in (tailwind_setup_problem(tmp_path) or "")
    plugin = {"@tailwindcss/vite": "^4.1.0"}
    _vite_project(
        tmp_path, "^4.1.0", plugin, "@tailwind base;\n", "import tailwindcss from '@tailwindcss/vite'"
    )
    assert 'import "tailwindcss"' in (tailwind_setup_problem(tmp_path) or "")


def test_a_correct_tailwind_setup_and_a_project_without_tailwind_are_fine(tmp_path: Path) -> None:
    from forge.tools.ui_audit import tailwind_setup_problem

    assert tailwind_setup_problem(tmp_path) is None
    plugin = {"@tailwindcss/vite": "^4.1.0"}
    _vite_project(
        tmp_path, "^4.1.0", plugin, '@import "tailwindcss";\n', "import tailwindcss from '@tailwindcss/vite'"
    )
    assert tailwind_setup_problem(tmp_path) is None


async def test_show_app_finds_a_server_that_listens_on_ipv6_only() -> None:
    """Vite on Windows listens on localhost = ::1 only; 127.0.0.1 refuses (D-247)."""
    import socket

    from forge.tools.show_app import wait_for_answer

    probe = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    try:
        probe.bind(("::1", 0))
    except OSError:
        probe.close()
        pytest.skip("IPv6 loopback is not available here")
    probe.close()

    class IPv6Server(http.server.ThreadingHTTPServer):
        address_family = socket.AF_INET6

    server = IPv6Server(("::1", 0), http.server.SimpleHTTPRequestHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url, detail = await wait_for_answer(port, "/")
        assert url is not None, detail
        assert "127.0.0.1" not in url
    finally:
        server.shutdown()


def test_the_design_critic_verdict_is_read_from_its_report() -> None:
    from forge.subagents.critic import critic_verdict
    from forge.tools.parity import BUILT_IN_TYPES

    assert "design-critic" in BUILT_IN_TYPES
    assert critic_verdict("SCORES: Hierarchy 4\nVERDICT: SHIP") == "SHIP"
    assert critic_verdict("... VERDICT: revise") == "REVISE"
    assert critic_verdict("no verdict line") is None


def test_the_skill_ships_its_reference_files() -> None:
    from forge.parity.skills import discover
    from forge.tools.parity import skill_files_note

    skill = discover()["ui-design-quality"]
    listed = skill_files_note(skill)
    for name in (
        "recipes/design-md-template.md",
        "recipes/index.css",
        "recipes/landing-reference.tsx",
        "recipes/palettes-and-fonts.md",
    ):
        assert name in listed


@pytest.mark.e2e
async def test_two_pages_that_look_identical_are_flagged(
    site: str, tmp_path: Path, original_repo: Path
) -> None:
    pytest.importorskip("playwright.async_api")
    context = ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))
    try:
        await BrowserOpen().run(BrowserOpen.Args(url=f"{site}/styled.html"), context)
        first = await BrowserScreenshot().run(BrowserScreenshot.Args(), context)
        assert "identical" not in first.content
        await BrowserOpen().run(BrowserOpen.Args(url=f"{site}/styled.html?copy=1"), context)
        second = await BrowserScreenshot().run(BrowserScreenshot.Args(), context)
        assert "pixel-identical" in second.content and context.ui_audit_blocked
    finally:
        await BrowserClose().run(BrowserClose.Args(), context)


GENERIC = """<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;font-family:Arial,sans-serif;color:#222}
.hero{padding:900px 24px 24px}h1{font-size:44px;margin:0 0 12px}
.cta{display:inline-block;padding:12px 20px;background:#b91c1c;color:#fff;border-radius:12px;text-decoration:none}
</style></head><body><div class="hero"><h1>Welcome to Acme \u2014 your trusted partner \u2014 today</h1>
<p>Lorem ipsum dolor sit amet.</p><a class="cta" href="#">Get started</a></div></body></html>"""


@pytest.mark.e2e
async def test_the_audit_flags_generic_tells(tmp_path: Path, original_repo: Path) -> None:
    pytest.importorskip("playwright.async_api")
    root = tmp_path / "site2"
    root.mkdir()
    (root / "generic.html").write_text(GENERIC, encoding="utf-8")
    (root / "app.js").write_text("window.alert('hi'); const x = '<img src=a.png>';\n", encoding="utf-8")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    (workspace.root / "src").mkdir(exist_ok=True)
    (workspace.root / "src" / "app.js").write_text("window.alert('hi');\n", encoding="utf-8")
    context = ToolContext(workspace=workspace)
    try:
        await BrowserOpen().run(
            BrowserOpen.Args(url=f"http://127.0.0.1:{server.server_address[1]}/generic.html"), context
        )
        shot = await BrowserScreenshot().run(BrowserScreenshot.Args(), context)
        text = shot.content
        assert "below the fold" in text and "em dashes" in text and "Placeholder content" in text
        assert "alert() is used" in text
    finally:
        await BrowserClose().run(BrowserClose.Args(), context)
        server.shutdown()


REVEAL = """<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;font:18px Arial}.spacer{height:2400px}.reveal{opacity:0;transition:opacity .3s}.reveal.is-visible{opacity:1}
</style></head><body><div class="spacer"></div><h2 id="late" class="reveal">Below the fold</h2><div class="spacer"></div>
<script>new IntersectionObserver((es)=>es.forEach(e=>e.isIntersecting&&e.target.classList.add('is-visible'))).observe(document.getElementById('late'))</script>
</body></html>"""


@pytest.mark.e2e
async def test_a_full_page_screenshot_first_plays_reveal_on_scroll_content(
    tmp_path: Path, original_repo: Path
) -> None:
    pytest.importorskip("playwright.async_api")
    root = tmp_path / "reveal"
    root.mkdir()
    (root / "index.html").write_text(REVEAL, encoding="utf-8")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    context = ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))
    try:
        await BrowserOpen().run(
            BrowserOpen.Args(url=f"http://127.0.0.1:{server.server_address[1]}/"), context
        )
        assert context.browser is not None
        assert (
            await context.browser.page.evaluate(
                "document.getElementById('late').classList.contains('is-visible')"
            )
            is False
        )
        await BrowserScreenshot().run(BrowserScreenshot.Args(full_page=True), context)
        assert (
            await context.browser.page.evaluate(
                "document.getElementById('late').classList.contains('is-visible')"
            )
            is True
        )
    finally:
        await BrowserClose().run(BrowserClose.Args(), context)
        server.shutdown()


BROKEN = """<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;font:16px Arial;background:#0b1020;color:#e5e7eb}
header{position:sticky;top:0;height:64px;background:transparent;display:flex;align-items:center;padding:0 24px}
main{padding:24px}h1{font-size:44px;margin:0 0 16px}
.card{width:200px;overflow:hidden;white-space:nowrap;border:1px solid #334}
input{display:block;margin-top:16px;padding:10px;border:1px solid #0e1426;background:#0b1020;color:#e5e7eb}
</style></head><body><header><b>Brand</b></header><main><h1>Give blood</h1>
<div class="card">One unit, three lives, register now please</div>
<label>Name<input aria-label="Name"></label></main></body></html>"""


@pytest.mark.e2e
async def test_the_audit_flags_see_through_headers_invisible_fields_and_clipped_text(
    tmp_path: Path, original_repo: Path
) -> None:
    pytest.importorskip("playwright.async_api")
    root = tmp_path / "broken"
    root.mkdir()
    (root / "index.html").write_text(BROKEN, encoding="utf-8")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    context = ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))
    try:
        await BrowserOpen().run(
            BrowserOpen.Args(url=f"http://127.0.0.1:{server.server_address[1]}/"), context
        )
        text = (await BrowserScreenshot().run(BrowserScreenshot.Args(), context)).content
        assert "see-through background" in text
        assert "nearly invisible" in text
        assert "cut off by its container" in text
    finally:
        await BrowserClose().run(BrowserClose.Args(), context)
        server.shutdown()

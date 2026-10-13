"""P1.2: the slides of a deck in the web UI: a strip of thumbnails in the chat with a viewer (arrow keys, speaker notes), and a
slide viewer for a .pptx in the Files tab, served by a narrow route."""

from __future__ import annotations

import json

import pytest

from forge.protocol.events import EventType
from forge.workspace.workspace import Workspace
from tests.conftest import REPO_ROOT
from tests.test_web_e2e import (  # noqa: F401  (the fixtures are used by name)
    LiveServer,
    configured_secrets,
    live_server,
    open_in_edge,
    playwright_api,
    workspace,
)
from tests.test_web_image_e2e import tiny_png

pytestmark = pytest.mark.e2e

SLIDES = ".forge/reports/slides/deck"


def make_pictures(workspace: Workspace, count: int = 3) -> list[str]:  # noqa: F811
    folder = workspace.root / SLIDES
    folder.mkdir(parents=True, exist_ok=True)
    names = []
    for number in range(1, count + 1):
        (folder / f"slide-{number}.png").write_bytes(tiny_png(320, 180))
        names.append(f"{SLIDES}/slide-{number}.png")
    return names


def make_deck(workspace: Workspace) -> str:  # noqa: F811
    from forge.slides.build import build_deck
    from forge.slides.spec import parse_deck

    outline = {
        "title": "Deck",
        "slides": [
            {"layout": "title", "title": "Q3 review", "notes": "Welcome everyone."},
            {
                "layout": "bullets",
                "title": "We shipped three things",
                "bullets": ["a", "b"],
                "notes": "Say thanks.",
            },
            {"layout": "closing", "title": "Thank you"},
        ],
    }
    workspace.write_bytes(
        "deck.pptx", build_deck(parse_deck(json.dumps(outline)), lambda name: b"").data, "deck"
    )
    return "deck.pptx"


def test_slides_appear_in_the_chat_and_open_in_a_viewer(
    live_server: LiveServer,  # noqa: F811
    workspace: Workspace,  # noqa: F811
) -> None:
    pictures = make_pictures(workspace)
    artifacts = REPO_ROOT / "test-artifacts" / "react-ui"
    artifacts.mkdir(parents=True, exist_ok=True)
    with playwright_api.sync_playwright() as p:
        browser, page = open_in_edge(p, live_server, workspace)
        live_server.publish(
            EventType.NOTICE,
            {
                "kind": "slides_ready",
                "text": "Slides of docs/deck.pptx",
                "deck": "docs/deck.pptx",
                "pictures": pictures,
                "notes": ["Welcome everyone.", "", "Thank them."],
            },
        )
        page.wait_for_selector("[data-testid=slide-thumb]")
        assert page.locator("[data-testid=slide-thumb]").count() == 3
        page.wait_for_function(
            "() => document.querySelector('[data-testid=slide-thumb] img').naturalWidth === 320"
        )
        page.screenshot(path=str(artifacts / "slides-strip.png"))
        page.locator("[data-testid=slide-thumb]").nth(1).click()
        page.wait_for_selector("[data-testid=slide-modal]")
        assert "Slide 2 of 3" in page.inner_text("[data-testid=slide-modal]")
        assert "none for this slide" in page.inner_text("[data-testid=slide-notes]")
        page.keyboard.press("ArrowRight")
        page.wait_for_function(
            "document.querySelector('[data-testid=slide-notes]').innerText.includes('Thank them.')"
        )
        page.screenshot(path=str(artifacts / "slides-viewer.png"))
        page.keyboard.press("ArrowLeft")
        page.keyboard.press("ArrowLeft")
        page.keyboard.press("ArrowLeft")  # stops at the first slide
        assert "Slide 1 of 3" in page.inner_text("[data-testid=slide-modal]")
        assert "Welcome everyone." in page.inner_text("[data-testid=slide-notes]")
        page.keyboard.press("Escape")
        page.wait_for_selector("[data-testid=slide-modal]", state="detached")
        assert page.problems == []  # type: ignore[attr-defined]
        browser.close()  # type: ignore[attr-defined]


def test_a_deck_in_the_files_tab_shows_its_slides_and_notes(
    live_server: LiveServer,  # noqa: F811
    workspace: Workspace,  # noqa: F811
) -> None:
    deck = make_deck(workspace)
    make_pictures(workspace)
    artifacts = REPO_ROOT / "test-artifacts" / "react-ui"
    artifacts.mkdir(parents=True, exist_ok=True)
    with playwright_api.sync_playwright() as p:
        browser, page = open_in_edge(p, live_server, workspace)
        page.click("[role=tab]:has-text('Files')")
        page.wait_for_selector(f"[role=tabpanel] button:has-text('{deck}')")
        page.click(f"[role=tabpanel] button:has-text('{deck}')")
        page.wait_for_selector("[data-testid=slide-viewer]")
        assert "Slide 1 of 3" in page.inner_text("[data-testid=deck-panel]")
        assert "Welcome everyone." in page.inner_text("[data-testid=slide-notes]")
        page.click("[data-testid=deck-panel] button[aria-label='Go to slide 2']")
        page.wait_for_function(
            "document.querySelector('[data-testid=slide-notes]').innerText.includes('Say thanks.')"
        )
        page.screenshot(path=str(artifacts / "slides-files-tab.png"))
        assert page.problems == []  # type: ignore[attr-defined]
        browser.close()  # type: ignore[attr-defined]


def test_the_slides_route_is_narrow_and_reports_what_exists(
    live_server: LiveServer,  # noqa: F811
    workspace: Workspace,  # noqa: F811
) -> None:
    import httpx

    deck = make_deck(workspace)
    base = f"http://127.0.0.1:{live_server.security.port}"
    client = httpx.Client(
        base_url=base, cookies={live_server.security.cookie_name: live_server.security.token}
    )
    token = {"t": live_server.security.token}
    assert client.post("/api/open", params=token, json={"workspace": str(workspace.root)}).status_code == 200
    bare = client.get("/api/slides", params={"root": "repo", "path": deck, **token}).json()
    assert bare["pictures"] == [] and bare["notes"] == ["Welcome everyone.", "Say thanks.", ""]
    names = make_pictures(workspace)
    shown = client.get("/api/slides", params={"root": "repo", "path": deck, **token}).json()
    assert shown["pictures"] == names and shown["deck"] == "deck.pptx"
    (workspace.root / "notes.txt").write_text("x", encoding="utf-8")
    for path, root, status in [
        ("notes.txt", "repo", 404),  # not a presentation
        ("../outside.pptx", "repo", 403),
        ("missing.pptx", "repo", 404),
        (deck, "elsewhere", 400),
    ]:
        reply = client.get("/api/slides", params={"root": root, "path": path, **token})
        assert reply.status_code == status, (path, root, reply.status_code)

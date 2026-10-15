"""D-253: the picture DebCraft looks at is shown in the chat (click to enlarge), served by a narrow, safe route."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

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

pytestmark = pytest.mark.e2e


def tiny_png(width: int = 320, height: int = 200) -> bytes:
    """A real PNG (red to blue gradient) built without Pillow, so the browser can decode and show it."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    rows = b"".join(
        b"\x00" + bytes(v for x in range(width) for v in (200 - x * 200 // width, 40, 60 + x * 190 // width))
        for _ in range(height)
    )
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def test_the_image_the_model_looks_at_appears_in_the_chat_and_enlarges(
    live_server: LiveServer,  # noqa: F811
    workspace: Workspace,  # noqa: F811
) -> None:
    shots = workspace.forge_dir / "screenshots"
    shots.mkdir(parents=True, exist_ok=True)
    (shots / "shot-test.png").write_bytes(tiny_png(320, 700))
    artifacts = REPO_ROOT / "test-artifacts" / "react-ui"
    artifacts.mkdir(parents=True, exist_ok=True)
    with playwright_api.sync_playwright() as p:
        browser, page = open_in_edge(p, live_server, workspace)
        live_server.publish(
            EventType.NOTICE,
            {
                "kind": "image_sent",
                "text": "Image sent to the vision model: .forge/screenshots/shot-test.png (sha256 ab12, 320x200)",
                "path": ".forge/screenshots/shot-test.png",
            },
        )
        page.wait_for_selector("[data-testid=chat-image] img")
        shown = page.evaluate("document.querySelector('[data-testid=chat-image] img').naturalWidth")
        assert shown == 320  # the browser really decoded the picture served by /api/image
        assert (
            page.evaluate(
                "document.querySelector('[data-testid=chat-image] img').getBoundingClientRect().height"
            )
            <= 290
        )  # tall shots are cropped
        page.screenshot(path=str(artifacts / "chat-image-thumbnail.png"))
        page.click("[data-testid=chat-image]")
        page.wait_for_selector("[data-testid=chat-image-large]")
        page.screenshot(path=str(artifacts / "chat-image-enlarged.png"))
        page.keyboard.press("Escape")
        page.wait_for_selector("[data-testid=chat-image-large]", state="detached")
        # a screenshot notice shows its picture too
        live_server.publish(
            EventType.NOTICE,
            {
                "kind": "screenshot",
                "text": "Screenshot saved: shot-test.png",
                "path": ".forge/screenshots/shot-test.png",
            },
        )
        for _ in range(
            100
        ):  # a locator count, not wait_for_function: the page's CSP forbids the eval that function needs
            if page.locator("[data-testid=chat-image]").count() == 2:
                break
            page.wait_for_timeout(100)
        assert page.locator("[data-testid=chat-image]").count() == 2
        assert page.problems == []  # type: ignore[attr-defined]
        browser.close()  # type: ignore[attr-defined]


def test_the_image_route_only_serves_images_inside_the_workspace(
    live_server: LiveServer,  # noqa: F811
    workspace: Workspace,  # noqa: F811
    tmp_path: Path,
) -> None:
    import httpx

    shots = workspace.forge_dir / "screenshots"
    shots.mkdir(parents=True, exist_ok=True)
    (shots / "ok.png").write_bytes(tiny_png(8, 8))
    (workspace.root / "notes.txt").write_text("not an image", encoding="utf-8")
    (workspace.root / ".env").write_text("KEY=1", encoding="utf-8")
    outside = tmp_path / "outside.png"
    outside.write_bytes(tiny_png(8, 8))
    base = f"http://127.0.0.1:{live_server.security.port}"
    client = httpx.Client(
        base_url=base, cookies={live_server.security.cookie_name: live_server.security.token}
    )
    token = {"t": live_server.security.token}
    opened = client.post("/api/open", params=token, json={"workspace": str(workspace.root)})
    assert opened.status_code == 200, opened.text
    ok = client.get("/api/image", params={"path": ".forge/screenshots/ok.png", **token})
    assert ok.status_code == 200 and ok.headers["content-type"] == "image/png"
    for path, status in [
        ("notes.txt", 403),  # not an image type
        ("../outside.png", 403),  # outside the workspace
        (str(outside), 403),  # an absolute path elsewhere
        (".forge/screenshots/missing.png", 404),
    ]:
        reply = client.get("/api/image", params={"path": path, **token})
        assert reply.status_code == status, (path, reply.status_code)


def test_a_question_option_shows_its_picture(
    live_server: LiveServer,  # noqa: F811
    workspace: Workspace,  # noqa: F811
) -> None:
    """Showing candidate designs before building (D-430): an option of the question card carries a picture."""
    folder = workspace.forge_dir / "candidates"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "specimen-a.png").write_bytes(tiny_png(480, 300))
    (folder / "specimen-b.png").write_bytes(tiny_png(480, 300))
    artifacts = REPO_ROOT / "test-artifacts" / "react-ui"
    artifacts.mkdir(parents=True, exist_ok=True)
    with playwright_api.sync_playwright() as p:
        browser, page = open_in_edge(p, live_server, workspace)
        live_server.publish(
            EventType.QUESTION_ASKED,
            {
                "id": "Q-designs",
                "question": "Which direction should the studio site take?",
                "context": "Two looks drawn from your brief.",
                "options": [
                    {
                        "label": "Warm and handmade",
                        "description": "Serif, terracotta.",
                        "image": ".forge/candidates/specimen-a.png",
                    },
                    {
                        "label": "Dark and bold",
                        "description": "Grotesk, amber.",
                        "image": ".forge/candidates/specimen-b.png",
                    },
                ],
                "recommended": "Warm and handmade",
            },
        )
        page.wait_for_selector("text=Which direction should the studio site take?")
        page.wait_for_function(
            "document.querySelectorAll('[role=radio] img').length === 2 && [...document.querySelectorAll('[role=radio] img')].every(i => i.naturalWidth === 480)"
        )
        page.screenshot(path=str(artifacts / "question-with-pictures.png"))
        browser.close()

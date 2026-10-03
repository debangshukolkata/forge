"""D-203: the `ocr_image` tool and when it is offered. The OCR tests run the real Tesseract and are
skipped on a machine without it; the gating tests need no Tesseract."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from forge.engine.session_host import SessionHost
from forge.environment import checks, store
from forge.protocol.events import EventBus
from forge.safety.redact import Redactor
from forge.safety.server_security import ServerSecurity
from forge.toolkit.base import ToolContext
from forge.tools.vision import OcrImage
from forge.vision import ocr
from forge.web.manager import WebSessionManager
from forge.web.server import create_app
from forge.workspace.create import create_workspace
from forge.workspace.workspace import Workspace
from tests.helpers import mocked_router

needs_tesseract = pytest.mark.skipif(ocr.find_tesseract() is None, reason="Tesseract is not installed here")
SIGNATURE = "def mask_pan(pan: str) -> str:"


def picture(*lines: str, size: tuple[int, int] = (1100, 360)) -> Image.Image:
    image = Image.new("L", size, 255)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=44)
    for number, line in enumerate(lines):
        draw.text((30, 30 + number * 150), line, fill=0, font=font)
    return image


@pytest.fixture
def workspace(original_repo: Path, tmp_path: Path) -> Workspace:
    return create_workspace(original_repo, tmp_path / "ws", "backend")


def saved(workspace: Workspace, name: str, image: Image.Image) -> str:
    folder = workspace.forge_dir / "inputs"
    folder.mkdir(parents=True, exist_ok=True)
    image.save(folder / name)
    return f".forge/inputs/{name}"


async def ocr_of(workspace: Workspace, **arguments: object) -> tuple[bool, str]:
    result = await OcrImage().run(OcrImage.Args(**arguments), ToolContext(workspace=workspace))  # type: ignore[arg-type]
    return result.ok, result.content


@needs_tesseract
async def test_it_reads_the_exact_text_of_a_screenshot(workspace: Workspace) -> None:
    path = saved(workspace, "signature.png", picture(SIGNATURE))
    ok, text = await ocr_of(workspace, path=path)
    assert ok and "mask_pan" in text and "pan: str" in text and "look-alike" in text


@needs_tesseract
async def test_a_region_reads_only_that_part(workspace: Workspace) -> None:
    path = saved(workspace, "two.png", picture("first_line_here", "second_line_there", size=(1100, 380)))
    ok, top = await ocr_of(workspace, path=path, region=[0, 0, 1100, 130], layout="block")
    assert ok and "first" in top and "second" not in top
    ok, bottom = await ocr_of(workspace, path=path, region=[0, 150, 1100, 380], layout="block")
    assert ok and "second" in bottom and "first" not in bottom


@needs_tesseract
async def test_it_reads_a_pdf_page_by_page(workspace: Workspace) -> None:
    pdf_path = workspace.forge_dir / "inputs" / "doc.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    first, second = picture("alpha_page_one"), picture("beta_page_two")
    first.convert("RGB").save(pdf_path, save_all=True, append_images=[second.convert("RGB")])

    ok, text = await ocr_of(workspace, path=".forge/inputs/doc.pdf")
    assert ok and "--- page 1 of 2 ---" in text and "--- page 2 of 2 ---" in text
    assert "alpha" in text and "beta" in text
    ok, only_second = await ocr_of(workspace, path=".forge/inputs/doc.pdf", pages=[2])
    assert ok and "beta" in only_second and "alpha" not in only_second


@needs_tesseract
async def test_a_blank_image_says_so(workspace: Workspace) -> None:
    path = saved(workspace, "blank.png", Image.new("L", (900, 300), 255))
    ok, text = await ocr_of(workspace, path=path)
    assert ok and text.startswith("No text was read")


async def test_bad_requests_become_clear_errors(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ocr, "find_tesseract", lambda: "tesseract-fake")
    path = saved(workspace, "small.png", picture("x"))
    assert await ocr_of(workspace, path=".forge/inputs/missing.png") == (
        False,
        ".forge/inputs/missing.png does not exist.",
    )
    ok, text = await ocr_of(workspace, path=path, region=[10, 10, 5, 5])
    assert not ok and "empty" in text
    ok, text = await ocr_of(workspace, path=path, region=[1, 2, 3])
    assert not ok and "four numbers" in text
    ok, text = await ocr_of(workspace, path=path, language="eng; rm -rf")
    assert not ok and "language" in text
    ok, text = await ocr_of(workspace, path=".forge/other/x.png")
    assert not ok and "Only .forge" in text
    (workspace.repo_dir / ".env").write_text("A=1\n", encoding="utf-8")
    ok, text = await ocr_of(workspace, path=".env")
    assert not ok and "Secret files" in text


async def test_without_tesseract_the_tool_explains(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ocr, "find_tesseract", lambda: None)
    ok, text = await ocr_of(workspace, path="anything.png")
    assert not ok and "Environment panel" in text


# --- when the tool is offered ---


def test_ready_needs_a_yes_and_a_passing_test(tmp_path: Path) -> None:
    assert store.tesseract_ready(tmp_path) is False
    store.save_answer(tmp_path, "tesseract", True)
    assert store.tesseract_ready(tmp_path) is False  # yes, but never tested
    store.save_result(tmp_path, "tesseract", {"status": "warn"})
    assert store.tesseract_ready(tmp_path) is False
    store.save_result(tmp_path, "tesseract", {"status": "ok"})
    assert store.tesseract_ready(tmp_path) is True
    store.save_answer(tmp_path, "tesseract", False)
    assert store.tesseract_ready(tmp_path) is False


def unreachable(request: object) -> object:
    raise AssertionError("no LLM call expected")


def host_for(workspace: Workspace) -> SessionHost:
    return SessionHost(mocked_router(unreachable), EventBus(redactor=Redactor()), workspace=workspace)


def test_a_new_session_gets_the_tool_only_when_it_is_ready(
    workspace: Workspace, isolated_forge_home: Path
) -> None:
    assert host_for(workspace).agent.tools.get("ocr_image") is None  # type: ignore[union-attr]
    store.save_answer(isolated_forge_home, "tesseract", True)
    store.save_result(isolated_forge_home, "tesseract", {"status": "ok"})
    tool = host_for(workspace).agent.tools.get("ocr_image")  # type: ignore[union-attr]
    assert tool is not None and tool.read_only  # read-only: it works in plan mode too


@pytest.fixture
def web(isolated_forge_home: Path) -> Iterator[tuple[TestClient, WebSessionManager]]:
    security = ServerSecurity(port=8796, token="test-token-0123456789")  # check_secrets: fake
    manager = WebSessionManager(isolated_forge_home, lambda ws: host_for(ws))
    with TestClient(create_app(manager, security), base_url="http://127.0.0.1:8796") as client:
        client.get(f"/?t={security.token}", follow_redirects=False)
        yield client, manager


def test_the_drawer_gives_and_takes_the_tool_in_the_open_session(
    web: tuple[TestClient, WebSessionManager],
    isolated_forge_home: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from forge.modeb.profile import ProfileStore

    client, manager = web
    origin = {"origin": "http://127.0.0.1:8796"}
    ProfileStore(isolated_forge_home).create("web-host")
    client.post("/api/standalone", json={"workspace": str(tmp_path / "wsb"), "profile": "web-host"})
    assert manager.host is not None and manager.host.agent is not None
    tools = manager.host.agent.tools
    assert tools.get("ocr_image") is None

    monkeypatch.setattr(checks, "check_tesseract", lambda: checks.Outcome("tesseract", "ok", "fake ok"))
    client.post("/api/environment/answer", json={"check": "tesseract", "enabled": True}, headers=origin)
    assert tools.get("ocr_image") is None  # a yes alone is not enough: it has to pass its test
    client.post("/api/environment/check/tesseract", headers=origin)
    assert tools.get("ocr_image") is not None
    client.post("/api/environment/answer", json={"check": "tesseract", "enabled": False}, headers=origin)
    assert tools.get("ocr_image") is None  # a no takes it away at once


def test_tesseract_is_found_on_path_or_in_the_windows_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/tesseract")
    assert ocr.find_tesseract() == "/usr/bin/tesseract"
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr(ocr.Path, "exists", lambda self: False)
    assert ocr.find_tesseract() is None

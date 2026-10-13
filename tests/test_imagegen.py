"""D5 (D-326): generate_image calls the Azure image deployment; the network is mocked at the transport, the settings come from the .env."""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import httpx2
import pytest
from PIL import Image

from forge.config import Secrets
from forge.toolkit.base import ToolContext
from forge.tools import imagegen
from forge.tools.imagegen import GenerateImage
from forge.workspace.create import create_workspace


def _png() -> str:
    out = io.BytesIO()
    Image.new("RGB", (8, 8), (200, 40, 40)).save(out, "PNG")
    return base64.b64encode(out.getvalue()).decode()


SECRETS = {
    "AZURE_OPENAI_ENDPOINT": "https://main.openai.azure.com/",
    "AZURE_OPENAI_API_KEY": "main-key-0123456789",  # check_secrets: fake
    "AZURE_IMAGE_DEPLOYMENT": "aicloud-dall-e-3",
    "AZURE_IMAGE_API_VERSION": "2023-12-01-preview",
}


def _context(original_repo: Path, tmp_path: Path, secrets: dict[str, str]) -> ToolContext:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    return ToolContext(workspace=workspace, secrets=Secrets(secrets, None))


def _mock(monkeypatch: pytest.MonkeyPatch, handler) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        imagegen, "http_client", lambda: httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    )


async def test_a_picture_is_requested_from_the_deployment_and_saved(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict = {}  # type: ignore[type-arg]

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["url"], seen["body"], seen["key"] = (
            str(request.url),
            json.loads(request.content),
            request.headers.get("api-key"),
        )
        return httpx2.Response(
            200,
            json={"created": 1, "data": [{"b64_json": _png(), "revised_prompt": "A red square, detailed"}]},
        )

    _mock(monkeypatch, handler)
    context = _context(original_repo, tmp_path, SECRETS)
    result = await GenerateImage().run(
        GenerateImage.Args(
            prompt="A flat illustration of a vineyard at dawn, no text", path="assets/hero.png"
        ),
        context,
    )
    assert result.ok, result.content
    assert (
        "/openai/deployments/aicloud-dall-e-3/images/generations" in seen["url"]
        and "api-version=2023-12-01-preview" in seen["url"]
    )
    assert (
        seen["body"]["size"] == "1792x1024"
        and seen["body"]["style"] == "natural"
        and seen["key"] == SECRETS["AZURE_OPENAI_API_KEY"]
    )
    assert Image.open(context.workspace.path_of("assets/hero.png")).size == (8, 8)
    assert "rewrote the prompt" in result.content and context.images_generated == 1


async def test_a_separate_resource_and_key_are_used_when_given(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict = {}  # type: ignore[type-arg]

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["host"], seen["key"] = request.url.host, request.headers.get("api-key")
        return httpx2.Response(200, json={"created": 1, "data": [{"b64_json": _png()}]})

    _mock(monkeypatch, handler)
    secrets = {
        **SECRETS,
        "AZURE_IMAGE_ENDPOINT": "https://images.openai.azure.com/",
        "AZURE_IMAGE_API_KEY": "image-key-0123456789",
    }  # check_secrets: fake
    result = await GenerateImage().run(
        GenerateImage.Args(prompt="A mountain lake at sunrise, soft light", path="a.png", shape="square"),
        _context(original_repo, tmp_path, secrets),
    )
    assert result.ok and seen == {"host": "images.openai.azure.com", "key": "image-key-0123456789"}


async def test_without_settings_the_tool_explains_what_to_add(original_repo: Path, tmp_path: Path) -> None:
    result = await GenerateImage().run(
        GenerateImage.Args(prompt="A mountain lake at sunrise", path="a.png"),
        _context(original_repo, tmp_path, {}),
    )
    assert not result.ok and "AZURE_IMAGE_DEPLOYMENT" in result.content and "SVG" in result.content


async def test_the_content_filter_and_other_failures_become_plain_messages(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _context(original_repo, tmp_path, SECRETS)
    args = GenerateImage.Args(prompt="A mountain lake at sunrise", path="a.png")
    _mock(
        monkeypatch,
        lambda r: httpx2.Response(
            400, json={"error": {"code": "content_policy_violation", "message": "content management policy"}}
        ),
    )
    refused = await GenerateImage().run(args, context)
    assert not refused.ok and "content filter" in refused.content
    _mock(monkeypatch, lambda r: httpx2.Response(401, json={"error": {"message": "bad key"}}))
    denied = await GenerateImage().run(args, context)
    assert not denied.ok and "401" in denied.content
    _mock(
        monkeypatch,
        lambda r: httpx2.Response(
            410, json={"error": {"code": 410, "message": "deprecated", "responseCode": "ModelDeprecated"}}
        ),
    )
    retired = await GenerateImage().run(args, context)
    assert not retired.ok and "retired" in retired.content and "AZURE_IMAGE_DEPLOYMENT" in retired.content
    _mock(monkeypatch, lambda r: httpx2.Response(200, json={"created": 1, "data": []}))
    empty = await GenerateImage().run(args, context)
    assert not empty.ok and "no picture" in empty.content
    assert not context.workspace.path_of("a.png").exists()


async def test_the_prompt_is_redacted_the_path_checked_and_the_session_capped(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        sent.append(json.loads(request.content)["prompt"])
        return httpx2.Response(200, json={"created": 1, "data": [{"b64_json": _png()}]})

    _mock(monkeypatch, handler)
    context = _context(original_repo, tmp_path, SECRETS)
    fake = "sk-" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4"  # check_secrets: fake
    await GenerateImage().run(
        GenerateImage.Args(prompt=f"A lake, label it {fake} in the corner", path="a.png"), context
    )
    assert fake not in sent[0]
    bad = await GenerateImage().run(
        GenerateImage.Args(prompt="A mountain lake at sunrise", path="a.jpg"), context
    )
    assert not bad.ok and ".png" in bad.content
    context.images_generated = imagegen.MAX_PER_SESSION
    capped = await GenerateImage().run(
        GenerateImage.Args(prompt="A mountain lake at sunrise", path="b.png"), context
    )
    assert not capped.ok and "this session" in capped.content

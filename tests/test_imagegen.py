"""D5 (D-327): generate_image uses Gemini or Imagen on Vertex AI. The SDK client is replaced by one that answers with real SDK response
types (the network is simulated, not the model); a live check is `scripts/dev/image_smoke.py` on a machine with Google credentials."""

from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from google.genai import errors, types
from PIL import Image

from forge.config import Secrets
from forge.toolkit.base import ToolContext
from forge.tools import imagegen
from forge.tools.imagegen import GenerateImage
from forge.workspace.create import create_workspace


def _png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (8, 8), (200, 40, 40)).save(out, "PNG")
    return out.getvalue()


class _Models:
    def __init__(self, behaviour: Any) -> None:
        self.behaviour, self.calls = behaviour, []

    async def generate_content(self, **kwargs: Any) -> Any:
        self.calls.append(("content", kwargs))
        return self.behaviour(kwargs)

    async def generate_images(self, **kwargs: Any) -> Any:
        self.calls.append(("images", kwargs))
        return self.behaviour(kwargs)


def _client(monkeypatch: pytest.MonkeyPatch, behaviour: Any) -> _Models:
    models = _Models(behaviour)
    monkeypatch.setattr(
        imagegen, "make_client", lambda secrets: SimpleNamespace(aio=SimpleNamespace(models=models))
    )
    return models


def _gemini_answer(data: bytes | None) -> types.GenerateContentResponse:
    parts = (
        [types.Part(inline_data=types.Blob(data=data, mime_type="image/png"))]
        if data
        else [types.Part(text="I cannot do that")]
    )
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=parts))]
    )


def _context(original_repo: Path, tmp_path: Path, values: dict[str, str] | None = None) -> ToolContext:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    return ToolContext(workspace=workspace, secrets=Secrets(values or {}, None))


ARGS = {"prompt": "A flat illustration of a vineyard at dawn, no text", "path": "assets/hero.png"}


async def test_gemini_is_asked_for_an_image_and_the_picture_is_saved(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    models = _client(monkeypatch, lambda kwargs: _gemini_answer(_png()))
    context = _context(original_repo, tmp_path)
    result = await GenerateImage().run(GenerateImage.Args(**ARGS), context)
    assert result.ok, result.content
    kind, call = models.calls[0]
    assert kind == "content" and call["model"] == "gemini-2.5-flash-image"
    assert (
        call["config"].response_modalities == ["IMAGE"] and call["config"].image_config.aspect_ratio == "16:9"
    )
    assert (
        Image.open(context.workspace.path_of("assets/hero.png")).size == (8, 8)
        and context.images_generated == 1
    )


async def test_the_model_comes_from_the_env_file_and_imagen_uses_its_own_call(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    answer = types.GenerateImagesResponse(
        generated_images=[types.GeneratedImage(image=types.Image(image_bytes=_png(), mime_type="image/png"))]
    )
    models = _client(monkeypatch, lambda kwargs: answer)
    context = _context(original_repo, tmp_path, {"GEMINI_IMAGE_MODEL": "imagen-4.0-generate-001"})
    result = await GenerateImage().run(GenerateImage.Args(**ARGS, shape="portrait"), context)
    assert result.ok, result.content
    kind, call = models.calls[0]
    assert (
        kind == "images"
        and call["model"] == "imagen-4.0-generate-001"
        and call["config"].aspect_ratio == "9:16"
    )


async def test_a_jpg_path_gets_a_jpeg(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _client(monkeypatch, lambda kwargs: _gemini_answer(_png()))
    context = _context(original_repo, tmp_path)
    result = await GenerateImage().run(GenerateImage.Args(prompt=ARGS["prompt"], path="a.jpg"), context)
    assert result.ok and Image.open(context.workspace.path_of("a.jpg")).format == "JPEG"


async def test_a_refusal_an_empty_answer_and_sdk_errors_become_plain_messages(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _context(original_repo, tmp_path)
    _client(monkeypatch, lambda kwargs: _gemini_answer(None))
    refused = await GenerateImage().run(GenerateImage.Args(**ARGS), context)
    assert not refused.ok and "no picture" in refused.content

    def denied(kwargs: Any) -> Any:
        raise errors.ClientError(
            403,
            {
                "error": {
                    "code": 403,
                    "message": "Permission denied on project",
                    "status": "PERMISSION_DENIED",
                }
            },
        )

    _client(monkeypatch, denied)
    failed = await GenerateImage().run(GenerateImage.Args(**ARGS), context)
    assert not failed.ok and "gemini-2.5-flash-image" in failed.content and "SVG" in failed.content
    assert not context.workspace.path_of("assets/hero.png").exists() and context.images_generated == 0


async def test_a_missing_project_says_where_to_add_it(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_project(secrets: Any) -> Any:
        raise ValueError("Project was not found in the credentials.")

    monkeypatch.setattr(imagegen, "make_client", no_project)
    result = await GenerateImage().run(GenerateImage.Args(**ARGS), _context(original_repo, tmp_path))
    assert not result.ok and "GOOGLE_CLOUD_PROJECT" in result.content


async def test_the_prompt_is_redacted_the_path_checked_and_the_session_capped(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    models = _client(monkeypatch, lambda kwargs: _gemini_answer(_png()))
    context = _context(original_repo, tmp_path)
    fake = "sk-" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4"  # check_secrets: fake
    await GenerateImage().run(
        GenerateImage.Args(prompt=f"A lake, label it {fake} in the corner", path="a.png"), context
    )
    assert fake not in models.calls[0][1]["contents"]
    bad = await GenerateImage().run(GenerateImage.Args(prompt=ARGS["prompt"], path="a.gif"), context)
    assert not bad.ok and ".png" in bad.content
    context.images_generated = imagegen.MAX_PER_SESSION
    capped = await GenerateImage().run(GenerateImage.Args(**ARGS), context)
    assert not capped.ok and "this session" in capped.content

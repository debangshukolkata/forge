"""generate_image (TODO D5, D-326, D-327): a picture made by a Gemini or Imagen model on Vertex AI, saved in the project.

Vertex AI through the google-genai SDK, authenticated by Application Default Credentials like the Gemini chat provider (DebCraft never
stores Google credentials). The project and region come from GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION in the .env file (both
optional); GEMINI_IMAGE_MODEL names the model (default `gemini-2.5-flash-image`; a name starting with `imagen` uses the Imagen API
instead). Azure image deployments are not used. The prompt is redacted before it leaves the machine, the picture is written through
the workspace (jail and checkpoints), and refusals and failures are reported as plain messages."""

from __future__ import annotations

import io
from typing import Any, Literal

from pydantic import Field

from forge.llm.gemini_errors import SDK_ERRORS, map_gemini_error
from forge.safety.redact import Redactor
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult

MODEL_ENV = "GEMINI_IMAGE_MODEL"
PROJECT_ENV = "GOOGLE_CLOUD_PROJECT"
LOCATION_ENV = "GOOGLE_CLOUD_LOCATION"
DEFAULT_MODEL = "gemini-2.5-flash-image"
DEFAULT_LOCATION = "us-central1"
TIMEOUT_MS = 120_000
MAX_PROMPT = 4000
RATIOS = {"landscape": "16:9", "square": "1:1", "portrait": "9:16"}
MAX_PER_SESSION = 12  # each picture costs money and seconds; a runaway loop stops here
NO_PICTURE = "The image model returned no picture (its safety filter may have refused the description): reword it and try once more."


def model_name(secrets: Any) -> str:
    return (secrets.get(MODEL_ENV) if secrets is not None else None) or DEFAULT_MODEL


def default_location(secrets: Any) -> str:
    """The Gemini 3 image models are served only from `global`; the older ones and Imagen keep the region that worked before (D-403)."""
    return "global" if model_name(secrets).startswith("gemini-3") else DEFAULT_LOCATION


def make_client(secrets: Any) -> Any:
    """The Vertex AI client; tests replace this (the network is what they simulate, not the model)."""
    from google import genai
    from google.genai import types

    return genai.Client(
        vertexai=True,
        project=secrets.get(PROJECT_ENV) if secrets is not None else None,
        location=(secrets.get(LOCATION_ENV) if secrets is not None else None) or default_location(secrets),
        http_options=types.HttpOptions(timeout=TIMEOUT_MS, retry_options=types.HttpRetryOptions(attempts=1)),
    )


class GenerateImage(Tool):
    name = "generate_image"
    read_only = False
    description = (
        "Make a picture from a text description with Google's image model on Vertex AI and save it in the project, for a slide, a web "
        "page or a document. Describe the subject, style, mood, colours and composition; ask for no text in the picture unless it is a "
        "few short words. Landscape (16:9) fits slides and hero images, square for cards, portrait for tall layouts. Look at the result "
        "with view_image before using it, write real alt text, and say in the deliverable that the picture is AI-generated. Not for "
        "logos, charts, diagrams or screenshots (draw those) and not for real people or brands."
    )

    class Args(ToolArgs):
        prompt: str = Field(
            min_length=10, max_length=MAX_PROMPT, description="What the picture shows, in detail"
        )
        path: str = Field(description="Where to save it, a .png or .jpg in the project, e.g. assets/hero.png")
        shape: Literal["landscape", "square", "portrait"] = "landscape"

    def summary(self, args: GenerateImage.Args) -> str:
        return f"generate image {args.path}"

    async def run(self, args: GenerateImage.Args, context: ToolContext) -> ToolResult:
        suffix = args.path.lower().rsplit(".", 1)[-1]
        if suffix not in ("png", "jpg", "jpeg"):
            return ToolResult(ok=False, content="Save the picture as a .png or .jpg.")
        used = context.images_generated
        if used >= MAX_PER_SESSION:
            return ToolResult(
                ok=False,
                content=f"{MAX_PER_SESSION} pictures were made in this session: use those or ask the user.",
            )
        model = model_name(context.secrets)
        prompt = Redactor().redact(args.prompt)
        try:
            data = await self._generate(make_client(context.secrets), model, prompt, RATIOS[args.shape])
        except SDK_ERRORS as error:
            return ToolResult(
                ok=False,
                content=f"{map_gemini_error(error)} (image model {model}). Meanwhile draw the picture as SVG or use find_asset.",
            )
        except ValueError as error:  # the SDK found no project in the credentials or the .env file
            return ToolResult(
                ok=False,
                content=f"{error} Add {PROJECT_ENV} to the DebCraft .env file, or use Google credentials that name a project.",
            )
        if isinstance(data, str):
            return ToolResult(ok=False, content=data)
        picture = _as_format(data, suffix)
        context.workspace.write_bytes(args.path, picture, "picture generated by the image model")
        context.images_generated = used + 1
        return ToolResult(
            ok=True,
            content=f"Saved {args.path} ({len(picture) // 1024} KB, {model}, {RATIOS[args.shape]}). Look at it with view_image before using it.",
        )

    @staticmethod
    async def _generate(client: Any, model: str, prompt: str, ratio: str) -> bytes | str:
        """The picture's bytes, or a message saying why there is none."""
        from google.genai import types

        if model.startswith("imagen"):
            result = await client.aio.models.generate_images(
                model=model,
                prompt=prompt,
                config=types.GenerateImagesConfig(number_of_images=1, aspect_ratio=ratio),
            )
            images = result.generated_images or []
            if not images or images[0].image is None or not images[0].image.image_bytes:
                return NO_PICTURE
            return bytes(images[0].image.image_bytes)
        response = await client.aio.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"], image_config=types.ImageConfig(aspect_ratio=ratio)
            ),
        )
        for candidate in response.candidates or []:
            parts = candidate.content.parts if candidate.content and candidate.content.parts else []
            for part in parts:
                if part.inline_data is not None and part.inline_data.data:
                    return bytes(part.inline_data.data)
        return NO_PICTURE


def _as_format(data: bytes, suffix: str) -> bytes:
    """The bytes in the format the path asks for (the model usually answers with PNG)."""
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as picture:
            wanted = "JPEG" if suffix in ("jpg", "jpeg") else "PNG"
            if picture.format == wanted:
                return data
            out = io.BytesIO()
            picture.convert("RGB" if wanted == "JPEG" else picture.mode).save(out, wanted)
            return out.getvalue()
    except Exception:  # unusual data is better saved as it came than lost
        return data


def imagegen_tools() -> list[Tool]:
    return [GenerateImage()]

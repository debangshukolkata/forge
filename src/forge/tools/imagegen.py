"""generate_image (TODO D5, D-326): a picture made by the company's Azure DALL-E 3 deployment, saved in the project.

Settings come from the user's .env file (never typed into the app): AZURE_IMAGE_DEPLOYMENT (the deployment name) and
AZURE_IMAGE_API_VERSION are required; AZURE_IMAGE_ENDPOINT and AZURE_IMAGE_API_KEY default to the main AZURE_OPENAI_ENDPOINT and
AZURE_OPENAI_API_KEY (same resource). The prompt is redacted before it leaves the machine, the picture is written through the
workspace (jail and checkpoints), and DALL-E 3's own content filter is reported as a plain message."""

from __future__ import annotations

import base64
from typing import Literal

import httpx2  # the openai SDK's HTTP client (a maintained httpx fork)
from pydantic import Field

from forge.safety.redact import Redactor
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult

DEPLOYMENT = "AZURE_IMAGE_DEPLOYMENT"
API_VERSION = "AZURE_IMAGE_API_VERSION"
ENDPOINT = "AZURE_IMAGE_ENDPOINT"
API_KEY = "AZURE_IMAGE_API_KEY"
MAIN_ENDPOINT = "AZURE_OPENAI_ENDPOINT"
MAIN_KEY = "AZURE_OPENAI_API_KEY"
TIMEOUT_S = 120.0
MAX_PROMPT = 4000  # DALL-E 3 accepts 4000 characters
SIZES = {"landscape": "1792x1024", "square": "1024x1024", "portrait": "1024x1792"}
MAX_PER_SESSION = 12  # each picture costs money and seconds; a runaway loop stops here


def http_client() -> httpx2.AsyncClient | None:
    """The HTTP client for the call; tests replace this with one on a mock transport (the network, not the model)."""
    return None


def configured(secrets: object) -> bool:
    get = getattr(secrets, "get", None)
    return bool(
        get
        and get(DEPLOYMENT)
        and get(API_VERSION)
        and (get(ENDPOINT) or get(MAIN_ENDPOINT))
        and (get(API_KEY) or get(MAIN_KEY))
    )


class GenerateImage(Tool):
    name = "generate_image"
    read_only = False
    description = (
        "Make a picture from a text description with the company's image model (DALL-E 3) and save it in the project, for a slide, a web "
        "page or a document. Describe the subject, style, mood, colours and composition; ask for no text in the picture (the model "
        "spells badly). Landscape (1792x1024) fits slides and hero images, square for cards, portrait for tall layouts. Look at the "
        "result with view_image before using it, write real alt text, and say in the deliverable that the picture is AI-generated. Not "
        "for logos, charts, diagrams or screenshots (draw those) and not for real people or brands."
    )

    class Args(ToolArgs):
        prompt: str = Field(
            min_length=10, max_length=MAX_PROMPT, description="What the picture shows, in detail"
        )
        path: str = Field(description="Where to save it, a .png in the project, e.g. assets/hero.png")
        shape: Literal["landscape", "square", "portrait"] = "landscape"
        style: Literal["natural", "vivid"] = "natural"
        quality: Literal["standard", "hd"] = "standard"

    def summary(self, args: GenerateImage.Args) -> str:
        return f"generate image {args.path}"

    async def run(self, args: GenerateImage.Args, context: ToolContext) -> ToolResult:
        secrets = context.secrets
        if not configured(secrets):
            return ToolResult(
                ok=False,
                content=(
                    f"No image model is set up. The user adds {DEPLOYMENT} and {API_VERSION} (and, if the image model is on another "
                    f"resource, {ENDPOINT} and {API_KEY}) to the DebCraft .env file. Tell the user; meanwhile draw the picture as SVG "
                    "or use find_asset."
                ),
            )
        if not args.path.lower().endswith(".png"):
            return ToolResult(ok=False, content="Save the picture as a .png.")
        used = getattr(context, "images_generated", 0)
        if used >= MAX_PER_SESSION:
            return ToolResult(
                ok=False,
                content=f"{MAX_PER_SESSION} pictures were made in this session: use those or ask the user.",
            )
        from openai import APIStatusError, AsyncAzureOpenAI, BadRequestError

        client = AsyncAzureOpenAI(
            azure_endpoint=secrets.get(ENDPOINT) or secrets.require(MAIN_ENDPOINT),
            api_key=secrets.get(API_KEY) or secrets.require(MAIN_KEY),
            api_version=secrets.require(API_VERSION),
            timeout=TIMEOUT_S,
            max_retries=1,
            http_client=http_client(),
        )
        prompt = Redactor().redact(args.prompt)
        try:
            response = await client.images.generate(
                model=secrets.require(DEPLOYMENT),
                prompt=prompt,
                size=SIZES[args.shape],
                style=args.style,
                quality=args.quality,
                n=1,
                response_format="b64_json",
            )
        except BadRequestError as error:
            reason = str(error)
            if "content_policy" in reason or "content management policy" in reason:
                return ToolResult(
                    ok=False,
                    content="The image model's content filter refused this description. Reword it without the sensitive part (no real "
                    "people, violence or brands) and try once more.",
                )
            return ToolResult(ok=False, content=f"The image model refused the request: {reason[:300]}")
        except APIStatusError as error:
            if error.status_code == 410 or "ModelDeprecated" in str(error):
                return ToolResult(
                    ok=False,
                    content="Azure says the model behind this image deployment is retired (410 ModelDeprecated). Tell the user: they need a "
                    f"deployment of a current image model, and its name in {DEPLOYMENT}. Meanwhile draw the picture as SVG or use find_asset.",
                )
            return ToolResult(
                ok=False, content=f"The image service answered {error.status_code}: {str(error)[:300]}"
            )
        except Exception as error:  # a network failure: say so, the model can retry or draw instead
            return ToolResult(
                ok=False,
                content=f"The image service could not be reached ({type(error).__name__}). Try again, or draw it as SVG.",
            )
        finally:
            await client.close()
        data = response.data[0] if response.data else None
        if data is None or not data.b64_json:
            return ToolResult(ok=False, content="The image service returned no picture.")
        picture = base64.b64decode(data.b64_json)
        context.workspace.write_bytes(args.path, picture, "picture generated by the image model")
        context.images_generated = used + 1
        revised = getattr(data, "revised_prompt", None) or ""
        return ToolResult(
            ok=True,
            content=(
                f"Saved {args.path} ({len(picture) // 1024} KB, {SIZES[args.shape]}). Look at it with view_image before using it."
                + (f"\nThe model rewrote the prompt as: {revised[:500]}" if revised else "")
            ),
        )


def imagegen_tools() -> list[Tool]:
    return [GenerateImage()]

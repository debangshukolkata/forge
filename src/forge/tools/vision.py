"""Forge's own vision tools (spec §13A.1) — for building and verifying, separate from the vision features of the
code it writes — plus the eval tools (§13A.2-13A.4).

Images reach the model ONLY through view_image (never as base64 in text); every image sent is logged by hash
in the transcript; they go only to the configured `vision` role model (the enterprise Azure endpoint).
Paths: repo-relative, or .forge/inputs|scratch_images|reports|screenshots/... for attached and generated images.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import Field

from forge.errors import ForgeError
from forge.llm.base import ChatRequest, Message
from forge.safety.paths import resolve_inside
from forge.tools.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.vision import images, pdf
from forge.vision.evals import JUDGE_RUBRIC, run_eval
from forge.vision.synthetic import DocumentSpec, generate

FORGE_IMAGE_DIRS = ("inputs", "scratch_images", "reports", "screenshots")
VISION_PROMPT = (
    "You look at an image for a software engineer who is building or checking a document/image pipeline. "
    "Answer precisely; give pixel coordinates [x1, y1, x2, y2] of the image you were sent when asked where "
    "something is; say plainly when something is unreadable or absent instead of guessing."
)


def image_path(context: ToolContext, path: str) -> Path:
    normalised = path.replace("\\", "/")
    if normalised.startswith(".forge/"):
        rest = normalised.removeprefix(".forge/")
        if rest.split("/")[0] not in FORGE_IMAGE_DIRS:
            raise ForgeError(f"Only .forge/{{{','.join(FORGE_IMAGE_DIRS)}}}/ images can be used.")
        return resolve_inside(context.workspace.forge_dir, rest)
    resolved = context.workspace.path_of(normalised)
    if context.workspace.is_secret(normalised):
        raise ForgeError("Secret files are never sent anywhere.")
    return resolved


def _scratch(context: ToolContext) -> Path:
    folder = context.workspace.jail.check(context.workspace.forge_dir / "scratch_images")
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _relative(context: ToolContext, path: Path) -> str:
    return path.resolve().relative_to(context.workspace.root.resolve()).as_posix()


class ViewImage(Tool):
    name = "view_image"
    read_only = True
    description = (
        "Look at an image (or a region [x1,y1,x2,y2] of it) with the vision model and get its answer to a "
        "question. The only way to see images. Paths: repo-relative or .forge/inputs|scratch_images|reports/..."
    )

    class Args(ToolArgs):
        path: str
        question: str = (
            "Describe this image precisely, including any text, and the location of notable regions."
        )
        region: list[float] | None = Field(default=None, description="[x1, y1, x2, y2] in pixels")

    def summary(self, args: ViewImage.Args) -> str:
        return f"view image {args.path}" + (f" {args.region}" if args.region else "")

    async def run(self, args: ViewImage.Args, context: ToolContext) -> ToolResult:
        if context.router is None:
            return ToolResult(ok=False, content="No model is available to look at images here.")
        path = image_path(context, args.path)
        if path.suffix.lower() == ".pdf":
            return ToolResult(
                ok=False, content="Render the PDF first with pdf_render, then view a page image."
            )
        image = images.open_image(path)
        region = tuple(args.region) if args.region and len(args.region) == 4 else None
        url, meta = images.for_model(image, region)  # type: ignore[arg-type]
        await context.emit(
            "notice",
            {
                "kind": "image_sent",
                "text": f"Image sent to the vision model: {args.path} "
                f"(sha256 {meta['sha256']}, {meta['sent_size'][0]}x{meta['sent_size'][1]})",
            },
        )
        scale = f"The image was sent at {meta['sent_size']} (original {meta['original_size']})."
        request = ChatRequest(
            messages=[
                Message.system(VISION_PROMPT),
                Message(role="user", content=f"{args.question}\n\n{scale}", images=[url]),
            ]
        )
        response = await context.router.chat("vision", request)
        note = ""
        if meta["sent_size"] != meta["original_size"] and region is None:
            factor = meta["original_size"][0] / meta["sent_size"][0]
            note = f"\n[coordinates in the answer refer to the sent image; multiply by {factor:.3f} for the original]"
        return ToolResult(ok=True, content=response.text + note)


class PdfRender(Tool):
    name = "pdf_render"
    description = (
        "Render PDF pages to PNG in .forge/scratch_images/ (pypdfium2); tells whether it has a text layer."
    )

    class Args(ToolArgs):
        path: str
        pages: list[int] | None = None
        dpi: int = Field(default=200, ge=72, le=400)

    async def run(self, args: PdfRender.Args, context: ToolContext) -> ToolResult:
        source = image_path(context, args.path)
        written = pdf.render(source, _scratch(context), args.pages, args.dpi)
        text_layer = pdf.has_text_layer(source)
        listing = "\n".join(_relative(context, p) for p in written)
        return ToolResult(
            ok=True,
            content=f"{len(written)} page(s) rendered at {args.dpi} dpi (text layer: {'yes' if text_layer else 'no — image-only PDF'}):\n{listing}",
        )


class ImageInfo(Tool):
    name = "image_info"
    read_only = True
    description = "Size, DPI, mode, EXIF orientation, frame/page count and hash of an image or PDF."

    class Args(ToolArgs):
        path: str

    async def run(self, args: ImageInfo.Args, context: ToolContext) -> ToolResult:
        path = image_path(context, args.path)
        if path.suffix.lower() == ".pdf":
            return ToolResult(
                ok=True,
                content=json.dumps({"pages": pdf.page_count(path), "text_layer": pdf.has_text_layer(path)}),
            )
        return ToolResult(ok=True, content=json.dumps(images.info(path)))


class ImageOps(Tool):
    name = "image_ops"
    description = (
        "Apply operations to a copy of an image and save it in .forge/scratch_images/: crop{box}, rotate{degrees}, "
        "deskew, resize{width|height|scale}, grayscale, threshold{level}, pad{pixels}, autocontrast, sharpen, denoise."
    )

    class Args(ToolArgs):
        path: str
        ops: list[dict[str, Any]]

    async def run(self, args: ImageOps.Args, context: ToolContext) -> ToolResult:
        source = image_path(context, args.path)
        result = images.apply_ops(images.open_image(source), args.ops)
        target = images.save(
            result, _scratch(context) / f"{source.stem}-ops{len(list(_scratch(context).iterdir()))}.png"
        )
        return ToolResult(
            ok=True, content=f"Saved {_relative(context, target)} ({result.width}x{result.height})."
        )


class DrawBoxes(Tool):
    name = "draw_boxes"
    description = (
        "Draw labelled boxes on a copy of an image (to SEE what a detector found); returns the new path."
    )

    class Args(ToolArgs):
        path: str
        boxes: list[dict[str, Any]] = Field(description='[{"box": [x1,y1,x2,y2], "label": "signature"}]')

    async def run(self, args: DrawBoxes.Args, context: ToolContext) -> ToolResult:
        source = image_path(context, args.path)
        drawn = images.draw_boxes(images.open_image(source), args.boxes)
        target = images.save(drawn, _scratch(context) / f"{source.stem}-boxes.png")
        return ToolResult(ok=True, content=f"Saved {_relative(context, target)}; look at it with view_image.")


class CompareImages(Tool):
    name = "compare_images"
    read_only = True
    description = (
        "Side-by-side composite of two images plus their ink-overlap ratio (e.g. a crop vs ground truth)."
    )

    class Args(ToolArgs):
        a: str
        b: str

    async def run(self, args: CompareImages.Args, context: ToolContext) -> ToolResult:
        composite, overlap = images.compare(
            images.open_image(image_path(context, args.a)), images.open_image(image_path(context, args.b))
        )
        target = images.save(composite, _scratch(context) / "compare.png")
        return ToolResult(
            ok=True, content=f"Ink overlap: {overlap:.3f}. Composite: {_relative(context, target)}"
        )


class RunEval(Tool):
    name = "run_eval"
    description = (
        "Run the BUILT system on an eval set (evals/<name>/: eval.yaml command, samples, labels, questions) and "
        "score it against the targets: field match, region IoU/recall, unreadable-respected, answer correctness. "
        "Use subset while iterating (evals call real models and cost money), the full set at milestones."
    )

    class Args(ToolArgs):
        name: str
        subset: int | None = Field(default=None, ge=1)

    async def run(self, args: RunEval.Args, context: ToolContext) -> ToolResult:
        judge = None
        if context.router is not None:
            router = context.router

            async def judge(question: str, expected: str, answer: str) -> str:
                request = ChatRequest(
                    messages=[
                        Message.system(JUDGE_RUBRIC),
                        Message.user(f"Question: {question}\nExpected: {expected}\nAnswer: {answer}"),
                    ]
                )
                return str((await router.chat("judge", request)).text)

        try:
            run = await run_eval(context, args.name, args.subset, judge)
        except ValueError as error:
            return ToolResult(ok=False, content=str(error))
        return ToolResult(ok=not run.misses, content=run.summary())


class SynthSamples(Tool):
    name = "synth_samples"
    description = (
        "Generate synthetic labelled samples into evals/<name>/ for the requirement's document type: spec = "
        '{"title": ..., "fields": {"name": ["value", ...]}, "regions": ["signature", "diagram", "stamp"], '
        '"unreadable_chance": 0.1}. For pipeline tests and regressions — NOT proof of real-world accuracy.'
    )

    class Args(ToolArgs):
        name: str
        spec: dict[str, Any]
        count: int = Field(default=10, ge=1, le=200)
        seed: int = 7

    async def run(self, args: SynthSamples.Args, context: ToolContext) -> ToolResult:
        base = context.workspace.path_of(f"evals/{args.name}")
        context.workspace.jail.check(base)
        written = generate(DocumentSpec.from_dict(args.spec), base, args.count, args.seed)
        context.last_edit_step = context.step
        return ToolResult(
            ok=True,
            content=f"{len(written)} synthetic sample(s) with exact labels in evals/{args.name}/ (marked synthetic).",
        )


def vision_tools() -> list[Tool]:
    return [
        ViewImage(),
        PdfRender(),
        ImageInfo(),
        ImageOps(),
        DrawBoxes(),
        CompareImages(),
        RunEval(),
        SynthSamples(),
    ]

"""Forge's own vision tools (spec §13A.1) — for building and verifying, separate from the vision features of the
code it writes — plus the eval tools (§13A.2-13A.4).

Images reach the model ONLY through view_image (never as base64 in text); every image sent is logged by hash
in the transcript; they go only to the configured `vision` role model (the enterprise Azure endpoint).
Paths: repo-relative, or .forge/inputs|scratch_images|reports|screenshots/... for attached and generated images.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from forge.config import load_secrets
from forge.errors import ForgeError
from forge.llm.base import ChatRequest, Message
from forge.safety.paths import resolve_inside
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.vision import images, ocr, pdf
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


MAX_OCR_PAGES = 10
OCR_PDF_DPI = 300
OCR_CAUTION = "(OCR can confuse look-alike characters such as l/1 and O/0: check anything that matters with view_image.)"


class OcrImage(Tool):
    name = "ocr_image"
    read_only = True  # works on temporary copies outside the workspace; nothing is written there
    description = (
        "Read the exact text in an image or PDF page with Tesseract, on this computer (view_image is the one to "
        "understand what a picture shows). Use it for characters that must be exact: a function signature, "
        "code, numbers or a table in a screenshot. Paths: repo-relative or .forge/inputs|scratch_images|reports/... "
        "For a PDF give the pages (1-based, up to 10); a region [x1,y1,x2,y2] reads only that part of an image."
    )

    class Args(ToolArgs):
        path: str
        pages: list[int] | None = Field(
            default=None, description="PDF pages, 1-based (default: the first 10)"
        )
        region: list[float] | None = Field(default=None, description="[x1, y1, x2, y2] in pixels (images)")
        layout: Literal["page", "block", "line", "word"] = Field(
            default="page", description="page: whole page; block: one block of text; line / word: just that"
        )
        language: str = Field(default="eng", description="Tesseract language code, e.g. eng or eng+deu")

    def summary(self, args: OcrImage.Args) -> str:
        return f"ocr {args.path}" + (f" {args.region}" if args.region else "")

    async def run(self, args: OcrImage.Args, context: ToolContext) -> ToolResult:
        binary = ocr.find_tesseract(load_secrets().get("TESSERACT_CMD"))
        if binary is None:
            return ToolResult(
                ok=False,
                content="Tesseract was not found on this computer. Ask the user to check it in the Environment panel.",
            )
        try:
            source = image_path(context, args.path)
            if not source.is_file():
                return ToolResult(ok=False, content=f"{args.path} does not exist.")
            if source.suffix.lower() == ".pdf":
                text = await asyncio.to_thread(self._read_pdf, binary, source, args)
            else:
                text = await asyncio.to_thread(self._read_image, binary, source, args)
        except (ForgeError, ocr.OcrError, ValueError, OSError) as error:
            return ToolResult(ok=False, content=str(error))
        if not text.strip():
            return ToolResult(
                ok=True,
                content="No text was read. The image may have none, or it is too small or blurry: try a "
                "larger region, or look at it with view_image.",
            )
        return ToolResult(ok=True, content=f"{text}\n\n{OCR_CAUTION}")

    @staticmethod
    def _read_image(binary: str, source: Path, args: OcrImage.Args) -> str:
        image = images.open_image(source)
        if args.region:
            if len(args.region) != 4:
                raise ValueError("region needs four numbers: [x1, y1, x2, y2]")
            x1, y1, x2, y2 = (int(value) for value in args.region)
            box = (max(0, x1), max(0, y1), min(image.width, x2), min(image.height, y2))
            if box[2] <= box[0] or box[3] <= box[1]:
                raise ValueError(
                    f"region {args.region} is empty for an image of {image.width}x{image.height}"
                )
            image = image.crop(box)
        return ocr.read_image(binary, image, args.language, args.layout)

    @staticmethod
    def _read_pdf(binary: str, source: Path, args: OcrImage.Args) -> str:
        total = pdf.page_count(source)
        wanted = args.pages or list(range(1, min(total, MAX_OCR_PAGES) + 1))
        if len(wanted) > MAX_OCR_PAGES:
            raise ValueError(f"at most {MAX_OCR_PAGES} pages at a time")
        parts = []
        with tempfile.TemporaryDirectory() as folder:
            for number, rendered in zip(
                wanted, pdf.render(source, Path(folder), wanted, OCR_PDF_DPI), strict=True
            ):
                text = ocr.read_image(binary, images.open_image(rendered), args.language, args.layout)
                parts.append(f"--- page {number} of {total} ---\n{text}")
        if args.pages is None and total > MAX_OCR_PAGES:
            parts.append(
                f"(only the first {MAX_OCR_PAGES} of {total} pages were read; pass pages for the others)"
            )
        return "\n\n".join(parts)


def ocr_tools() -> list[Tool]:
    """Only offered once the user said Tesseract is installed and the Environment test passed (D-201, D-203)."""
    return [OcrImage()]


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

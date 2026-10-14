"""build_presentation and preview_presentation (D-240): make a real .pptx from an outline, then look at it.

The skill `make-presentation` teaches how to write the outline and how to work: outline, build, preview, fix.
These tools run inside DebCraft itself (python-pptx is DebCraft's optional extra `slides`), so they do not depend on
the project's own Python environment."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from forge.errors import ForgeError
from forge.slides import icons, preview
from forge.slides.accessibility import check_deck
from forge.slides.build import SlidesUnavailable, build_deck
from forge.slides.contact_sheet import ContactSheetUnavailable, make_contact_sheets
from forge.slides.convert import OLD_FORMATS, convert_deck
from forge.slides.design_reader import describe_design, read_design
from forge.slides.edit import OPERATIONS, apply_operations, parse_operations
from forge.slides.extract import deck_markdown
from forge.slides.image_reader import (
    analyze_reference_image,
    compare_to_reference,
    describe_comparison,
    describe_reference,
)
from forge.slides.importer import merge_decks, split_deck
from forge.slides.measure import measure_deck, overflow_problems
from forge.slides.open_deck import DeckError, open_deck, save_deck
from forge.slides.read import describe_deck, slide_notes
from forge.slides.review import review_deck, summarize
from forge.slides.spec import BrandKit, parse_deck
from forge.slides.template import analyze_template, describe_template
from forge.slides.template_build import _open
from forge.slides.template_samples import analyze_samples, describe_samples
from forge.slides.validate import validate_package
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools.brand_file import BRAND_FILE_DESCRIPTION, load_brand_file
from forge.tools.vision import image_path

PREVIEW_FOLDER = ".forge/reports/slides"
MAX_LISTED_PICTURES = 30  # a long deck is read from its contact sheets; single pictures are for a closer look


def _fault_message(path: str, faults: list[str]) -> str:
    """The file was written, but PowerPoint may refuse it or offer to repair it: say so and list why (P1.8)."""
    listed = "\n".join(f"- {fault}" for fault in faults)
    return (
        f"{path} was written but its package has structural faults, so PowerPoint may offer to repair it:\n{listed}\n"
        "This is a DebCraft bug or a bad edit; undo the last operation or rebuild from the outline, and tell the "
        "user if it repeats."
    )


class BuildPresentation(Tool):
    name = "build_presentation"
    read_only = False
    description = (
        "Make a PowerPoint (.pptx) from an outline file you wrote (JSON or YAML; load the "
        "`make-presentation` skill for its format and the design rules). Slides get real titles, text "
        "boxes, native charts and tables, speaker notes, and text sized to fit; the `freeform` layout lets "
        "you place every element yourself for a designed look. Returns per-slide warnings "
        "(text too long, too many bullets, ...) that you should fix by editing the outline and building "
        "again. Then call preview_presentation and look at the pictures."
    )

    class Args(ToolArgs):
        outline: str = Field(description="Path of the JSON or YAML outline, relative to the repository root")
        output: str = Field(description="Path of the .pptx to write, e.g. docs/q3-review.pptx")
        brand_file: str = Field(default="", description=BRAND_FILE_DESCRIPTION)
        reason: str = Field(default="", description="One line saying why; shown to the user in CHANGES.md.")

    def summary(self, args: BuildPresentation.Args) -> str:
        return f"build presentation {args.output}"

    async def run(self, args: BuildPresentation.Args, context: ToolContext) -> ToolResult:
        if not args.output.lower().endswith(".pptx"):
            return ToolResult(ok=False, content="The output file name must end in .pptx")
        outline = context.workspace.path_of(args.outline)
        if not outline.is_file():
            return ToolResult(ok=False, content=f"No outline file at {args.outline}. Write it first.")
        try:
            deck = parse_deck(
                outline.read_text(encoding="utf-8"), as_yaml=outline.suffix.lower() in {".yaml", ".yml"}
            )
            kit = load_brand_file(context, args.brand_file)
            if kit is not None:
                deck.brand = BrandKit.model_validate(kit.model_dump())
            built = await asyncio.to_thread(
                build_deck, deck, lambda name: image_path(context, name).read_bytes()
            )
            context.workspace.write_bytes(
                args.output, built.data, args.reason or "presentation built from an outline"
            )
        except SlidesUnavailable as error:
            return ToolResult(
                ok=False, content=f"{error} Tell the user; a presentation cannot be built without it."
            )
        except (ForgeError, OSError, ValueError) as error:
            return ToolResult(ok=False, content=str(error))
        context.last_edit_step = context.step
        faults = validate_package(built.data)
        if faults:
            return ToolResult(ok=False, content=_fault_message(args.output, faults))
        warnings = [f"slide {s.number} ({s.layout}): {w}" for s in built.slides for w in s.warnings]
        warnings += [f"deck: {w}" for w in built.deck_warnings]
        lines = [f"Built {args.output}: {len(built.slides)} slides, {len(built.data) // 1024} KB."]
        lines += (
            ["Fix these in the outline and build again:", *[f"- {w}" for w in warnings]]
            if warnings
            else ["No layout warnings."]
        )
        lines.append("Next: preview_presentation to look at the slides.")
        return ToolResult(ok=True, content="\n".join(lines))


class ReadPresentation(Tool):
    name = "read_presentation"
    read_only = True
    description = (
        "Read an existing PowerPoint (.pptx, or a .potx template; an old .ppt/.pps/.pptm is converted first when PowerPoint is "
        "installed). format 'outline' (default): every slide with its layout, title, shapes (with the id to refer to each by), tables, "
        "chart data, picture alt text, speaker notes, hidden slides, sections, transitions, animations and comments, plus the layouts "
        "the deck can add slides from. format 'markdown': the deck's text as Markdown (one heading per slide, bullets, tables, chart "
        "data, links, notes, comments), best for summarising or rewriting. The Markdown refers to pictures in the folder 'pictures' (save "
        "them there with convert_presentation to='pictures'). Nothing in the file is run."
    )

    class Args(ToolArgs):
        path: str = Field(
            description="The .pptx or .potx, relative to the repository root (or a file the user opened)"
        )
        format: Literal["outline", "markdown"] = "outline"

    def summary(self, args: ReadPresentation.Args) -> str:
        return f"read presentation {args.path}"

    async def run(self, args: ReadPresentation.Args, context: ToolContext) -> ToolResult:
        file = context.workspace.path_of(args.path)
        if not file.is_file():
            return ToolResult(ok=False, content=f"No file at {args.path}.")
        try:
            deck = await asyncio.to_thread(_open_any, file)
            text = deck_markdown(deck) if args.format == "markdown" else describe_deck(deck)
            return ToolResult(ok=True, content=text)
        except SlidesUnavailable as error:
            return ToolResult(ok=False, content=f"{error} Tell the user.")
        except (ForgeError, OSError, preview.PreviewUnavailable) as error:
            return ToolResult(ok=False, content=str(error))


def _open_any(file: Path) -> Any:
    """A .pptx or .potx directly; an old format through PowerPoint (a temporary .pptx that is read and dropped)."""
    if file.suffix.lower() in OLD_FORMATS - {".potx"}:
        import tempfile

        try:
            data = convert_deck(file, "pptx")
        except preview.PreviewUnavailable as error:
            raise DeckError(
                f"{file.name} is an old format and PowerPoint cannot convert it here ({error}). Ask the user to save it as .pptx first."
            ) from error
        with tempfile.TemporaryDirectory(prefix="forge-read-") as folder:
            converted = Path(folder) / "converted.pptx"
            converted.write_bytes(data)
            return open_deck(converted)
    return open_deck(file)


async def _save_pictures(deck: Any, context: ToolContext, folder: str) -> str:
    from forge.slides.edit_find import walk
    from forge.slides.extract import _image_name

    saved = []
    for number, slide in enumerate(deck.slides, start=1):
        for shape in walk(slide.shapes):
            if shape.shape_type == 13:
                relative = f"{folder}/{_image_name(number, shape)}"
                context.workspace.write_bytes(relative, shape.image.blob, "picture extracted from a deck")
                saved.append(relative)
    if not saved:
        return "The deck has no pictures to extract."
    return f"Saved {len(saved)} picture(s):" + "".join(f"\n- {name}" for name in saved)


class ConvertPresentation(Tool):
    name = "convert_presentation"
    read_only = False
    description = (
        "Convert a deck with PowerPoint itself (Windows with PowerPoint installed): an old .ppt/.pps/.pptm to .pptx so it can be read "
        "and edited, or any deck to PDF to hand to someone, or save the deck's embedded pictures as files (to 'pictures', no PowerPoint "
        "needed). The result is written to 'output' (default: next to the source)."
    )

    class Args(ToolArgs):
        path: str = Field(description="The deck, relative to the repository root")
        to: Literal["pptx", "pdf", "pictures"] = "pdf"
        output: str = Field(
            default="",
            description="Where to write the result (for pictures: a folder); default: same name with the new extension, or the folder 'pictures'",
        )

    def summary(self, args: ConvertPresentation.Args) -> str:
        return f"convert {args.path} to {args.to}"

    async def run(self, args: ConvertPresentation.Args, context: ToolContext) -> ToolResult:
        source = context.workspace.path_of(args.path)
        if not source.is_file():
            return ToolResult(ok=False, content=f"No file at {args.path}.")
        if args.to == "pictures":
            try:
                deck = await asyncio.to_thread(_open_any, source)
                return ToolResult(
                    ok=True,
                    content=(
                        await _save_pictures(deck, context, args.output.strip().strip("/") or "pictures")
                    ).strip(),
                )
            except SlidesUnavailable as error:
                return ToolResult(ok=False, content=f"{error} Tell the user.")
            except (ForgeError, OSError, preview.PreviewUnavailable) as error:
                return ToolResult(ok=False, content=str(error))
        target = args.output.strip() or str(Path(args.path).with_suffix("." + args.to).as_posix())
        try:
            data = await asyncio.to_thread(convert_deck, source, args.to)
        except preview.PreviewUnavailable as error:
            return ToolResult(
                ok=False,
                content=f"Could not convert: {error} Tell the user what to do by hand (File > Save As in PowerPoint).",
            )
        context.workspace.write_bytes(target, data, f"converted from {args.path}")
        return ToolResult(ok=True, content=f"Wrote {target} ({len(data) // 1024} KB).")


class CheckAccessibility(Tool):
    name = "check_accessibility"
    read_only = True
    description = (
        "Check a .pptx for accessibility: document title, slide titles, alt text on pictures, charts and tables, table header rows, "
        "reading order (title first, footer last), link texts, the text language, and chart colours a colour-blind viewer cannot tell "
        "apart. Decks built by build_presentation are already repaired where that needs no guessing; use this on decks made elsewhere "
        "or after edits, and fix what it lists (edit_presentation can set alt text)."
    )

    class Args(ToolArgs):
        path: str = Field(description="The .pptx, relative to the repository root")

    def summary(self, args: CheckAccessibility.Args) -> str:
        return f"check accessibility {args.path}"

    async def run(self, args: CheckAccessibility.Args, context: ToolContext) -> ToolResult:
        file = context.workspace.path_of(args.path)
        if not file.is_file():
            return ToolResult(ok=False, content=f"No file at {args.path}.")
        try:
            deck = await asyncio.to_thread(open_deck, file)
            problems = check_deck(deck)
        except SlidesUnavailable as error:
            return ToolResult(ok=False, content=f"{error} Tell the user.")
        except (ForgeError, OSError) as error:
            return ToolResult(ok=False, content=str(error))
        if not problems:
            return ToolResult(ok=True, content="No accessibility problems found.")
        errors = sum(1 for p in problems if p.level == "error")
        lines = [p.render() for p in problems[:40]]
        more = f"\n... and {len(problems) - 40} more" if len(problems) > 40 else ""
        header = f"{errors} error(s), {len(problems) - errors} warning(s):"
        return ToolResult(ok=True, content=header + "\n" + "\n".join(lines) + more)


class ReviewPresentation(Tool):
    name = "review_presentation"
    read_only = True
    description = (
        "Critique a .pptx (any deck, yours or the user's) with deterministic checks and list what to change: titles that are labels "
        "instead of messages, too many words or bullets, mixed fonts and sizes, titles that jump around, low contrast, shapes off the "
        "slide or overlapping, runs of the same layout, text-only decks, empty placeholders, missing speaker notes and the "
        "accessibility findings. Each finding says how to fix it with edit_presentation. Look at preview pictures too: this checks "
        "what can be measured, not whether the story is good."
    )

    class Args(ToolArgs):
        path: str = Field(description="The .pptx, relative to the repository root")
        minutes: int | None = Field(
            default=None, ge=1, le=480, description="Length of the talk, to judge the slide count"
        )

    def summary(self, args: ReviewPresentation.Args) -> str:
        return f"review {args.path}"

    async def run(self, args: ReviewPresentation.Args, context: ToolContext) -> ToolResult:
        file = context.workspace.path_of(args.path)
        if not file.is_file():
            return ToolResult(ok=False, content=f"No file at {args.path}.")
        try:
            deck = await asyncio.to_thread(_open_any, file)
            findings = review_deck(deck, args.minutes)
        except SlidesUnavailable as error:
            return ToolResult(ok=False, content=f"{error} Tell the user.")
        except (ForgeError, OSError) as error:
            return ToolResult(ok=False, content=str(error))
        return ToolResult(ok=True, content=summarize(findings))


class SplitPart(ToolArgs):
    output: str
    slides: list[int] = Field(min_length=1, description="Slide numbers (1-based) this part keeps")


class MergePresentations(Tool):
    name = "merge_presentations"
    read_only = False
    description = (
        "Combine decks into one new .pptx: the first deck, then every slide of the others, each keeping its own look (design 'keep') or "
        "taking the first deck's (design 'match'). One section per source deck. To bring only some slides into a deck you are editing, use "
        "edit_presentation with an import_slides operation instead."
    )

    class Args(ToolArgs):
        paths: list[str] = Field(
            min_length=2, description="The decks in order, relative to the repository root"
        )
        output: str = Field(description="Where to save the merged deck (a .pptx)")
        design: Literal["keep", "match"] = "keep"

    def summary(self, args: MergePresentations.Args) -> str:
        return f"merge {len(args.paths)} decks into {args.output}"

    async def run(self, args: MergePresentations.Args, context: ToolContext) -> ToolResult:
        if not args.output.lower().endswith(".pptx"):
            return ToolResult(ok=False, content="Save the result as a .pptx.")
        try:
            decks = []
            for path in args.paths:
                file = context.workspace.path_of(path)
                if not file.is_file():
                    return ToolResult(ok=False, content=f"No file at {path}.")
                decks.append((Path(path).stem, await asyncio.to_thread(open_deck, file)))
            merged, notes = await asyncio.to_thread(merge_decks, decks, args.design)
            data = save_deck(merged)
            context.workspace.write_bytes(args.output, data, "decks merged")
        except SlidesUnavailable as error:
            return ToolResult(ok=False, content=f"{error} Tell the user.")
        except (ForgeError, OSError, ValueError) as error:
            return ToolResult(ok=False, content=str(error))
        faults = validate_package(data)
        if faults:
            return ToolResult(ok=False, content=_fault_message(args.output, faults))
        lines = [f"Saved {args.output} ({len(merged.slides)} slides from {len(args.paths)} decks).", *notes]
        lines.append("Next: preview_presentation and look at the joins between the decks.")
        return ToolResult(ok=True, content="\n".join(lines))


class SplitPresentation(Tool):
    name = "split_presentation"
    read_only = False
    description = (
        "Split a deck into several new .pptx files, each with the slides you choose (the original is not changed). For example a short "
        "version of a long deck, or one file per section."
    )

    class Args(ToolArgs):
        path: str = Field(description="The deck, relative to the repository root")
        parts: list[SplitPart] = Field(
            min_length=1, description="Each part: where to save it and which slides it keeps"
        )

    def summary(self, args: SplitPresentation.Args) -> str:
        return f"split {args.path} into {len(args.parts)} file(s)"

    async def run(self, args: SplitPresentation.Args, context: ToolContext) -> ToolResult:
        source = context.workspace.path_of(args.path)
        if not source.is_file():
            return ToolResult(ok=False, content=f"No file at {args.path}.")
        written = []
        try:
            for part in args.parts:
                if not part.output.lower().endswith(".pptx"):
                    return ToolResult(ok=False, content=f"{part.output}: save each part as a .pptx.")
                deck = await asyncio.to_thread(open_deck, source)  # a fresh copy for each part
                data = save_deck(split_deck(deck, part.slides))
                faults = validate_package(data)
                if faults:
                    return ToolResult(ok=False, content=_fault_message(part.output, faults))
                context.workspace.write_bytes(part.output, data, f"split from {args.path}")
                written.append(f"{part.output} ({len(part.slides)} slides)")
        except SlidesUnavailable as error:
            return ToolResult(ok=False, content=f"{error} Tell the user.")
        except (ForgeError, OSError, ValueError) as error:
            return ToolResult(ok=False, content=str(error))
        return ToolResult(ok=True, content="Saved:\n" + "\n".join(f"- {line}" for line in written))


class DescribeDesign(Tool):
    name = "describe_design"
    read_only = True
    description = (
        "Read the DESIGN of any .pptx (not its content): slide size, theme colours and fonts, how many slides are dark or light, where the "
        "titles sit, the text margins, the shapes that repeat on most slides (logo, bars, footer), the layouts, fonts, sizes and fill "
        "colours really used, and a brand kit to paste into an outline. Use it first when the user says 'make new slides in this format' or "
        "gives a deck as the style to follow; then build on the deck itself as a template (build_presentation with template) when it is "
        "16:9, or with the brand kit and the same title position and frame shapes in freeform slides."
    )

    class Args(ToolArgs):
        path: str = Field(
            description="The .pptx or .potx, relative to the repository root (or a file the user opened)"
        )

    def summary(self, args: DescribeDesign.Args) -> str:
        return f"describe design {args.path}"

    async def run(self, args: DescribeDesign.Args, context: ToolContext) -> ToolResult:
        file = context.workspace.path_of(args.path)
        if not file.is_file():
            return ToolResult(ok=False, content=f"No file at {args.path}.")
        try:
            deck = await asyncio.to_thread(_open_any, file)
            design = await asyncio.to_thread(read_design, deck)
        except SlidesUnavailable as error:
            return ToolResult(ok=False, content=f"{error} Tell the user.")
        except (ForgeError, OSError, preview.PreviewUnavailable) as error:
            return ToolResult(ok=False, content=str(error))
        text = describe_design(design, Path(args.path).name)
        widescreen = abs(design.width / design.height - 16 / 9) < 0.03
        advice = (
            "Next: the deck is 16:9, so build on it as a template (analyze_template, then build_presentation with `template`): its own sample slides "
            "are copied and filled."
            if widescreen and design.slides
            else "Next: the deck is not 16:9, so it cannot be a template; use the brand kit above and keep the title position, margins and the "
            "repeated frame shapes in freeform slides."
        )
        return ToolResult(ok=True, content=text + "\n" + advice)


class AnalyzeReferenceImage(Tool):
    name = "analyze_reference_image"
    read_only = True
    description = (
        "Measure a picture of a slide (a screenshot or a photo of a deck the user wants matched): the dominant colours with their shares, the "
        "background and text colours, the accents, where the content sits (regions in inches on a 13.33 x 7.5 slide), the marks in the "
        "corners (logos) and a brand kit for the outline. These are measured from pixels, not guessed. Fonts and photographs cannot be read: "
        "look at the picture with view_image for those. Then build the slide (freeform), preview it, and call compare_to_reference with the "
        "preview picture and this reference, fix the cells that differ most, and repeat up to three times."
    )

    class Args(ToolArgs):
        path: str = Field(
            description="The reference picture (png, jpg), relative to the repository root or a file the user opened"
        )

    def summary(self, args: AnalyzeReferenceImage.Args) -> str:
        return f"analyze reference image {args.path}"

    async def run(self, args: AnalyzeReferenceImage.Args, context: ToolContext) -> ToolResult:
        try:
            data = image_path(context, args.path).read_bytes()
            design = await asyncio.to_thread(analyze_reference_image, data)
        except (ForgeError, OSError, ValueError) as error:
            return ToolResult(ok=False, content=f"The picture could not be read: {error}")
        return ToolResult(ok=True, content=describe_reference(design, Path(args.path).name))


class CompareToReference(Tool):
    name = "compare_to_reference"
    read_only = True
    description = (
        "Score how close a rendered slide picture is to a reference picture (colour and layout, on an 8 x 5 grid; 100 = the same) and name "
        "the cells that differ most. Use it after preview_presentation when matching a design shown as a picture; aim for 80 or more."
    )

    class Args(ToolArgs):
        rendered: str = Field(
            description="The picture of your slide, e.g. from preview_presentation (.forge/reports/slides/...)"
        )
        reference: str = Field(description="The reference picture the user gave")

    def summary(self, args: CompareToReference.Args) -> str:
        return f"compare {args.rendered} to {args.reference}"

    async def run(self, args: CompareToReference.Args, context: ToolContext) -> ToolResult:
        try:
            first = image_path(context, args.rendered).read_bytes()
            second = image_path(context, args.reference).read_bytes()
            result = await asyncio.to_thread(compare_to_reference, first, second)
        except (ForgeError, OSError, ValueError) as error:
            return ToolResult(ok=False, content=f"The pictures could not be compared: {error}")
        return ToolResult(ok=True, content=describe_comparison(result))


class AnalyzeTemplate(Tool):
    name = "analyze_template"
    read_only = False  # with pictures it writes them under .forge/reports
    description = (
        "Study a company PowerPoint template (.potx or .pptx): slide size, theme colours, fonts, what each layout is for, and "
        "the template's own SAMPLE SLIDES (title, cards, big numbers, bullets, thank you...) with their slots. To build a deck in "
        'the corporate format, set "template" in the outline of build_presentation: slides then use the samples and '
        "layouts, or copy a chosen sample with {layout: template_slide, source: N, fill: {...}}. With pictures=true it also "
        "renders the template with PowerPoint so you can look at each sample with view_image and choose the right one."
    )

    class Args(ToolArgs):
        path: str = Field(
            description="The template, relative to the repository root (or a file the user opened)"
        )
        pictures: bool = Field(
            default=False, description="Also make pictures of the template's slides (needs PowerPoint)"
        )

    def summary(self, args: AnalyzeTemplate.Args) -> str:
        return f"analyze template {args.path}"

    async def run(self, args: AnalyzeTemplate.Args, context: ToolContext) -> ToolResult:
        file = context.workspace.path_of(args.path)
        if not file.is_file():
            return ToolResult(ok=False, content=f"No file at {args.path}.")
        try:
            data = await asyncio.to_thread(file.read_bytes)
            prs = _open(data)
            text = (
                describe_template(analyze_template(prs), args.path)
                + "\n\n"
                + describe_samples(analyze_samples(prs))
            )
        except SlidesUnavailable as error:
            return ToolResult(ok=False, content=f"{error} Tell the user.")
        except (ForgeError, OSError) as error:
            return ToolResult(ok=False, content=str(error))
        if args.pictures:
            text += await self._pictures(file, context)
        return ToolResult(ok=True, content=text)

    @staticmethod
    async def _pictures(file: Path, context: ToolContext) -> str:
        folder = context.workspace.jail.check(context.workspace.root / PREVIEW_FOLDER / file.stem)
        try:
            pictures = await asyncio.to_thread(preview.export_slides, file, folder)
        except preview.PreviewUnavailable as error:
            return f"\n\nNo pictures could be made: {error}"
        names = [PreviewPresentation.relative(context, p) for p in pictures]
        try:
            sheets = await asyncio.to_thread(make_contact_sheets, pictures, folder)
            names = [PreviewPresentation.relative(context, s) for s in sheets] + names
        except (ContactSheetUnavailable, OSError):
            pass
        return (
            "\n\nPictures of the template's slides (look at them with view_image; contact sheets first):\n"
            + "\n".join(f"- {name}" for name in names)
        )


class EditPresentation(Tool):
    name = "edit_presentation"
    read_only = False
    description = (
        "Change an existing PowerPoint without rebuilding it, keeping its formatting. Operations (a "
        "list, run in order; if one fails nothing is saved): " + OPERATIONS + ". Slides are numbered "
        "from 1 as in read_presentation; shapes are named by their id or exact name. add_slide without a layout copies the look of "
        "the deck's own last text slide and lands before a closing slide; with a layout name it uses the deck's own layouts, which is how a company template is used: open the template with output set "
        "to a new .pptx, add the slides, and delete its sample slides. Read the deck first, and preview "
        "the result afterwards."
    )

    class Args(ToolArgs):
        path: str = Field(description="The .pptx or .potx to change, relative to the repository root")
        operations: list[dict[str, Any]] = Field(
            description='For example [{"op": "replace_text", "find": "Q3", "replace": "Q4"}, '
            '{"op": "add_slide", "layout": "Title and Content", "title": "Next steps", "body": ["Ship it"]}]'
        )
        output: str = Field(
            default="",
            description="Where to save the result (a .pptx). Empty = change the file in place (it can "
            "be undone). Required when path is a .potx template.",
        )
        reason: str = Field(default="", description="One line saying why; shown to the user in CHANGES.md.")

    def summary(self, args: EditPresentation.Args) -> str:
        return f"edit presentation {args.path} ({len(args.operations)} operations)"

    async def run(self, args: EditPresentation.Args, context: ToolContext) -> ToolResult:
        source = context.workspace.path_of(args.path)
        target = args.output or args.path
        if not source.is_file():
            return ToolResult(ok=False, content=f"No file at {args.path}.")
        if not target.lower().endswith(".pptx"):
            return ToolResult(
                ok=False,
                content="Save the result as a .pptx: give `output` (a template cannot be overwritten).",
            )
        try:
            deck = await asyncio.to_thread(open_deck, source)
            done = apply_operations(
                deck,
                parse_operations(args.operations),
                lambda name: image_path(context, name).read_bytes(),
                lambda name: open_deck(context.workspace.path_of(name)),
            )
            data = save_deck(deck)
            context.workspace.write_bytes(target, data, args.reason or "presentation edited")
        except SlidesUnavailable as error:
            return ToolResult(ok=False, content=f"{error} Tell the user.")
        except (ForgeError, OSError, ValueError) as error:
            return ToolResult(ok=False, content=str(error))
        context.last_edit_step = context.step
        faults = validate_package(data)
        if faults:
            return ToolResult(ok=False, content=_fault_message(target, faults))
        lines = [f"Saved {target} ({len(deck.slides)} slides). Done:", *[f"- {line}" for line in done]]
        lines.append("Next: preview_presentation and look at the slides you changed.")
        return ToolResult(ok=True, content="\n".join(lines))


class PreviewPresentation(Tool):
    name = "preview_presentation"
    read_only = False
    description = (
        "Make a picture of every slide of a .pptx with PowerPoint itself (Windows with PowerPoint "
        "installed), so you can look at them with view_image and fix what looks wrong: crowded or cut-off "
        "text, uneven spacing, a chart that is hard to read. If PowerPoint is not available it says so, and "
        "you rely on the build warnings instead."
    )

    class Args(ToolArgs):
        path: str = Field(description="The .pptx to preview, relative to the repository root")

    def summary(self, args: PreviewPresentation.Args) -> str:
        return f"preview {args.path}"

    async def run(self, args: PreviewPresentation.Args, context: ToolContext) -> ToolResult:
        deck = context.workspace.path_of(args.path)
        if not deck.is_file() or deck.suffix.lower() != ".pptx":
            return ToolResult(ok=False, content=f"No .pptx file at {args.path}.")
        folder = context.workspace.jail.check(context.workspace.root / PREVIEW_FOLDER / deck.stem)
        try:
            pictures = await asyncio.to_thread(preview.export_slides, deck, folder)
        except preview.PreviewUnavailable as error:
            return ToolResult(
                ok=True,
                content=f"No pictures could be made: {error} Go by the build warnings, and tell the user "
                "the slides were not looked at.",
            )
        names = [self.relative(context, picture) for picture in pictures]
        try:
            notes = await asyncio.to_thread(slide_notes, deck)
        except (ForgeError, OSError, ValueError, KeyError):
            notes = []
        await context.emit(  # the chat shows the slides (P1.2); the model's own result below is unchanged
            "notice",
            {
                "kind": "slides_ready",
                "text": f"Slides of {args.path}",
                "deck": args.path,
                "pictures": names,
                "notes": [n[:1500] for n in notes],
            },
        )
        sheets: list[str] = []
        try:
            made = await asyncio.to_thread(make_contact_sheets, pictures, folder)
            sheets = [self.relative(context, sheet) for sheet in made]
        except (ContactSheetUnavailable, OSError):
            pass  # the single pictures are enough
        if sheets:
            text = (
                "Contact sheet(s) with all slides at a glance: look at these first with view_image to judge flow, "
                "rhythm and consistency (do the slides look like one deck? any text-only or crowded slide?):\n"
                + "\n".join(f"- {name}" for name in sheets)
                + "\n\nThen look at single slides that need a closer look:\n"
            )
        else:
            text = "Pictures of the slides (look at each with view_image and fix what is wrong):\n"
        shown = names[:MAX_LISTED_PICTURES]
        text += "\n".join(f"- {name}" for name in shown)
        if len(names) > len(shown):
            text += (
                f"\n(... and {len(names) - len(shown)} more in {PREVIEW_FOLDER}/{deck.stem}/ as slide-N.png; "
                "the contact sheets show all)"
            )
        try:  # PowerPoint is open anyway: ask it for the real text sizes instead of trusting the estimate (P2.18)
            spilled: list[str] | None = overflow_problems(await asyncio.to_thread(measure_deck, deck))
        except (preview.PreviewUnavailable, OSError, ValueError, KeyError):
            spilled = None
        if spilled:
            listed = "\n".join(f"- {line}" for line in spilled)
            text += (
                f"\n\nPowerPoint measured text that does not fit (fix these, then preview again):\n{listed}"
            )
        elif spilled is not None:
            text += "\n\nPowerPoint measured every text box and table: all fit their space."
        return ToolResult(ok=True, content=text)

    @staticmethod
    def relative(context: ToolContext, path: Path) -> str:
        return path.resolve().relative_to(context.workspace.root.resolve()).as_posix()


class FindIcon(Tool):
    name = "find_icon"
    read_only = True
    description = (
        "Search the bundled icons (Lucide outline icons and Material Symbols filled icons, offline) for slides. Give a few "
        "words ('growth chart', 'security', 'team'); returns icon names such as lucide:trending-up to use in a freeform "
        "slide's icon element ({type: icon, name: ..., x, y, w, h, color, badge}). For an SVG file (web pages, documents) use find_image and fetch_image: they list the same bundled icons first and can save them as SVG in any colour; they also search online sets (Iconify) when none of these fits."
    )

    class Args(ToolArgs):
        query: str = Field(description="what the icon should show, in a few words")
        limit: int = Field(default=8, ge=1, le=20)

    async def run(self, args: FindIcon.Args, context: ToolContext) -> ToolResult:
        found = icons.search_icons(args.query, args.limit)
        if not found:
            return ToolResult(
                ok=True,
                content=f"No icon matched {args.query!r}. Try one or two other words (a noun: 'chart', 'lock', 'people'), or search online sets with find_image (kind icon).",
            )
        return ToolResult(
            ok=True,
            content="Icons (lucide: = outline, material: = filled):\n"
            + "\n".join(f"- {name}" for name in found),
        )


def presentation_tools() -> list[Tool]:
    return [
        BuildPresentation(),
        ReadPresentation(),
        ConvertPresentation(),
        MergePresentations(),
        SplitPresentation(),
        AnalyzeTemplate(),
        CheckAccessibility(),
        ReviewPresentation(),
        DescribeDesign(),
        AnalyzeReferenceImage(),
        CompareToReference(),
        EditPresentation(),
        PreviewPresentation(),
        FindIcon(),
    ]

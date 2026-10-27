"""design_specimen and design_candidates (TODO DS3, D-350): look at a design system, and choose the best of two or three.

A specimen is the tokens of a DESIGN.md applied to a standard set of components (hero, cards, table, form, status chips, swatches), drawn in a
guarded offline browser. `design_candidates` checks each candidate with the linter, makes sure the candidates (and the designs the user already
rejected) differ on at least three dimensions, draws a specimen for each, and has the vision model judge them against the brief. The result and
what was shown are kept in `.forge/design-rounds.json`, so a second round knows what to avoid."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import Field

from forge.designsystem.brief_kind import classify_brief
from forge.designsystem.concept import concept_problem, same_idea
from forge.designsystem.fonts import font_css
from forge.designsystem.lint import describe_findings, lint_text
from forge.designsystem.novelty import describe_fingerprint, differences, fingerprint, is_different_enough
from forge.designsystem.spec import DesignMdError, DesignSystem, parse_design_md
from forge.designsystem.specimen import families_of, specimen_html
from forge.errors import ForgeError
from forge.llm.base import ChatRequest, Message
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools.vision import _relative
from forge.tools.web_render import RenderUnavailable, _launch
from forge.vision import images

CANDIDATE_FOLDER = ".forge/candidates"
ROUNDS_FILE = ".forge/design-rounds.json"
LABELS = "ABC"
MAX_SIMILAR_REFUSALS = (
    2  # then the candidates are judged as they are: a wrong refusal can never trap the model
)
RUBRIC = (
    "You are a demanding art director judging design systems from specimen pictures (the same components drawn with each candidate's tokens). "
    "You are given the brief, the candidates labelled A, B and C, and sometimes the designs the user already rejected and why. Judge only what you "
    "see. Be strict and use the whole scale: 5 is award-winning studio work, 4 is clearly professional studio work whose distinctive quality you can name, 3 is competent but template-like, 2 is the generic machine-made look, 1 is poor; most machine-made designs are 2 or 3. Score each candidate 1 to 5 on: typography (does the type suit the product, its mood and its language; real pairing and contrast of roles; a system font stack is a 2), distinctiveness (does it look designed for this product, not like a default template; generic blue SaaS, "
    "purple-blue gradients, cream-and-terracotta and identical card rows score low), hierarchy (type scale, weight and spacing guide the eye), "
    "harmony (palette, shape and depth belong together), fit (the feeling the brief asks for), polish (contrast, alignment, rhythm). "
    'Reply with JSON only: {"scores": {"A": {"typography": n, "distinctiveness": n, "hierarchy": n, "harmony": n, "fit": n, "polish": n}, ...}, "winner": "A", '
    '"reasons": "two sentences", "fixes": {"A": ["a concrete change to the tokens"], ...}}. Pick the winner by overall quality for the brief, '
    "not by the highest single score. If a candidate repeats what the user rejected, say so and do not pick it."
)


class SpecimenUnavailable(ForgeError):
    """The specimen could not be drawn; the message says why."""


async def draw(html: str, target: Path) -> None:
    """Draws `html` to a PNG with no network at all."""
    try:
        from playwright.async_api import Error as PlaywrightError
        from playwright.async_api import async_playwright
    except ImportError as error:
        raise SpecimenUnavailable("playwright is not installed (pip install playwright)") from error
    async with async_playwright() as playwright:
        try:
            browser = await _launch(playwright)
        except RenderUnavailable as error:
            raise SpecimenUnavailable(str(error)) from error
        try:
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900}, service_workers="block"
            )

            async def offline(route: Any) -> None:
                await route.abort()

            await context.route(re.compile(r"^(?!data:|about:).*"), offline)
            page = await context.new_page()
            try:
                await page.set_content(html, wait_until="load")
                target.parent.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(target), full_page=True)
            except PlaywrightError as error:
                raise SpecimenUnavailable(
                    f"the browser could not draw it: {str(error).splitlines()[0][:160]}"
                ) from error
        finally:
            await browser.close()


def _font_notes(path: str, system: DesignSystem, text: str) -> list[str]:
    """Typography problems of a candidate: system fonts (a candidate in the system stack is the machine-made look) and families that cannot be shown."""
    notes = [f"{path}: {f.path}: {f.message}" for f in lint_text(text) if f.rule == "system-font"]
    _, missing = font_css(families_of(system))
    if missing:
        notes.append(
            f"{path}: {', '.join(missing)} is not bundled, so the specimen shows a fallback; judge the pairing from the names, and fetch the real font "
            "with find_font and fetch_font when it wins."
        )
    return notes


def _load(context: ToolContext, path: str) -> tuple[DesignSystem, str]:
    file = context.workspace.path_of(path)
    if not file.is_file():
        raise DesignMdError(f"No file at {path}.")
    text = file.read_text(encoding="utf-8", errors="replace")
    return parse_design_md(text), text


class DesignSpecimen(Tool):
    name = "design_specimen"
    read_only = False
    description = (
        "Draw a picture of a DESIGN.md: its colours, type, shapes and states on a standard set of components (hero, cards, table, form, status chips, "
        "swatches), so you can judge the design before building any page. Look at the picture with view_image. Fonts that are not installed on this "
        "computer show as fallbacks: judge palette, hierarchy and shape."
    )

    class Args(ToolArgs):
        path: str = Field(default="DESIGN.md", description="The DESIGN.md file")
        headline: str = Field(
            default="", description="A real headline for the product, so the picture is not lorem ipsum"
        )
        lede: str = Field(default="", description="One supporting sentence")
        output: str = Field(
            default="", description="Where to write the PNG (default .forge/candidates/<name>-specimen.png)"
        )

    def summary(self, args: DesignSpecimen.Args) -> str:
        return f"specimen of {args.path}"

    async def run(self, args: DesignSpecimen.Args, context: ToolContext) -> ToolResult:
        try:
            system, text = _load(context, args.path)
            target = context.workspace.root / (
                args.output or f"{CANDIDATE_FOLDER}/{Path(args.path).parent.name or 'project'}-specimen.png"
            )
            context.workspace.jail.check(target)
            await draw(specimen_html(system, args.headline, args.lede), target)
        except (ForgeError, OSError) as error:
            return ToolResult(ok=False, content=str(error))
        errors = [f for f in lint_text(text) if f.severity == "error"]
        note = (
            ("\nThe file has lint errors (design_md_lint): " + describe_findings(errors, 5)) if errors else ""
        )
        return ToolResult(
            ok=True, content=f"Specimen: {_relative(context, target)}. Look at it with view_image.{note}"
        )


def _unknown_composition(context: ToolContext, composition: str) -> str:
    """A composition that is not a catalogue id. The night-1 and night-2 design runs invented names such as `app-northline-bright-logistics` and `lay-admin-table`, so the real
    screens (`app-dashboard-ops`, `app-table-data`, `app-form-wizard`) were never copied and the pages were written from a blank file (D-406). Empty string when it is fine."""
    import difflib

    from forge.tools.assets import _catalogues

    words = composition.split()
    if not words or words[0].lower() == "custom":
        return ""
    wanted = words[0].strip("`'\",.;")
    known = {asset.id for _skill, asset in _catalogues(context) if asset.type == "section"}
    if wanted in known:
        return ""
    layouts = sorted(
        i for i in known if i.startswith(("lay-", "app-")) and not i.startswith(("lay-react-", "app-react-"))
    )
    close = difflib.get_close_matches(wanted, layouts, n=4, cutoff=0.25)
    near = ", ".join(close or layouts[:6])
    return (
        f"`composition: {wanted}` is not in the catalogue. Pick a real one (closest: {near}; find_asset with the tag 'composition' or 'app screen' lists them all), then add_asset copies it, "
        "or write `composition: custom <one line describing the layout idea>` when none fits."
    )


def _closest_screens(context: ToolContext, brief: str, limit: int = 3) -> list[str]:
    """The ready-made application screens that fit the brief best, as "id (title)" with the plain-HTML ones first."""
    from forge.parity.assets import search
    from forge.tools.assets import _catalogues

    screens = [
        asset
        for _skill, asset in _catalogues(context)
        if asset.type == "section" and asset.id.startswith("app-") and not asset.id.startswith("app-react-")
    ]
    return [
        f"{asset.id} ({asset.title.removeprefix('App screen: ')})"
        for asset in search(screens, brief, limit=limit)
    ]


def _kind_notes(context: ToolContext, brief: str, compositions: dict[str, str]) -> list[str]:
    """Says what kind of request the brief is and whether each candidate's composition matches it (D-488). Notes only: a wrong guess must never block a design."""
    verdict = classify_brief(brief)
    notes: list[str] = []
    if verdict.kind == "application":
        close = _closest_screens(context, brief)
        notes.append(
            f"THIS BRIEF READS AS AN APPLICATION SCREEN ({verdict.reason}), not a brand page. Closest ready-made screens: {'; '.join(close) or 'none found'}. "
            "Name one of them as `composition: app-...` in the winner; add_asset copies it and the first page is refused until it has been copied. Write "
            "`composition: custom <one line>` only when none of them fits what the user does on the screen. For the look, start from the design system ds-office-polish "
            "(find_asset type design-system) and the rules in recipes/back-office-polish.md, unless the user supplied their own design. Keep the design system's own orange and do not ask which palette they want; "
            "only if the user says they dislike the colours or asks to change them, call design_palette show and ask them with one ask_user call, then design_palette apply."
        )
        for path, composition in compositions.items():
            if composition.lower().startswith("lay-"):
                notes.append(
                    f"{path}: `{composition}` is a layout for a brand page; this brief is an application, so use an `app-...` screen from the list above."
                )
    elif verdict.kind == "brand":
        for path, composition in compositions.items():
            if composition.lower().startswith("app-"):
                notes.append(
                    f"{path}: `{composition}` is an application screen, but the brief reads as a brand page ({verdict.reason}); pick a `lay-...` composition unless the page really is a tool."
                )
    return notes


SHOW_CANDIDATES_NOTE = (
    chr(10)
    + "NEXT STEP, required unless an exception below applies. Before you import the winner: when the look is open (the brief names no style, and the user supplied no DESIGN.md, brand guide or reference to follow), show the "
    "candidates and let the user choose, because a wrong direction costs a whole build: call ask_user once with one option per candidate (label a short name, description one "
    "line on what makes it different, image the candidate's specimen path above, recommended the winner). Skip the question when the user's own DESIGN.md or brand guide is binding, "
    "when the brief already fixes the style, or when the user has asked you not to ask. Import the candidate the user picks."
)


def _composition_next_step(system: DesignSystem | None) -> str:
    """After the vote: copy the winner's composition instead of writing the page from a blank file (AS1)."""
    if system is None:
        return ""
    words = str(system.extra.get("composition", "") or "").split()
    if not words or words[0].lower() == "custom":
        return ""
    return (
        f"\nThe winner's composition is {words[0]}: add_asset it now and build the page from its files (change the words, the art and the tokens), "
        "not from a blank file: a copied screen is tested at both widths and costs a fraction of the output."
    )


class DesignCandidates(Tool):
    name = "design_candidates"
    read_only = False
    description = (
        "Choose the best of two or three candidate design systems (DESIGN.md drafts you wrote, for example in .forge/candidates/a/DESIGN.md): each is "
        "linted, the candidates are checked to differ on at least three dimensions (tone, accent hue, display font, corners, density, layout energy), a "
        "specimen is drawn for each, and the vision model judges them against the brief and names a winner with concrete fixes. After a rejection pass "
        "the rejected design(s) and the user's reason: the new candidates must differ from them too. The winner is not copied for you: use "
        "design_md_import on its path to make it the project's DESIGN.md."
    )

    class Args(ToolArgs):
        brief: str = Field(
            description="What the design is for and the feeling it needs, in two or three sentences"
        )
        candidates: list[str] = Field(
            min_length=2, max_length=3, description="Paths of the candidate DESIGN.md files"
        )
        rejected: list[str] = Field(
            default_factory=list, description="Paths of designs the user already rejected"
        )
        rejected_reason: str = Field(default="", description="What the user said was wrong, in their words")
        headline: str = Field(
            default="", description="A real headline for the product, used in every specimen"
        )

    def summary(self, args: DesignCandidates.Args) -> str:
        return f"choose among {len(args.candidates)} designs"

    async def run(self, args: DesignCandidates.Args, context: ToolContext) -> ToolResult:
        loaded: dict[str, tuple[DesignSystem, str]] = {}
        try:
            for path in [*args.candidates, *args.rejected]:
                loaded[path] = _load(context, path)
        except (ForgeError, OSError) as error:
            return ToolResult(ok=False, content=str(error))
        lines: list[str] = []
        usable: list[str] = []
        for path in args.candidates:
            errors = [f for f in lint_text(loaded[path][1]) if f.severity == "error"]
            if not str(loaded[path][0].extra.get("composition", "") or "").strip():
                lines.append(
                    f"{path}: NOT USABLE until it names its composition: add `composition: lay-...` to the front matter (find_asset type section, tag "
                    "composition lists seven complete page layouts with drawn art; for an application use `composition: app-...` from the tag 'app screen'; add_asset copies one and shows its pictures), or `composition: custom <one line "
                    "describing the layout idea>` when none fits the product."
                )
                continue
            missing_concept = concept_problem(loaded[path][1])
            if missing_concept:
                lines.append(f"{path}: NOT USABLE until it has its Concept (D-486). {missing_concept}")
                continue
            unknown = _unknown_composition(context, str(loaded[path][0].extra.get("composition", "")))
            if unknown:
                lines.append(f"{path}: NOT USABLE until fixed\n{unknown}")
                continue
            if errors:
                lines.append(f"{path}: NOT USABLE until fixed\n{describe_findings(errors, 6)}")
            else:
                usable.append(path)
        prints = {path: fingerprint(loaded[path][0]) for path in loaded}
        lines.extend(
            _kind_notes(
                context,
                args.brief,
                {
                    path: str(loaded[path][0].extra.get("composition", "") or "").split(" ")[0]
                    for path in usable
                },
            )
        )
        for path in usable:
            lines.append(f"{path}: {describe_fingerprint(prints[path])}")
            lines.extend(_font_notes(path, loaded[path][0], loaded[path][1]))
        for index, one in enumerate(usable):
            for two in usable[index + 1 :]:
                if same_idea(loaded[one][1], loaded[two][1]):
                    lines.append(
                        f"SAME IDEA: {one} and {two} have the same Concept idea, so they are one design in different colours; give each its own idea and signature visual."
                    )
                if not is_different_enough(prints[one], prints[two]):
                    lines.append(
                        f"TOO SIMILAR: {one} and {two} differ only in {', '.join(differences(prints[one], prints[two])) or 'nothing'}; change at least three of tone, accent hue, display font, corners, density, layout energy."
                    )
            for old in args.rejected:
                if not is_different_enough(prints[one], prints[old]):
                    lines.append(
                        f"TOO CLOSE TO THE REJECTED DESIGN: {one} resembles {old} (differs in {', '.join(differences(prints[one], prints[old])) or 'nothing'}); the user did not like that one."
                    )
        similar = [line for line in lines if line.startswith(("TOO SIMILAR", "TOO CLOSE"))]
        if similar and context.design_similar_refusals < MAX_SIMILAR_REFUSALS:
            context.design_similar_refusals += 1
            return ToolResult(
                ok=False,
                content="Not judged: the candidates are not different enough, so choosing among them would be choosing among copies."
                + "\n".join(lines)
                + "\nChange the similar candidates so that they differ in at least three dimensions (for example a dark candidate with a different accent hue and a different display font). "
                "Change only the candidate(s) named above and only their front matter (colors, typography, rounded, dials), with one multi_edit each; do not rewrite the whole file. "
                "Then call design_candidates again.",
            )
        if len(usable) < 2:
            return ToolResult(ok=False, content="Fewer than two usable candidates.\n" + "\n".join(lines))
        folder = context.workspace.root / CANDIDATE_FOLDER
        context.workspace.jail.check(folder)
        pictures: dict[str, Path] = {}
        try:
            for label, path in zip(LABELS, usable, strict=False):
                pictures[path] = folder / f"specimen-{label}.png"
                await draw(specimen_html(loaded[path][0], args.headline), pictures[path])
        except SpecimenUnavailable as error:
            return ToolResult(
                ok=True,
                content="\n".join(lines)
                + f"\nSpecimens could not be drawn ({error}); judge the candidates from their tokens.",
            )
        verdict: dict[str, Any] | None = None
        if context.router is not None:
            urls = [images.for_model(images.open_image(pictures[p]))[0] for p in usable]
            asked = f"Brief: {args.brief}\nCandidates in order: " + ", ".join(
                f"{label} = {path}" for label, path in zip(LABELS, usable, strict=False)
            )
            if args.rejected:
                asked += f"\nThe user rejected earlier designs ({', '.join(args.rejected)}) because: {args.rejected_reason or 'they did not like it'}."
            response = await context.ask_model(
                "critic",
                ChatRequest(
                    messages=[Message.system(RUBRIC), Message(role="user", content=asked, images=urls)]
                ),
                "comparing the candidate designs",
            )
            found = re.search(r"\{.*\}", response.text, re.S)
            try:
                verdict = json.loads(found.group(0)) if found else None
            except ValueError:
                verdict = None
        record = {
            "brief": args.brief,
            "candidates": {p: describe_fingerprint(prints[p]) for p in usable},
            "rejected": args.rejected,
            "rejected_reason": args.rejected_reason,
            "verdict": verdict,
        }
        self._remember(context, record)
        shown = ", ".join(_relative(context, pictures[p]) for p in usable)
        if verdict is None:
            return ToolResult(
                ok=True,
                content="\n".join(lines)
                + f"\nSpecimens: {shown}\nNo score was available: look at the specimens with view_image and choose yourself, and say why."
                + SHOW_CANDIDATES_NOTE,
            )
        winner = str(verdict.get("winner", ""))
        path = usable[LABELS.index(winner)] if winner in LABELS[: len(usable)] else ""
        return ToolResult(
            ok=True,
            content="\n".join(lines)
            + f"\nSpecimens: {shown}\nWinner: {winner} ({path})\n"
            + json.dumps({k: verdict.get(k) for k in ("scores", "reasons", "fixes")}, indent=1)[:3500]
            + SHOW_CANDIDATES_NOTE
            + "\nApply the winner's fixes to its DESIGN.md, then design_md_import it as the project's DESIGN.md (overwrite) and record the other candidates in its Overview."
            + _composition_next_step(loaded[path][0] if path else None),
        )

    @staticmethod
    def _remember(context: ToolContext, record: dict[str, Any]) -> None:
        file = context.workspace.root / ROUNDS_FILE
        context.workspace.jail.check(file)
        rounds: list[dict[str, Any]] = []
        if file.is_file():
            try:
                rounds = json.loads(file.read_text(encoding="utf-8"))
            except ValueError:
                rounds = []
        rounds.append(record)
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(rounds[-12:], indent=1), encoding="utf-8")


def design_candidate_tools() -> list[Tool]:
    return [DesignSpecimen(), DesignCandidates()]

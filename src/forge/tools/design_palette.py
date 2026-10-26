"""design_palette (D-490): shows colour palette options for an office app as pictures and applies the one the user picks to the project's DESIGN.md.

The office design is one accent on neutral surfaces (D-489), so the colour is the user's decision, not the model's: `show` draws four options at a time and tells the
model to put them to the user with one ask_user call; `apply` writes the choice (a palette id, or the user's own hex colours) into DESIGN.md."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from forge.brand.kit import mix
from forge.designsystem.lint import describe_findings, lint_text
from forge.designsystem.palettes import (
    PAGES,
    PALETTES,
    Palette,
    apply_palette,
    custom_palette,
    dark_variant,
    is_dark_design,
    palette_by_id,
)
from forge.errors import ForgeError
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools.design_candidates import SpecimenUnavailable, draw
from forge.tools.vision import _relative

PALETTE_FOLDER = ".forge/palettes"


def _tint(colour: str, share: float, base: str = "FFFFFF") -> str:
    return "#" + mix(base, colour.lstrip("#"), share)


def palette_html(palette: Palette, dark: bool = False) -> str:
    """A small office screen drawn in the palette: a menu with the active item, a tab row with a count, a stat tile with its icon square, status chips, a progress bar,
    a focused field and the two buttons. No network, no fonts: the shapes and colours are what is being judged."""
    primary, brand, on = palette.primary, palette.brand, palette.on_primary
    page, card, line, text, muted = (
        ("#0E1116", "#171B22", "#2A303A", "#E8EAEE", "#98A2B3")
        if dark
        else ("#F7F8FA", "#fff", "{line}", "{text}", "{muted}")
    )
    base = card.lstrip("#") if dark else "FFFFFF"
    soft, ring = _tint(brand, 0.16 if dark else 0.12, base), _tint(brand, 0.40 if dark else 0.30, base)
    ok, warn, error = ("#4ADE80", "#FBBF24", "#F87171") if dark else ("#17693D", "#8A5200", "#B42318")

    def chip(label: str, colour: str) -> str:
        return f'<span class="chip" style="background:{_tint(colour, 0.16 if dark else 0.13, base)};color:{colour};box-shadow:inset 0 0 0 1px {_tint(colour, 0.40 if dark else 0.30, base)}">{label}</span>'

    note = f"white text {palette.ratio:.1f} to 1" + (" (below the 4.5 guideline)" if palette.below_aa else "")
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box}}body{{margin:0;width:1280px;height:900px;background:{page};color:{text};font:500 22px system-ui,Segoe UI,sans-serif;display:grid;grid-template-columns:300px 1fr}}
.side{{background:{card};border-right:1px solid {line};padding:28px 20px}}.logo{{display:flex;align-items:center;gap:12px;font-weight:700;font-size:26px;margin-bottom:28px}}
.logo i{{width:44px;height:44px;border-radius:12px;background:{primary};color:{on};display:grid;place-items:center;font-style:normal}}
.item{{padding:12px 14px;border-radius:12px;color:{muted};margin-bottom:6px}}.item.on{{background:{soft};color:{primary};font-weight:700}}
.main{{padding:32px 40px}}.title{{font-size:34px;font-weight:700;letter-spacing:-.02em}}.sub{{color:{muted};font-size:19px;margin:4px 0 22px}}
.tabs{{display:flex;gap:26px;border-bottom:1px solid {line};margin-bottom:22px}}.tab{{padding:8px 2px 14px;color:{muted}}}.tab.on{{color:{primary};font-weight:700;border-bottom:3px solid {brand}}}
.count{{background:{soft};color:{primary};border-radius:999px;padding:1px 10px;font-size:16px;margin-left:8px}}
.row{{display:grid;grid-template-columns:1.1fr 1fr;gap:22px}}.card{{background:{card};border:1px solid {line};border-radius:18px;padding:22px;box-shadow:{"0 1px 2px rgba(0,0,0,.4)" if dark else "0 1px 2px rgba(16,24,40,.06),0 6px 20px rgba(16,24,40,.05)"}}}
.tile{{display:flex;justify-content:space-between}}.big{{font-size:44px;font-weight:700}}.ic{{width:56px;height:56px;border-radius:14px;background:{soft};color:{primary};box-shadow:inset 0 0 0 1px {ring};display:grid;place-items:center;font-size:26px}}
.chip{{display:inline-block;border-radius:999px;padding:3px 14px;font-size:17px;font-weight:700;margin-right:8px}}
.bar{{height:10px;border-radius:99px;background:{line};margin:18px 0}}.bar i{{display:block;width:64%;height:100%;border-radius:99px;background:{brand}}}
.field{{height:52px;border-radius:12px;border:2px solid {brand};box-shadow:0 0 0 5px {_tint(brand, 0.20)};background:{card};padding:12px 16px;color:{muted};font-size:19px}}
.btn{{display:inline-block;height:48px;line-height:48px;padding:0 24px;border-radius:12px;font-weight:700;font-size:19px;margin:18px 10px 0 0}}
.p{{background:{primary};color:{on}}}.s{{background:{card};border:1px solid {line};color:{text};line-height:46px}}
.name{{position:absolute;right:28px;bottom:20px;font-size:20px;color:{muted}}}
.line{{display:grid;grid-template-columns:1fr 160px 140px;align-items:center;padding:14px 8px;border-top:1px solid {line};font-size:20px}}.line:first-child{{border-top:0}}.line.sel{{background:{soft};border-radius:10px}}.line span:nth-child(2){{color:{muted}}}
</style></head><body>
<div class="side"><div class="logo"><i>&#9679;</i>Office</div><div class="item on">Approvals</div><div class="item">Orders</div><div class="item">Reports</div><div class="item">Settings</div></div>
<div class="main"><div class="title">Approvals</div><div class="sub">14 waiting, 2 past their deadline</div>
<div class="tabs"><div class="tab on">Open<span class="count">14</span></div><div class="tab">Mine</div><div class="tab">Done</div></div>
<div class="row"><div class="card"><div class="tile"><div><div style="color:{muted};font-size:19px">Waiting for you</div><div class="big">14</div></div><div class="ic">&#9993;</div></div>
<div class="bar"><i></i></div>{chip("In progress", brand if not palette.below_aa else primary)}{chip("Done", ok)}{chip("Overdue", error)}</div>
<div class="card"><div class="field">Search requests</div><span class="btn p">Approve</span><span class="btn s">Ask for changes</span></div></div>
<div class="card" style="margin-top:22px"><div class="line"><b>Client dinner and travel</b><span>$1,284.00</span>{chip("Review", warn)}</div>
<div class="line sel"><b>Laptop refresh, 12 units</b><span>$18,960.00</span>{chip("Overdue", error)}</div><div class="line"><b>Conference ticket</b><span>$640.00</span>{chip("Approved", ok)}</div></div>
<div class="name">{palette.name}: {note}</div></div></body></html>"""


class DesignPalette(Tool):
    name = "design_palette"
    read_only = False
    description = (
        "Colour palette for an office app, chosen by the user. action `show` draws four palette options as pictures (page 1 to 3 for more) and tells you how to put them to "
        "the user with ONE ask_user call: do this for an application or back-office design when the user has not named a colour or supplied a brand guide or DESIGN.md. "
        "action `apply` writes the choice into DESIGN.md: a palette id, or the user's own colour as `primary` (and optionally `brand`) hex."
    )

    class Args(ToolArgs):
        action: Literal["show", "apply"]
        page: int = Field(default=1, ge=1, le=3, description="show: which four palettes (1 to 3)")
        theme: Literal["light", "dark"] = Field(
            default="light", description="show: draw the options on the light or the dark office design"
        )
        palette: str = Field(default="", description="apply: a palette id, for example blue or orange-bright")
        primary: str = Field(
            default="", description="apply: the user's own colour for filled controls, as a six-digit hex"
        )
        brand: str = Field(
            default="", description="apply: the user's own accent for bars and rings (defaults to primary)"
        )
        path: str = Field(default="DESIGN.md", description="apply: the DESIGN.md to change")

    def summary(self, args: DesignPalette.Args) -> str:
        return (
            "show colour palettes"
            if args.action == "show"
            else f"apply palette {args.palette or args.primary}"
        )

    async def run(self, args: DesignPalette.Args, context: ToolContext) -> ToolResult:
        try:
            return await (self._show(args, context) if args.action == "show" else self._apply(args, context))
        except (ForgeError, OSError, SpecimenUnavailable) as error:
            return ToolResult(ok=False, content=str(error))

    async def _show(self, args: DesignPalette.Args, context: ToolContext) -> ToolResult:
        ids = PAGES[min(args.page, len(PAGES)) - 1]
        lines = []
        for identifier in ids:
            palette = palette_by_id(identifier)
            assert palette is not None
            dark = args.theme == "dark"
            shown = dark_variant(palette) if dark else palette
            target = context.workspace.root / PALETTE_FOLDER / f"{shown.id}.png"
            context.workspace.jail.check(target)
            await draw(palette_html(shown, dark), target)
            lines.append(
                f"- {palette.name} (`{palette.id}`): {palette.primary} for buttons, {palette.brand} for bars and rings; {palette.mood}; white text "
                f"{palette.ratio:.1f} to 1. Picture: {_relative(context, target)}"
            )
        more = (
            f" The user can ask for more: call design_palette show with page={args.page + 1}."
            if args.page < len(PAGES)
            else ""
        )
        return ToolResult(
            ok=True,
            content=(
                f"Palette options, page {min(args.page, len(PAGES))} of {len(PAGES)}:\n"
                + "\n".join(lines)
                + "\n\n"
                "NEXT STEP: ask the user to choose with ONE ask_user call: one option per palette (label the name, description the mood and what it is good for, image the picture path), "
                "recommend the one that fits the product, and say in the question that they can type their own colour (a hex such as #0A84FF) or ask for more."
                + more
                + "\n"
                "Then call design_palette apply with the palette id, or with primary=<their hex>. A palette marked below 4.5 to 1 is still allowed when the user picks it: "
                "tell them the contrast in one sentence, and apply records it as accepted so the checks leave it alone."
            ),
        )

    async def _apply(self, args: DesignPalette.Args, context: ToolContext) -> ToolResult:
        palette = palette_by_id(args.palette) if args.palette else custom_palette(args.primary, args.brand)
        if palette is None:
            known = ", ".join(p.id for p in PALETTES)
            return ToolResult(
                ok=False,
                content=f"No such palette. Use one of: {known}; or pass primary as a six-digit hex such as #0A84FF.",
            )
        file = context.workspace.path_of(args.path)
        if not file.is_file():
            return ToolResult(
                ok=False,
                content=f"No DESIGN.md at {args.path}: add a design system first (find_asset type design-system, 'office').",
            )
        before = file.read_text(encoding="utf-8", errors="replace")
        if is_dark_design(before):  # a dark design takes the light accent with dark text on it (BO7)
            palette = dark_variant(palette)
        after = apply_palette(before, palette)
        if after == before:
            return ToolResult(ok=False, content=f"{args.path} has no front matter with colors to change.")
        context.workspace.write_text(args.path, after, f"palette: {palette.name}")
        context.last_edit_step = context.step
        findings = [f for f in lint_text(after) if f.severity in ("error", "warning")]
        accepted = (
            f" White text on {palette.primary} is {palette.ratio:.1f} to 1, below the 4.5 guideline; it is recorded as accepted (contrast-accepted) because the user chose it."
            if palette.below_aa
            else ""
        )
        return ToolResult(
            ok=True,
            content=f"Applied the {palette.name} palette to {args.path} (primary {palette.primary}, brand {palette.brand}).{accepted}\n"
            + (
                describe_findings(findings, 10)
                if findings
                else "No lint errors. Export the tokens again with design_md_export so the code picks the new colours up."
            ),
        )


def design_palette_tools() -> list[Tool]:
    return [DesignPalette()]

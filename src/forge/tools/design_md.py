"""DESIGN.md tools (TODO DS1, D-348): design_md_lint, design_md_export, design_md_diff."""

from __future__ import annotations

from pydantic import Field

from forge.designsystem.diff import describe_diff, diff_systems
from forge.designsystem.export import FORMATS, export
from forge.designsystem.lint import describe_findings, lint_text
from forge.designsystem.spec import DesignMdError, parse_design_md
from forge.errors import ForgeError
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools.design_knowledge import repeats_recent

DEFAULT_PATH = "DESIGN.md"
SUGGESTED_OUTPUT = {
    "css-tailwind": "src/theme.css",
    "css-variables": "src/tokens.css",
    "dtcg": "design-tokens.json",
    "json-tailwind": "tailwind.theme.json",
}


def _read(context: ToolContext, path: str) -> str:
    file = context.workspace.path_of(path)
    if not file.is_file():
        raise DesignMdError(
            f"No file at {path}. Write the DESIGN.md first (recipe design-md-template.md in the ui-design-quality skill)."
        )
    return file.read_text(encoding="utf-8", errors="replace")


class DesignMdLint(Tool):
    name = "design_md_lint"
    read_only = True
    description = (
        "Check a DESIGN.md (the project's design system): valid front matter, required name and primary colour, token references that exist, "
        "units, contrast of every text-on-background pair (4.5:1), section order, one-note or over-busy palettes. Errors must be fixed before "
        "building pages; warnings should be."
    )

    class Args(ToolArgs):
        path: str = Field(default=DEFAULT_PATH, description="The DESIGN.md file")

    def summary(self, args: DesignMdLint.Args) -> str:
        return f"lint {args.path}"

    async def run(self, args: DesignMdLint.Args, context: ToolContext) -> ToolResult:
        try:
            text = _read(context, args.path)
        except (ForgeError, OSError) as error:
            return ToolResult(ok=False, content=str(error))
        content = describe_findings(lint_text(text))
        try:
            repeats = repeats_recent(text)
        except OSError:
            repeats = []
        if repeats:
            content += (
                chr(10)
                + "This design resembles a recent one ("
                + "; ".join(repeats)
                + "): change at least three of tone, accent hue, display font, corner style, density, layout energy and composition, unless the brief fixes them."
            )
        return ToolResult(ok=True, content=content)


class DesignMdExport(Tool):
    name = "design_md_export"
    read_only = False
    description = (
        "Turn the tokens of a DESIGN.md into code so pages use them instead of retyping colours: css-tailwind (a Tailwind v4 @theme block to import "
        "in your main CSS), css-variables (a :root block), dtcg (W3C design tokens JSON) or json-tailwind (Tailwind v3 theme.extend). References "
        "are resolved. Refuses a file with lint errors unless force is true. Export again after every change to DESIGN.md."
    )

    class Args(ToolArgs):
        path: str = Field(default=DEFAULT_PATH, description="The DESIGN.md file")
        format: str = Field(default="css-tailwind", description=f"One of {', '.join(FORMATS)}")
        output: str = Field(
            default="",
            description="Where to write the result; empty = the usual place for the format (e.g. src/theme.css)",
        )
        force: bool = Field(
            default=False, description="Export although lint reports errors (not recommended)"
        )

    def summary(self, args: DesignMdExport.Args) -> str:
        return f"export {args.path} as {args.format}"

    async def run(self, args: DesignMdExport.Args, context: ToolContext) -> ToolResult:
        try:
            text = _read(context, args.path)
            findings = lint_text(text)
            errors = [f for f in findings if f.severity == "error"]
            if errors and not args.force:
                return ToolResult(
                    ok=False, content="Not exported: fix these first.\n" + describe_findings(errors)
                )
            code = export(parse_design_md(text), args.format)
            target = args.output or SUGGESTED_OUTPUT.get(args.format, "design-tokens.txt")
            context.workspace.write_text(target, code, f"design tokens exported from {args.path}")
        except (ForgeError, OSError) as error:
            return ToolResult(ok=False, content=str(error))
        context.last_edit_step = context.step
        return ToolResult(
            ok=True,
            content=f"Wrote {target} ({args.format}). Import it once in the app's main stylesheet and use the variables; do not retype these values.",
        )


class DesignMdDiff(Tool):
    name = "design_md_diff"
    read_only = True
    description = (
        "Compare two DESIGN.md files (or a saved copy and the current one): which tokens were added, removed or changed, and any new lint problems "
        "(a regression when the new file has new errors). Use it before and after restyling."
    )

    class Args(ToolArgs):
        before: str = Field(description="The older DESIGN.md")
        after: str = Field(default=DEFAULT_PATH, description="The newer DESIGN.md")

    def summary(self, args: DesignMdDiff.Args) -> str:
        return f"diff {args.before} {args.after}"

    async def run(self, args: DesignMdDiff.Args, context: ToolContext) -> ToolResult:
        try:
            result = diff_systems(
                parse_design_md(_read(context, args.before)), parse_design_md(_read(context, args.after))
            )
        except (ForgeError, OSError) as error:
            return ToolResult(ok=False, content=str(error))
        return ToolResult(ok=True, content=describe_diff(result))


def design_md_tools() -> list[Tool]:
    return [DesignMdLint(), DesignMdExport(), DesignMdDiff()]

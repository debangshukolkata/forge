"""D-348: the DESIGN.md tools, the write-time lint, the design gate and the code-versus-DESIGN.md token check."""

from __future__ import annotations

import re
from pathlib import Path

from forge.designsystem.lint import lint_text
from forge.toolkit.base import ToolContext
from forge.tools.design_md import DesignMdDiff, DesignMdExport, DesignMdLint
from forge.tools.files import WriteFile, design_gate
from forge.tools.token_lint import token_lint_problems
from forge.workspace.create import create_workspace

TEMPLATE = (
    Path(__file__).resolve().parent.parent
    / "src/forge/skills/ui-design-quality/recipes/design-md-template.md"
)
COLOURS = [
    "1F3864",
    "475569",
    "FFFFFF",
    "111827",
    "4B5563",
    "F3F4F6",
    "D1D5DB",
    "15803D",
    "B45309",
    "B91C1C",
    "162B50",
]


def filled_template() -> str:
    block = re.search(r"```markdown\n(.*?)\n```", TEMPLATE.read_text(encoding="utf-8"), re.S)
    assert block, "the recipe has no markdown block"
    text = block.group(1)
    for colour in COLOURS:
        text = text.replace('"#______"', f'"#{colour}"', 1)
    return (
        text.replace("<Display font>", "Georgia")
        .replace("<Body font>", "Calibri")
        .replace("<Product>", "Acme")
    )


def test_the_recipe_template_is_itself_a_valid_design_md_once_filled_in() -> None:
    findings = lint_text(filled_template())
    assert [f for f in findings if f.severity in ("error", "warning")] == [], findings


async def test_the_tools_lint_export_and_diff(original_repo: Path, tmp_path: Path) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace)
    missing = await DesignMdLint().run(DesignMdLint.Args(), context)
    assert not missing.ok and "Write the DESIGN.md first" in missing.content
    workspace.write_text("DESIGN.md", filled_template(), "x")
    clean = await DesignMdLint().run(DesignMdLint.Args(), context)
    assert (clean.ok and "valid" in clean.content) or "0 error(s)" in clean.content
    exported = await DesignMdExport().run(DesignMdExport.Args(), context)
    assert exported.ok, exported.content
    theme = workspace.path_of("src/theme.css").read_text(encoding="utf-8")
    assert "@theme {" in theme and "--color-primary: #1F3864;" in theme
    broken = filled_template().replace('"{colors.primary}"', '"{colors.nope}"', 1)
    workspace.write_text("bad/DESIGN.md", broken, "x")
    refused = await DesignMdExport().run(DesignMdExport.Args(path="bad/DESIGN.md"), context)
    assert not refused.ok and "broken-reference" in refused.content
    workspace.write_text("DESIGN.old.md", filled_template(), "x")
    workspace.write_text("DESIGN.new.md", filled_template().replace("#1F3864", "#BBBBBB"), "x")
    compared = await DesignMdDiff().run(
        DesignMdDiff.Args(before="DESIGN.old.md", after="DESIGN.new.md"), context
    )
    assert compared.ok and "colors.primary" in compared.content and "REGRESSION" in compared.content


async def test_writing_a_design_md_shows_its_lint_findings_at_once(
    original_repo: Path, tmp_path: Path
) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace)
    saved = await WriteFile().run(
        WriteFile.Args(path="DESIGN.md", content="# Notes\n\nJust prose.\n"), context
    )
    assert saved.ok and "no-front-matter" in saved.content
    good = await WriteFile().run(WriteFile.Args(path="DESIGN.md", content=filled_template()), context)
    assert good.ok and "valid" in good.content


async def test_the_design_gate_accepts_a_clean_file_refuses_one_with_errors_and_leaves_free_text_alone(
    original_repo: Path, tmp_path: Path
) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace)
    assert "DESIGN.md" in design_gate(context, "src/App.tsx")  # none yet
    workspace.write_text(
        "DESIGN.md", filled_template().replace('"{colors.primary}"', '"{colors.nope}"', 1), "x"
    )
    refused = design_gate(context, "src/App.tsx")
    assert "errors that must be fixed" in refused and "broken-reference" in refused
    context.design_gate_rounds = 0
    workspace.write_text("DESIGN.md", filled_template(), "x")
    assert design_gate(context, "src/App.tsx") == ""
    workspace.write_text(
        "DESIGN.md", "# Brand guide\n\nUse our blue. Keep it calm.\n", "x"
    )  # a company's free-text guide is binding as it is
    assert design_gate(context, "src/App.tsx") == ""


def test_the_code_is_compared_with_the_design_md_tokens(tmp_path: Path) -> None:
    (tmp_path / "DESIGN.md").write_text(filled_template(), encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "App.tsx").write_text(
        "export const App = () => <div className='p-4'>hi</div>;\n", encoding="utf-8"
    )
    assert any("no theme tokens" in p for p in token_lint_problems(tmp_path))
    (tmp_path / "src" / "theme.css").write_text(
        "@theme {\n  --color-primary: #ff00aa;\n}\n", encoding="utf-8"
    )
    assert any("colours in DESIGN.md are theme tokens" in p for p in token_lint_problems(tmp_path))
    from forge.designsystem.export import export
    from forge.designsystem.spec import parse_design_md

    (tmp_path / "src" / "theme.css").write_text(
        export(parse_design_md(filled_template()), "css-tailwind"), encoding="utf-8"
    )
    assert not any("DESIGN.md" in p for p in token_lint_problems(tmp_path))


async def test_a_design_md_the_model_wrote_must_be_compared_with_candidates_once(
    original_repo: Path, tmp_path: Path
) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace)
    await WriteFile().run(WriteFile.Args(path="DESIGN.md", content=filled_template()), context)
    asked = design_gate(context, "src/App.tsx")
    assert "design_candidates" in asked and "differ" in asked
    assert design_gate(context, "src/App.tsx") == ""  # once only: a wrong refusal can never trap the model
    other = ToolContext(workspace=workspace)
    other.design_md_written = True
    (workspace.root / ".forge").mkdir(exist_ok=True)
    (workspace.root / ".forge" / "design-rounds.json").write_text("[]", encoding="utf-8")
    assert design_gate(other, "src/App.tsx") == ""  # candidates were compared
    imported = ToolContext(
        workspace=workspace
    )  # a file the user supplied (design_md_import never sets the flag)
    (workspace.root / ".forge" / "design-rounds.json").unlink()
    assert design_gate(imported, "src/App.tsx") == ""

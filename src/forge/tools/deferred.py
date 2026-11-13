"""Which tools are not sent to the model until it asks for them (D-561).

A session used to carry every tool's full schema in every request: about 115 tools and 22,000 tokens, over the
provider's limit of 128 once Mode B, database and MCP tools were added. Now only the core tools are sent. The
tools named here are deferred: the model sees their names and one line each inside `tool_search`, and loads the
ones a task needs (by name, by group or by keyword); a skill that names tools in its header loads them with it.
A tool that is in no group is a core tool and is always sent.
"""

from __future__ import annotations

from collections.abc import Iterable

# group -> (what the group is for, its tools). A group name works wherever a tool name does.
DEFERRED_GROUPS: dict[str, tuple[str, tuple[str, ...]]] = {
    "presentations": (
        "PowerPoint files: make, read, edit, review, preview (skill make-presentation)",
        (
            "build_presentation",
            "read_presentation",
            "edit_presentation",
            "preview_presentation",
            "review_presentation",
            "check_accessibility",
            "analyze_template",
            "describe_design",
            "analyze_reference_image",
            "compare_to_reference",
            "convert_presentation",
            "merge_presentations",
            "split_presentation",
            "unpack_presentation",
            "pack_presentation",
            "read_source_document",
            "find_icon",
        ),
    ),
    "spreadsheets": (
        "Excel files: make, read, edit, check formulas, clean a messy table (skill make-spreadsheet)",
        ("build_workbook", "read_workbook", "edit_workbook", "check_workbook", "clean_table"),
    ),
    "documents": (
        "Word files: make, edit, check; page pictures and a review of any office file (skill make-document)",
        ("build_document", "edit_document", "check_document", "preview_file", "critique_document"),
    ),
    "pdf": (
        "PDF files: make, merge, split, redact, render pages, OCR (skill pdf-toolkit); read_pdf is always loaded",
        (
            "build_pdf",
            "edit_pdf",
            "split_pdf",
            "redact_pdf",
            "extract_pdf_images",
            "pdf_render",
            "ocr_pdf",
        ),
    ),
    "design": (
        "The look of a web page: DESIGN.md, candidates, palettes, references, themes, ready-made assets, "
        "shadcn/ui, fonts, visual baselines (skill ui-design-quality)",
        (
            "design_md_lint",
            "design_md_export",
            "design_md_diff",
            "design_md_from_project",
            "design_md_import",
            "design_candidates",
            "design_specimen",
            "design_palette",
            "design_inspire",
            "design_kb_search",
            "design_kb_add",
            "theme_search",
            "find_asset",
            "add_asset",
            "shadcn_setup",
            "add_ui_component",
            "save_brand",
            "find_font",
            "fetch_font",
            "compare_designs",
            "visual_baseline",
            "visual_check",
        ),
    ),
    "pictures": (
        "Pictures: search, download, generate, measure, change, compare, OCR; view_image is always loaded",
        (
            "find_image",
            "fetch_image",
            "generate_image",
            "image_info",
            "image_ops",
            "draw_boxes",
            "compare_images",
            "ocr_image",
        ),
    ),
    "evals": (
        "Measuring what was built: eval sets, synthetic samples, mutation testing of the tests",
        ("run_eval", "synth_samples", "mutation_check"),
    ),
    "notebooks": ("Jupyter notebooks: read and edit cells", ("notebook_read", "notebook_edit_cell")),
    "remote_apps": (
        "Signing in to an environment of the user's web application (dev, SIT) and keeping the token",
        ("app_login",),
    ),
    "conversations": (
        "Earlier conversations of this project: what was asked and answered in them",
        ("conversation_recall",),
    ),
    "code_intel": (
        "Exact Python lookups: where a name is defined, who uses it, the symbols of a file",
        ("find_definition", "find_references", "list_symbols"),
    ),
}

GROUP_OF: dict[str, str] = {name: group for group, (_, names) in DEFERRED_GROUPS.items() for name in names}


MCP_PREFIX = "mcp__"  # forge.parity.mcp_client.PREFIX; not imported: this module has no dependencies


def is_deferrable(name: str) -> bool:
    """A tool in a group, and every tool of an MCP server (TR3, D-591): a server can bring dozens of schemas that a
    session mostly does not use; they wait in the `tool_search` list like the other deferred tools."""
    return name in GROUP_OF or name.startswith(MCP_PREFIX)


def expand(names: Iterable[str]) -> list[str]:
    """Tool names for a mix of tool and group names, in the order given, without repeats."""
    found: dict[str, None] = {}
    for raw in names:
        name = raw.strip()
        if name in DEFERRED_GROUPS:
            found.update(dict.fromkeys(DEFERRED_GROUPS[name][1]))
        elif name:
            found[name] = None
    return list(found)

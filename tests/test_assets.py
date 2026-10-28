"""L0: the asset catalogue validates, searches and copies assets; the committed catalogue is never out of date."""

from __future__ import annotations

import json
from pathlib import Path

from forge.parity.assets import build_catalogue, catalogue_files, load_catalogue, search
from forge.toolkit.base import ToolContext
from forge.tools.assets import AddAsset, FindAsset
from forge.workspace.create import create_workspace

SKILL = Path(__file__).resolve().parents[1] / "src" / "forge" / "skills" / "ui-design-quality"

GOOD = """---
id: fx-demo
type: effect
title: Demo effect
summary: A demo effect for tests.
moods: [calm]
products: [landing]
density: any
dependencies: []
licence: original
source: tests
tested: by the test
files:
  - {from: recipes/demo.css, to: src/demo.css}
---
Use it like this.
"""


def _skill(tmp_path: Path, asset_text: str = GOOD, name: str = "fx-demo.md", folder: str = "effect") -> Path:
    (tmp_path / "recipes").mkdir()
    (tmp_path / "recipes" / "demo.css").write_text(".demo { color: red; }\n", encoding="utf-8")
    (tmp_path / "assets" / folder).mkdir(parents=True)
    (tmp_path / "assets" / folder / name).write_text(asset_text, encoding="utf-8")
    return tmp_path


def test_a_valid_asset_builds(tmp_path: Path) -> None:
    result = build_catalogue(_skill(tmp_path))
    assert result.errors == [] and [a.id for a in result.assets] == ["fx-demo"]
    assert result.assets[0].size > len(".demo { color: red; }")
    assert any("no preview" in w for w in result.warnings)


def test_missing_licence_and_missing_file_fail_the_build(tmp_path: Path) -> None:
    bad = GOOD.replace("licence: original\n", "").replace("recipes/demo.css", "recipes/nothing.css")
    errors = build_catalogue(_skill(tmp_path, bad)).errors
    assert any("missing licence" in e for e in errors) and any("does not exist" in e for e in errors)


def test_wrong_folder_wrong_name_and_bad_target_fail(tmp_path: Path) -> None:
    errors = build_catalogue(
        _skill(tmp_path, GOOD.replace("src/demo.css", "../escape.css"), "other.md", "component")
    ).errors
    text = " | ".join(errors)
    assert "wrong folder" in text and "file name must be the id" in text and "inside the project" in text


def test_duplicate_ids_and_unreadable_front_matter_fail(tmp_path: Path) -> None:
    _skill(tmp_path)
    (tmp_path / "assets" / "effect" / "fx-copy.md").write_text(
        GOOD.replace("fx-demo", "fx-demo"), encoding="utf-8"
    )
    (tmp_path / "assets" / "effect" / "fx-broken.md").write_text("no front matter here", encoding="utf-8")
    errors = " | ".join(build_catalogue(tmp_path).errors)
    assert "already used" in errors or "file name must be the id" in errors
    assert "no front-matter" in errors


def test_the_real_catalogue_is_valid_and_up_to_date() -> None:
    result = build_catalogue(SKILL)
    assert result.errors == []
    assert len(result.assets) >= 30
    for name, text in catalogue_files(result).items():
        committed = (SKILL / "assets" / name).read_text(encoding="utf-8").replace("\r\n", "\n")
        assert committed == text, f"{name} is out of date: run scripts/build_asset_catalogue.py"
    assert {a.type for a in result.assets} >= {"direction", "effect", "component"}
    assert all(a.licence and a.source and a.tested for a in result.assets)


def test_every_skill_catalogue_is_valid_and_up_to_date() -> None:
    folders = [p.parent.parent for p in (SKILL.parent).glob("*/assets/catalogue.json")]
    assert {p.name for p in folders} >= {"ui-design-quality", "python-project"}
    for folder in folders:
        result = build_catalogue(folder)
        assert result.errors == [], folder.name
        for name, text in catalogue_files(result).items():
            committed = (folder / "assets" / name).read_text(encoding="utf-8").replace("\r\n", "\n")
            assert committed == text, (
                f"{folder.name}/{name} is out of date: run scripts/build_asset_catalogue.py"
            )


def test_every_style_direction_heading_has_an_asset() -> None:
    import re

    text = (SKILL / "recipes" / "style-directions.md").read_text(encoding="utf-8")
    headings = re.findall(r"(?m)^## (?:\d+b?\. )?([^(\n]+)", text)
    titles = {a.title.lower() for a in load_catalogue(SKILL) if a.type == "direction"}
    names = [h.strip().lower() for h in headings if h.strip().lower() != "choosing and varying"]
    assert len(titles) == len(names)


def test_search_finds_the_expected_assets() -> None:
    catalogue = load_catalogue(SKILL)
    assert search(catalogue, "warm charity landing page", "direction")[0].id == "dir-soft-editorial"
    assert search(catalogue, "numbers that count up when visible")[0].id == "fx-count-up"
    assert search(catalogue, "modal dialog", "component")[0].id == "cmp-dialog"
    assert "dir-dark-dashboard" in [a.id for a in search(catalogue, "dark dashboard for analytics")]
    assert search(catalogue, "kids play food", "direction")[0].id in {
        "dir-playful-friendly",
        "dir-claymorphism",
    }
    assert search(catalogue, "zzzzqqq") == []
    assert {a.type for a in search(catalogue, "dashboard", "direction")} == {"direction"}


def _all_assets() -> list:  # type: ignore[type-arg]
    return [a for p in SKILL.parent.glob("*/assets/catalogue.json") for a in load_catalogue(p.parent.parent)]


def _context(tmp_path: Path, original_repo: Path) -> ToolContext:
    return ToolContext(
        workspace=create_workspace(original_repo, tmp_path / "ws", "backend"), design_first=False
    )


async def test_find_asset_tool(tmp_path: Path, original_repo: Path) -> None:
    context = _context(tmp_path, original_repo)
    result = await FindAsset().run(FindAsset.Args(query="count up stats"), context)
    assert result.ok and "fx-count-up" in result.content
    nothing = await FindAsset().run(FindAsset.Args(query="zzzzqqq"), context)
    assert nothing.ok and "Nothing matched" in nothing.content
    wrong = await FindAsset().run(FindAsset.Args(query="x", type="nonsense"), context)
    assert not wrong.ok


async def test_the_catalogue_hint_names_good_matches_and_stays_silent_otherwise(
    tmp_path: Path, original_repo: Path
) -> None:
    """D-518: a request that matches the catalogue well gets its best matches put in front of the model; other requests get nothing."""
    from forge.tools.assets import catalogue_hint

    context = _context(tmp_path, original_repo)
    hint = catalogue_hint(context, "Build a warm landing page for a blood donation charity.")
    assert "tpl-landing-charity" in hint and "add_asset" in hint
    assert "fx-count-up" in catalogue_hint(
        context, "The stats section should have numbers that count up when they scroll into view."
    )
    assert catalogue_hint(context, "Fix the typo 'recieve' in the README.") == ""
    assert catalogue_hint(context, "Rename the function get_policy to fetch_policy everywhere.") == ""
    assert catalogue_hint(context, "x" * 5000) == ""  # only the start of a long message is searched


async def test_the_hint_for_each_live_retrieval_request_contains_an_acceptable_asset(
    tmp_path: Path, original_repo: Path
) -> None:
    """D-518: the 12 plain requests of the live retrieval tests each get a hint with at least one acceptable asset in it, so a change to the search or the
    catalogue that would hide the right asset fails here, in seconds, before a live run is spent on it."""
    from forge.tools.assets import catalogue_hint
    from tests.test_live_asset_retrieval import SCENARIOS

    context = _context(tmp_path, original_repo)
    for name, (request, acceptable) in SCENARIOS.items():
        hint = catalogue_hint(context, request)
        assert any(f"- {asset_id} (" in hint for asset_id in acceptable), (name, hint)


async def test_the_hint_also_serves_code_document_and_spreadsheet_requests(
    tmp_path: Path, original_repo: Path
) -> None:
    """D-518: requests for a recipe, a skeleton or a document template find them too (measured by hand on 13 requests; these are the clear ones)."""
    from forge.tools.assets import catalogue_hint

    context = _context(tmp_path, original_repo)
    expected = {
        "Add logging to the service.": "rcp-logging",
        "Create an Excel budget tracker with monthly totals and a chart.": "rcp-xl-budget",
        "Our app crashes with a stack trace in the payment code, find the cause.": "rcp-stack-trace-fixing",
        "Write a script that cleans messy data with pandas.": "rcp-data-pandas-polars",
        "Write a typer command line tool that renames files.": "rcp-typer-click",
        "Write a Word report with a title page and a table of contents.": "tpl-doc-report-clean",
    }
    for request, asset_id in expected.items():
        assert f"- {asset_id} (" in catalogue_hint(context, request), request


async def test_unrelated_requests_get_no_catalogue_hint(tmp_path: Path, original_repo: Path) -> None:
    from forge.tools.assets import catalogue_hint

    context = _context(tmp_path, original_repo)
    for request in (
        "Fix the typo 'recieve' in the README.",
        "Our claims endpoint returns a 500 for some inputs. Find out why.",
        "Explain how this repository is structured.",
        "Rename the function get_policy to fetch_policy everywhere.",
        "Why is the test suite slow?",
    ):
        assert catalogue_hint(context, request) == "", request


async def test_add_asset_copies_files_records_the_licence_and_is_idempotent(
    tmp_path: Path, original_repo: Path
) -> None:
    context = _context(tmp_path, original_repo)
    added = await AddAsset().run(AddAsset.Args(id="fx-count-up", project_dir="web"), context)
    assert added.ok and added.meta["ui_files"] is True
    assert "Usage note" in added.content and "CountUp" in added.content
    repo = context.workspace.repo_dir
    assert (repo / "web" / "src" / "motion.css").is_file() and (repo / "web" / "src" / "motion.tsx").is_file()
    notices = (repo / "web" / "NOTICES.md").read_text(encoding="utf-8")
    assert "fx-count-up" in notices and "original" in notices

    again = await AddAsset().run(AddAsset.Args(id="fx-count-up", project_dir="web"), context)
    assert again.ok and "already the same" in again.content and "Files written" not in again.content
    assert (repo / "web" / "NOTICES.md").read_text(encoding="utf-8").count("fx-count-up") == 1


async def test_add_asset_does_not_replace_a_changed_file_unless_asked(
    tmp_path: Path, original_repo: Path
) -> None:
    context = _context(tmp_path, original_repo)
    await AddAsset().run(AddAsset.Args(id="fx-float"), context)
    css = context.workspace.repo_dir / "src" / "motion.css"
    css.write_text("/* my own edits */\n", encoding="utf-8")
    kept = await AddAsset().run(AddAsset.Args(id="fx-float"), context)
    assert "exists and differs" in kept.content and css.read_text(encoding="utf-8") == "/* my own edits */\n"
    replaced = await AddAsset().run(AddAsset.Args(id="fx-float", overwrite=True), context)
    assert "Files written" in replaced.content and ".float" in css.read_text(encoding="utf-8")


async def test_a_direction_has_no_files_and_returns_its_text(tmp_path: Path, original_repo: Path) -> None:
    context = _context(tmp_path, original_repo)
    result = await AddAsset().run(AddAsset.Args(id="dir-soft-editorial"), context)
    assert result.ok and result.meta["ui_files"] is False and "Palette" in result.content
    assert not (context.workspace.repo_dir / "NOTICES.md").exists()


async def test_unknown_asset(tmp_path: Path, original_repo: Path) -> None:
    result = await AddAsset().run(AddAsset.Args(id="nope"), _context(tmp_path, original_repo))
    assert not result.ok and "find_asset" in result.content


def test_catalogue_json_is_plain_data() -> None:
    data = json.loads((SKILL / "assets" / "catalogue.json").read_text(encoding="utf-8"))
    assert data["version"] == 1 and all("id" in a and "files" in a for a in data["assets"])


RETRIEVAL_PROMPTS = [
    ("a warm landing page for a blood donation charity", "dir-soft-editorial"),
    ("loud poster style page for a music festival", "dir-bold-poster"),
    ("playful site for a kids bakery", "dir-playful-friendly"),
    ("dark analytics dashboard with dense tables", "dir-dark-dashboard"),
    ("minimal portfolio for an architect", "dir-minimal-monochrome"),
    ("retro terminal look for a developer tool", "dir-retro-terminal"),
    ("modern dark saas hero with frosted glass", "dir-glass-aurora"),
    ("clean fintech product page", "dir-clean-product"),
    ("feature overview as a bento grid", "dir-bento"),
    ("neo brutalist indie product", "dir-neo-brutalist"),
    ("stats section where the numbers count up", "fx-count-up"),
    ("scroll reveal animation with stagger", "fx-scroll-reveal"),
    ("logo strip that scrolls endlessly", "fx-marquee"),
    ("loading placeholder while data loads", "fx-skeleton"),
    ("card that glows following the mouse", "fx-spotlight-card"),
    ("modal dialog for confirmations", "cmp-dialog"),
    ("toast messages instead of alert", "cmp-toasts"),
    ("sortable searchable table", "cmp-data-table"),
    ("empty state when a list has no items", "cmp-empty-state"),
    ("keyboard accessible tabs for settings", "cmp-tabs"),
    ("new python command line tool", "skel-python-cli"),
    ("rest api service backend", "skel-fastapi-service"),
    ("background job queue worker", "skel-async-worker"),
    ("python library package", "skel-python-package"),
    ("how to handle errors and exceptions", "rcp-error-handling"),
    ("logging instead of print", "rcp-logging"),
    ("read settings from environment variables and .env", "rcp-settings"),
    ("type hints protocol dataclass mypy", "rcp-typing"),
    ("asyncio timeout and concurrency limit", "rcp-async"),
    ("pytest fixtures parametrize tests", "rcp-pytest"),
    ("sql injection safe queries sqlite", "rcp-sql"),
    ("security checklist for user input", "rcp-security"),
    ("code is slow performance profiling", "rcp-performance"),
    ("refactor duplicated if chains", "rcp-refactoring"),
    ("new python features 3.12 3.13", "rcp-python-versions"),
    ("cli exit codes subcommands stdin", "rcp-cli-design"),
    ("shake the form when validation fails", "fx-shake"),
    ("typing effect with a blinking caret", "fx-type-writer"),
    ("thin progress bar while scrolling an article", "fx-scroll-progress"),
    ("card that flips over to show the back", "fx-flip-card"),
    ("dot pattern background for a hero", "fx-bg-dots"),
    ("progress ring percentage", "fx-progress-ring"),
    ("landing page for a charity blood drive", "tpl-landing-charity"),
    ("saas product landing page with pricing", "tpl-landing-saas"),
    ("architect portfolio website", "tpl-landing-portfolio"),
    ("pricing section with three plans", "sec-pricing-tiers"),
    ("faq accordion section", "sec-faq-list"),
    ("sign up form with validation and success message", "sec-contact-form"),
    ("heartbeat loader for a health app", "mi-loader-heartbeat"),
    ("sun and moon dark mode switch", "mi-toggle-sunmoon"),
    ("button whose arrow slides right on hover", "mi-btn-arrow-slide"),
    ("label that floats above the input when focused", "mi-input-float-label"),
    ("card that flips over on hover", "mi-card-flip"),
    ("checkbox with a drawn checkmark", "mi-checkbox-draw"),
    ("colours for a clinic or hospital website", "pal-calm-clinical"),
    ("dark mode palette for a developer analytics tool", "pal-dark-mode-product"),
    ("palette for a food or grocery community site", "pal-fresh-and-friendly"),
    ("container queries and subgrid for a responsive card layout", "css-layout"),
    ("native dialog and popover instead of a javascript modal", "css-native-html-that-replaces-widgets"),
    ("scroll driven animation and view transitions", "css-animation-techniques"),
]


def test_retrieval_finds_the_expected_asset_for_at_least_90_percent_of_prompts() -> None:
    catalogue = _all_assets()
    missed = [
        (prompt, expected, [a.id for a in search(catalogue, prompt, limit=3)])
        for prompt, expected in RETRIEVAL_PROMPTS
        if expected not in [a.id for a in search(catalogue, prompt, limit=3)]
    ]
    hit_rate = 1 - len(missed) / len(RETRIEVAL_PROMPTS)
    assert hit_rate >= 0.9, f"hit rate {hit_rate:.0%}; missed: {missed}"

"""L8: the token lint flags hard-coded colours, fonts and default palette classes, and stays quiet otherwise."""

from __future__ import annotations

from pathlib import Path

from forge.tools.token_lint import token_lint_problems

THEME = """@import "tailwindcss";
@theme {
  --color-brand: #b3261e;
  --color-ink: #1f1a17;
  --font-display: "Fraunces", serif;
}
"""


def _project(tmp_path: Path, page: str, extra: dict[str, str] | None = None) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.css").write_text(THEME, encoding="utf-8")
    (tmp_path / "src" / "App.tsx").write_text(page, encoding="utf-8")
    for name, text in (extra or {}).items():
        (tmp_path / "src" / name).write_text(text, encoding="utf-8")
    return tmp_path


def test_clean_page_using_tokens_has_no_findings(tmp_path: Path) -> None:
    root = _project(tmp_path, '<h1 className="text-brand bg-ink font-display">Hi</h1>')
    assert token_lint_problems(root) == []


def test_token_values_written_literally_are_allowed(tmp_path: Path) -> None:
    root = _project(tmp_path, '<div style={{ color: "#b3261e" }} />')
    assert token_lint_problems(root) == []


def test_three_untokenised_colours_in_a_file_are_flagged(tmp_path: Path) -> None:
    page = '<div style={{ color: "#112233", background: "#445566", borderColor: "rgb(200, 30, 90)" }} />'
    problems = token_lint_problems(_project(tmp_path, page))
    assert len(problems) == 1 and "src/App.tsx (3)" in problems[0]


def test_one_odd_colour_is_tolerated(tmp_path: Path) -> None:
    assert token_lint_problems(_project(tmp_path, '<path fill="#123456" />')) == []


def test_font_outside_the_theme_and_default_palette_are_flagged(tmp_path: Path) -> None:
    page = '<p className="bg-blue-500" style={{ fontFamily: "Comic Sans MS" }}>x</p>'
    problems = token_lint_problems(_project(tmp_path, page))
    assert any("font families outside the theme" in p and "comic sans ms" in p for p in problems)
    assert any("default palette" in p for p in problems)


def test_generic_and_theme_fonts_are_fine(tmp_path: Path) -> None:
    css = "body { font-family: system-ui, sans-serif; } h1 { font-family: 'Fraunces', serif; }"
    assert token_lint_problems(_project(tmp_path, "<p/>", {"extra.css": css})) == []


def test_project_without_tokens_is_left_alone(tmp_path: Path) -> None:
    (tmp_path / "App.tsx").write_text(
        '<p className="bg-blue-500" style={{ color: "#111" }} />', encoding="utf-8"
    )
    assert token_lint_problems(tmp_path) == []


def test_our_own_reference_recipes_pass_the_lint() -> None:
    recipes = (
        Path(__file__).resolve().parents[1] / "src" / "forge" / "skills" / "ui-design-quality" / "recipes"
    )
    assert token_lint_problems(recipes) == []


def test_black_white_and_grey_overlays_are_not_counted(tmp_path: Path) -> None:
    page = '<div style={{ mask: "#000", a: "#fff", b: "rgb(255 255 255 / 0.5)", c: "rgb(15 15 20 / .5)" }} />'
    assert token_lint_problems(_project(tmp_path, page)) == []

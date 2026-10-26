"""D-490: a Tailwind 3 project's design tokens are read from tailwind.config.js and from shadcn-style CSS variables (bare HSL numbers, a .dark block)."""

from __future__ import annotations

from forge.designsystem.extract import css_from_project, draft_design_md, from_css
from forge.designsystem.lint import lint_text
from forge.designsystem.tailwind3 import colour_hex, light_variables, objects_named, read_config

CSS = """
@tailwind base;
@layer base {
  :root {
    --background: 216 20% 98%; /* page */
    --foreground: 240 4% 11%;
    --card: 0 0% 100%;
    --muted: 220 14% 96%;
    --muted-foreground: 220 9% 40%;
    --border: 220 13% 91%;
    --radius: 0.75rem;
  }
  .dark {
    --background: 220 16% 9%;
    --foreground: 210 20% 96%;
    --card: 220 15% 12%;
  }
}
@media (prefers-color-scheme: dark) { :root { --card: 1 2% 3%; } }
"""

CONFIG = """
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // semantic tokens driven by CSS variables
        border: 'hsl(var(--border))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        card: { DEFAULT: 'hsl(var(--card))', foreground: 'hsl(var(--card-foreground))' },
        muted: { DEFAULT: 'hsl(var(--muted))', foreground: 'hsl(var(--muted-foreground))' },
        primary: { DEFAULT: '#0F766E', foreground: '#ffffff', 50: '#F0FDFA', 100: '#CCFBF1', 200: '#99F6E4', 300: '#5EEAD4', 400: '#2DD4BF', 500: '#14B8A6', 600: '#0D9488', 700: '#0F766E' },
        success: { DEFAULT: '#16A34A' },
        warning: { DEFAULT: '#D97706' },
        danger: { DEFAULT: '#DC2626' },
        info: { DEFAULT: '#2563EB' },
      },
      borderRadius: { lg: 'var(--radius)', md: 'calc(var(--radius) - 2px)' },
      fontFamily: {
        sans: ['Inter', 'Tiro Bangla', 'ui-sans-serif', 'system-ui'],
        display: ["Fraunces", "serif"],
      },
      boxShadow: { card: '0 6px 20px rgba(0,0,0,.06)' },
    },
  },
  plugins: [],
}
"""


def test_the_light_theme_is_taken_apart_from_the_dark_one() -> None:
    variables = light_variables(CSS)
    assert (
        variables["background"] == "216 20% 98%" and variables["card"] == "0 0% 100%"
    )  # not the .dark nor the media-query values
    assert variables["radius"] == "0.75rem"


def test_bare_hsl_numbers_and_variable_references_become_hex() -> None:
    variables = light_variables(CSS)
    assert colour_hex("216 20% 98%", variables) == "#F9FAFB"
    assert colour_hex("hsl(var(--background))", variables) == "#F9FAFB"
    assert colour_hex("hsl(var(--background) / <alpha-value>)", variables) == "#F9FAFB"
    assert colour_hex("hsl(var(--missing))", variables) is None
    assert colour_hex("#0f766e", variables) == "#0F766E" and colour_hex("not a colour", variables) is None


def test_css_variables_in_the_shadcn_pattern_give_the_page_ink_surface_muted_text_and_border() -> None:
    found = from_css(CSS)
    assert (
        found.colors["neutral"] == "#F9FAFB"
        and found.colors["surface"] == "#FFFFFF"
        and found.colors["border"] == "#E5E7EB"
    )
    assert (
        found.colors["muted"] == colour_hex("220 9% 40%", {}) != colour_hex("220 14% 96%", {})
    )  # the muted TEXT, not the pale muted background
    assert 12.0 in found.radii


def test_the_config_is_parsed_as_an_object_literal_without_running_it() -> None:
    colours = objects_named(CONFIG, "colors")[0]
    assert (
        colours["primary"]["DEFAULT"] == "#0F766E"
        and colours["card"]["foreground"] == "hsl(var(--card-foreground))"
    )
    assert objects_named(CONFIG, "fontFamily")[0]["sans"][:2] == ["Inter", "Tiro Bangla"]


def test_the_config_gives_the_brand_status_colours_fonts_and_the_scales() -> None:
    read = read_config(CONFIG, light_variables(CSS))
    assert (
        read["colors"]["primary"] == "#0F766E"
        and read["colors"]["ok"] == "#16A34A"
        and read["colors"]["warn"] == "#D97706"
    )
    assert read["colors"]["error"] == "#DC2626" and read["colors"]["info"] == "#2563EB"
    assert read["colors"]["neutral"] == "#F9FAFB" and read["colors"]["ink"].startswith(
        "#"
    )  # through the CSS variables
    assert read["ramps"] == ["primary"]
    assert read["fonts"]["sans"][0] == "Inter" and read["fonts"]["display"][0] == "Fraunces"


def test_a_project_with_a_config_and_a_stylesheet_gives_a_design_md_that_lints_clean() -> None:
    found = css_from_project({"src/index.css": CSS, "tailwind.config.js": CONFIG})
    assert found.colors["primary"] == "#0F766E" and found.colors["neutral"] == "#F9FAFB"
    assert found.fonts[0] == "Inter" and any("Tailwind 3" in note for note in found.notes)
    assert any("Tiro Bangla" in note for note in found.notes)  # the Bengali fallback is remembered
    draft = draft_design_md(found, "Acme", "the project's own style files")
    assert "#0F766E" in draft
    assert [f for f in lint_text(draft) if f.severity == "error"] == []


def test_a_config_alone_is_enough_and_a_broken_one_is_survived() -> None:
    assert css_from_project({"tailwind.config.js": CONFIG}).colors["primary"] == "#0F766E"
    broken = "export default { theme: { extend: { colors: { primary: '#123456', oops: { , } , } } }"
    assert css_from_project({"tailwind.config.js": broken}).colors["primary"] == "#123456"

"""Builds the micro-interaction kit of the ui-design-quality skill (D-382): one stylesheet, forty catalogue effects.

    python scripts/dev/make_micro_effects.py

Reads the definitions in scripts/dev/micro_effects/ and writes recipes/motion-micro.css and assets/effect/mi-*.md. Run scripts/build_asset_catalogue.py afterwards. The effects are
written for DebCraft (no third-party code or catalogue was used): loaders, toggles, buttons, inputs and cards, plain CSS, tokens with fallbacks, switched off under
prefers-reduced-motion. tests/test_micro_effects.py proves each one in Edge from the same definitions."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "dev"))

from micro_effects.defs_controls import CONTROLS  # noqa: E402
from micro_effects.defs_surfaces import SURFACES  # noqa: E402
from micro_effects.model import Effect  # noqa: E402

SKILL = REPO / "src" / "forge" / "skills" / "ui-design-quality"
EFFECTS: list[Effect] = [*CONTROLS, *SURFACES]
HEADER = (
    "/* Micro-interactions (D-382): forty small, self-contained effects for loaders, toggles, buttons, inputs and cards. Every class is prefixed mi-. They read the project's tokens\n"
    "   (--color-primary, --color-ink, --color-surface, --color-border, --color-muted, --color-on-primary, --color-danger, --color-accent2, --r, --radius) with fallbacks, and stop\n"
    "   under prefers-reduced-motion. Import this file once; use only the classes you need and delete the rest. */\n"
)
REDUCED = '@media (prefers-reduced-motion:reduce){[class*="mi-"],[class*="mi-"] *,[class*="mi-"]::before,[class*="mi-"]::after{animation:none!important;transition-duration:.01ms!important;transition-delay:0s!important}}\n'
SOURCE = "authored for DebCraft (micro-interaction kit, D-382)"
TESTED = "demo page in Edge: the action (hover, focus, check, press or invalid) changes the probed property or the animation runs, and it is switched off under reduced motion (tests/test_micro_effects.py, D-382)"


def stylesheet() -> str:
    parts = [HEADER]
    kind = ""
    for effect in EFFECTS:
        if effect.kind != kind:
            kind = effect.kind
            parts.append(f"\n/* --- {kind}s --- */\n")
        parts.append(f"/* {effect.id}: {effect.title}. {effect.summary} */\n{effect.css}\n")
    parts.append("\n" + REDUCED)
    return "".join(parts)


def asset_markdown(effect: Effect) -> str:
    tags = ", ".join(["animation", "motion", "micro-interaction", effect.kind, "css", "no build step"])
    lines = [
        "---",
        f"id: {effect.id}",
        "type: effect",
        f'title: "{effect.title}"',
        f'summary: "{effect.summary}"',
        f"moods: [{', '.join(effect.moods)}]",
        f"products: [{', '.join(effect.products)}]",
        f"tags: [{tags}]",
        "density: any",
        "dependencies: []",
        "licence: original",
        f'source: "{SOURCE}"',
        f'tested: "{TESTED}"',
        "files:",
        "  - from: recipes/motion-micro.css",
        "    to: src/motion-micro.css",
        "---",
        "",
        f"## {effect.title}",
        "",
        f"{effect.summary} {effect.note}",
        "",
        "Markup:",
        "",
        "```html",
        effect.demo,
        "```",
        "",
        'Import the stylesheet once, after index.css: `import "./motion-micro.css"` (it holds all forty micro-interactions; keep the classes you use). It reads the project\'s tokens with fallbacks and stops under `prefers-reduced-motion`; do not rely on motion alone to say something (show a text state too).',
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ids = [e.id for e in EFFECTS]
    assert len(ids) == len(set(ids)) == 40, f"expected forty distinct effects, got {len(ids)}"
    (SKILL / "recipes" / "motion-micro.css").write_text(stylesheet(), encoding="utf-8", newline="\n")
    folder = SKILL / "assets" / "effect"
    for effect in EFFECTS:
        (folder / f"{effect.id}.md").write_text(asset_markdown(effect), encoding="utf-8", newline="\n")
    print(f"wrote recipes/motion-micro.css and {len(EFFECTS)} effects")
    return 0


if __name__ == "__main__":
    sys.exit(main())

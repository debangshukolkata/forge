"""React versions of the seven page compositions (TODO DS7 remainder, D-398).

    python scripts/dev/make_react_compositions.py

Each recipes/compositions/<name>.html becomes recipes/compositions-react/<name>/ with `Composition.tsx` (the converted body, same class names and sample content),
`composition.css` (the stylesheet without its :root block) and `tokens.css` (the :root block), plus a catalogue entry assets/section/lay-react-<name>.md. It uses the same
HTML-to-JSX converter as the application screens (scripts/dev/app_screens/jsx.py), so the structure cannot drift from the HTML recipe."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app_screens.jsx import html_to_jsx  # noqa: E402

SKILL = REPO / "src" / "forge" / "skills" / "ui-design-quality"
SOURCE_FOLDER = SKILL / "recipes" / "compositions"
TARGET_FOLDER = SKILL / "recipes" / "compositions-react"
SOURCE = "authored for DebCraft (D-354 compositions, converted to React in D-398)"
TESTED = "built with Vite and React (type-checked), rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing (tests/test_compositions_react.py, D-398)"


def split(html: str) -> tuple[str, str, str, str]:
    """(title, the :root block, the rest of the stylesheet, the body markup) of one composition file."""
    title = re.search(r"<title>(.*?)</title>", html, re.S)
    style = re.search(r"<style>(.*?)</style>", html, re.S)
    body = re.search(r"<body[^>]*>(.*)</body>", html, re.S)
    if not (title and style and body):
        raise ValueError("a composition needs a title, one style element and a body")
    root = re.search(r"^:root\{.*?\}\s*$", style.group(1), re.S | re.M)
    root_block = root.group(0).strip() if root else ":root{}"
    css = style.group(1).replace(root_block, "", 1).strip()
    return title.group(1).strip(), root_block, css, body.group(1).strip()


def component(name: str, jsx: str) -> str:
    types = 'import type { CSSProperties } from "react";\n' if "as CSSProperties" in jsx else ""
    return (
        f"// Composition `{name}` (React): the structure and class names of the HTML recipe with the same sample content. Replace the words and the drawn art with the product's own,\n"
        "// replace tokens.css with the tokens exported from DESIGN.md, and split it into components if the page grows. The colours and fonts come from CSS variables.\n"
        + types
        + 'import "./tokens.css";\nimport "./composition.css";\n\n'
        "export default function Composition() {\n  return (\n    <>\n"
        + "\n".join("      " + line for line in jsx.splitlines())
        + "\n    </>\n  );\n}\n"
    )


def asset(name: str, title: str, original: str) -> str:
    base = f"recipes/compositions-react/{name}"
    target = f"src/compositions/{name}"
    meta = dict(re.findall(r"^(moods|products|density|summary): ?(.*)$", original, re.M))
    summary = meta.get("summary", "").strip().strip('"')
    lines = [
        "---",
        f"id: lay-react-{name}",
        "type: section",
        f'title: "React composition: {title}"',
        f'summary: "{summary} (React, TSX with plain CSS.)"',
        f"moods: {meta.get('moods', '[]')}",
        f"products: {meta.get('products', '[]')}",
        "tags: [react, tsx, plain css, composition, layout, drawn svg art]",
        f"density: {meta.get('density', 'balanced')}",
        "dependencies: []",
        "licence: original",
        f'source: "{SOURCE}"',
        f'tested: "{TESTED}"',
        "files:",
        f"  - from: {base}/Composition.tsx",
        f"    to: {target}/Composition.tsx",
        f"  - from: {base}/composition.css",
        f"    to: {target}/composition.css",
        f"  - from: {base}/tokens.css",
        f"    to: {target}/tokens.css",
        "---",
        f"The React version of the composition `lay-{name}`: the same layout, class names and drawn art as the HTML file, as a component with its own stylesheet and a token file. "
        "Copy the three files, replace `tokens.css` with the tokens exported from DESIGN.md (`design_md_export css-variables`), replace the sample words and redraw the SVG for the "
        "product, and render `<Composition />` from the app. Use it as the layout of one candidate in `design_candidates` (`composition: lay-react-"
        + name
        + "` is also accepted); "
        "do not ship it unchanged.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    for source in sorted(SOURCE_FOLDER.glob("*.html")):
        name = source.stem
        title, root_block, css, body = split(source.read_text(encoding="utf-8"))
        folder = TARGET_FOLDER / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "Composition.tsx").write_text(
            component(name, html_to_jsx(body)), encoding="utf-8", newline="\n"
        )
        (folder / "composition.css").write_text(css + "\n", encoding="utf-8", newline="\n")
        (folder / "tokens.css").write_text(root_block + "\n", encoding="utf-8", newline="\n")
        original = (SKILL / "assets" / "section" / f"lay-{name}.md").read_text(encoding="utf-8")
        (SKILL / "assets" / "section" / f"lay-react-{name}.md").write_text(
            asset(name, title, original), encoding="utf-8", newline="\n"
        )
        print("wrote", name)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Write a DESIGN.md's tokens as code (D-348): Tailwind v4 `@theme` CSS, CSS variables, W3C design tokens, Tailwind v3 JSON.

Every `{reference}` is resolved to its value first, so the output has no references left. Components are not exported: they are patterns to
build with these tokens, not tokens."""

from __future__ import annotations

import json
import re
from typing import Any

from forge.designsystem.spec import DesignMdError, DesignSystem

FORMATS = ("css-tailwind", "css-variables", "dtcg", "json-tailwind")
ALIASES = {"tailwind": "json-tailwind", "tailwind-v4": "css-tailwind", "css": "css-variables"}
MONO = re.compile(r"mono|code|courier", re.I)
SERIF = re.compile(r"serif|georgia|times|garamond|fraunces|playfair|merriweather|lora", re.I)


def _name(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def _value(system: DesignSystem, group: str, name: str, value: Any) -> Any:
    resolved = system.resolve(value)
    if resolved is None:
        raise DesignMdError(
            f"{group}.{name} points to a token that does not exist: fix it with design_md_lint first"
        )
    return resolved


def _dimension(value: Any) -> str:
    return f"{value}px" if isinstance(value, (int, float)) else str(value)


def _families(system: DesignSystem) -> dict[str, str]:
    """Font family per typography token, with a generic fallback appended so a missing font never falls back to the browser default."""
    found: dict[str, str] = {}
    for name, style in system.typography.items():
        if isinstance(style, dict) and style.get("fontFamily"):
            family = str(system.resolve(style["fontFamily"]))
            if MONO.search(family):
                generic = "monospace"
            elif SERIF.search(family) and "sans" not in family.lower():
                generic = "serif"
            else:
                generic = "sans-serif"
            parts = [p.strip().strip("\"'") for p in family.split(",") if p.strip()]
            quoted = ", ".join(f'"{p}"' if " " in p else p for p in parts)
            has_generic = any(p.lower() in ("serif", "sans-serif", "monospace", "system-ui") for p in parts)
            found[_name(name)] = quoted if has_generic else f"{quoted}, {generic}"
    return found


def _entries(system: DesignSystem) -> list[tuple[str, str]]:
    """(css variable, value) pairs for every token."""
    entries: list[tuple[str, str]] = []
    for name, value in system.colors.items():
        entries.append((f"--color-{_name(name)}", str(_value(system, "colors", name, value))))
    for name, family in _families(system).items():
        entries.append((f"--font-{name}", family))
    for name, style in system.typography.items():
        if not isinstance(style, dict):
            continue
        key = _name(name)
        if style.get("fontSize") is not None:
            entries.append((f"--text-{key}", str(_value(system, "typography", name, style["fontSize"]))))
        for css, source in (
            ("line-height", "lineHeight"),
            ("letter-spacing", "letterSpacing"),
            ("font-weight", "fontWeight"),
        ):
            if style.get(source) is not None:
                entries.append((f"--text-{key}--{css}", str(system.resolve(style[source]))))
    for name, value in system.rounded.items():
        entries.append((f"--radius-{_name(name)}", str(_value(system, "rounded", name, value))))
    for name, value in system.spacing.items():
        entries.append((f"--spacing-{_name(name)}", _dimension(_value(system, "spacing", name, value))))
    return entries


def to_tailwind_css(system: DesignSystem) -> str:
    body = "\n".join(f"  {variable}: {value};" for variable, value in _entries(system))
    return f"/* Generated from DESIGN.md ({system.name}); edit DESIGN.md and export again. */\n@theme {{\n{body}\n}}\n"


def to_css_variables(system: DesignSystem) -> str:
    body = "\n".join(f"  {variable}: {value};" for variable, value in _entries(system))
    return f"/* Generated from DESIGN.md ({system.name}); edit DESIGN.md and export again. */\n:root {{\n{body}\n}}\n"


def to_dtcg(system: DesignSystem) -> str:
    """W3C Design Tokens Format Module (JSON with $type and $value)."""
    tree: dict[str, Any] = {}
    for name, value in system.colors.items():
        tree.setdefault("color", {})[name] = {
            "$type": "color",
            "$value": _value(system, "colors", name, value),
        }
    for name, style in system.typography.items():
        if isinstance(style, dict):
            tree.setdefault("typography", {})[name] = {
                "$type": "typography",
                "$value": {k: system.resolve(v) for k, v in style.items()},
            }
    for name, value in system.rounded.items():
        tree.setdefault("radius", {})[name] = {
            "$type": "dimension",
            "$value": _value(system, "rounded", name, value),
        }
    for name, value in system.spacing.items():
        tree.setdefault("spacing", {})[name] = {
            "$type": "dimension",
            "$value": _dimension(_value(system, "spacing", name, value)),
        }
    return json.dumps(tree, indent=2) + "\n"


def to_tailwind_json(system: DesignSystem) -> str:
    """Tailwind v3 `theme.extend` object."""
    extend: dict[str, Any] = {}
    if system.colors:
        extend["colors"] = {_name(n): _value(system, "colors", n, v) for n, v in system.colors.items()}
    families = _families(system)
    if families:
        extend["fontFamily"] = {n: [p.strip() for p in f.split(",")] for n, f in families.items()}
    sizes: dict[str, Any] = {}
    for name, style in system.typography.items():
        if isinstance(style, dict) and style.get("fontSize") is not None:
            options: dict[str, Any] = {}
            for key in ("lineHeight", "letterSpacing", "fontWeight"):
                if style.get(key) is not None:
                    resolved = system.resolve(style[key])
                    options[key] = str(resolved) if key == "fontWeight" else resolved
            sizes[_name(name)] = [system.resolve(style["fontSize"]), options]
    if sizes:
        extend["fontSize"] = sizes
    if system.rounded:
        extend["borderRadius"] = {
            _name(n): _value(system, "rounded", n, v) for n, v in system.rounded.items()
        }
    if system.spacing:
        extend["spacing"] = {
            _name(n): _dimension(_value(system, "spacing", n, v)) for n, v in system.spacing.items()
        }
    return json.dumps({"theme": {"extend": extend}}, indent=2) + "\n"


def export(system: DesignSystem, fmt: str) -> str:
    fmt = ALIASES.get(fmt, fmt)
    if fmt == "css-tailwind":
        return to_tailwind_css(system)
    if fmt == "css-variables":
        return to_css_variables(system)
    if fmt == "dtcg":
        return to_dtcg(system)
    if fmt == "json-tailwind":
        return to_tailwind_json(system)
    raise DesignMdError(f"Unknown format {fmt!r}. Formats: {', '.join(FORMATS)}")

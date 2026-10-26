"""Design tokens of a Tailwind 3 project (D-490).

Tailwind 4 keeps its tokens in CSS (`@theme`), which `extract.from_css` reads. A Tailwind 3 project keeps the palette in `tailwind.config.js` and, when it follows the
shadcn pattern, the surface colours in CSS variables written as bare numbers (`--background: 216 20% 98%`) with a `.dark` block that overrides them. This module reads
both without running any JavaScript: the config is parsed as an object literal (strings, numbers, nested objects and arrays; anything else is skipped), the light
theme's variables are taken apart from the dark ones, and `hsl(var(--x))` references are resolved to hex."""

from __future__ import annotations

import re
from typing import Any

from forge.designsystem.colour import parse, to_hex

TRIPLET = re.compile(r"^\s*(-?\d+(?:\.\d+)?)(?:deg)?\s+(\d+(?:\.\d+)?)%\s+(\d+(?:\.\d+)?)%\s*$")
RGB_TRIPLET = re.compile(r"^\s*(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s*$")
DARK = re.compile(
    r"\.dark\b|\[data-theme=['\"]?dark|prefers-color-scheme:\s*dark|\.theme-dark|\[data-mode=['\"]?dark",
    re.IGNORECASE,
)
VARIABLE_REFERENCE = re.compile(r"^(hsla?|rgba?)\(\s*var\(--([\w-]+)\)", re.IGNORECASE)
PLAIN_REFERENCE = re.compile(r"^var\(--([\w-]+)\)$")
CONFIG_NAMES = ("tailwind.config.js", "tailwind.config.cjs", "tailwind.config.mjs", "tailwind.config.ts")
MAX_DEPTH = 6

ROLES: dict[str, tuple[str, ...]] = {
    "primary": ("primary",),
    "secondary": ("secondary",),
    "accent": ("accent",),
    "ok": ("success", "ok", "positive"),
    "warn": ("warning", "warn"),
    "error": ("danger", "destructive", "error"),
    "info": ("info",),
    "neutral": ("background",),
    "ink": ("foreground",),
    "surface": ("card", "popover"),
    "border": ("border",),
    "muted": ("muted-foreground",),
}


def light_variables(css: str) -> dict[str, str]:
    """The custom properties of the light theme: blocks under `.dark`, `[data-theme=dark]` or `prefers-color-scheme: dark` are left out, and the last
    light definition of a name wins."""
    return _variables(css, dark=False)


def dark_variables(css: str) -> dict[str, str]:
    """Only the custom properties set inside a dark-theme block (BO8): the overrides of the light values, last definition winning."""
    return _variables(css, dark=True)


def _variables(css: str, dark: bool) -> dict[str, str]:
    text = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    stack: list[str] = []
    declarations: list[list[str]] = []
    found: dict[str, str] = {}
    prelude = ""
    for char in text:
        if char == "{":
            stack.append(prelude.strip())
            declarations.append([])
            prelude = ""
        elif char == "}":
            if declarations:
                tail = prelude.strip()
                if tail:
                    declarations[-1].append(tail)
                if bool(DARK.search(" ".join(stack))) == dark:
                    for declaration in declarations[-1]:
                        match = re.match(r"^--([\w-]+)\s*:\s*(.+)$", declaration, re.DOTALL)
                        if match:
                            found[match.group(1)] = match.group(2).strip()
                stack.pop()
                declarations.pop()
            prelude = ""
        elif char == ";":
            if declarations and prelude.strip():
                declarations[-1].append(prelude.strip())
            prelude = ""
        else:
            prelude += char
    return found


def colour_hex(value: str, variables: dict[str, str], depth: int = 0) -> str | None:
    """A colour as `#RRGGBB`: a hex or functional colour, `hsl(var(--x))`, `rgb(var(--x))` or `var(--x)` (resolved through `variables`, bare triplets understood)."""
    text = value.strip()
    if depth > MAX_DEPTH:
        return None
    reference = VARIABLE_REFERENCE.match(text)
    if reference:
        raw = variables.get(reference.group(2), "")
        function = reference.group(1).lower().rstrip("a")
        if TRIPLET.match(raw) and function == "hsl":
            text = f"hsl({raw.strip()})"
        elif RGB_TRIPLET.match(raw) and function == "rgb":
            text = f"rgb({raw.strip()})"
        else:
            return None
    else:
        plain = PLAIN_REFERENCE.match(text)
        if plain:
            return colour_hex(variables.get(plain.group(1), ""), variables, depth + 1)
        triplet = TRIPLET.match(text)
        if triplet:
            text = f"hsl({text})"
    parsed = parse(text)
    if parsed is None or parsed[3] < 0.95:
        return None
    return "#" + to_hex(parsed)


# --- a JavaScript object literal, as far as a config needs ---------------------------------------------------------------------------------


def _skip(text: str, index: int) -> int:
    while index < len(text):
        if text[index].isspace():
            index += 1
        elif text.startswith("//", index):
            index = text.find("\n", index)
            index = len(text) if index < 0 else index
        elif text.startswith("/*", index):
            index = text.find("*/", index)
            index = len(text) if index < 0 else index + 2
        else:
            break
    return index


def _string(text: str, index: int) -> tuple[str, int]:
    quote = text[index]
    out = ""
    index += 1
    while index < len(text) and text[index] != quote:
        if text[index] == "\\" and index + 1 < len(text):
            index += 1
        out += text[index]
        index += 1
    return out, index + 1


def _raw(text: str, index: int) -> tuple[str, int]:
    """Anything else (a call, a name, an expression): read to the next comma or closing bracket at the same depth."""
    start, depth = index, 0
    while index < len(text):
        char = text[index]
        if char in "([{":
            depth += 1
        elif char in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif char in "\"'`":
            _, index = _string(text, index)
            continue
        elif char == "," and depth == 0:
            break
        index += 1
    return text[start:index].strip(), index


def _value(text: str, index: int, depth: int) -> tuple[Any, int]:
    index = _skip(text, index)
    if index >= len(text):
        return "", index
    char = text[index]
    if char == "{" and depth < MAX_DEPTH:
        return _object(text, index, depth + 1)
    if char == "[":
        items: list[Any] = []
        index += 1
        while index < len(text):
            index = _skip(text, index)
            if index >= len(text) or text[index] == "]":
                return items, index + 1
            if text[index] == ",":
                index += 1
                continue
            item, index = _value(text, index, depth + 1)
            items.append(item)
        return items, index
    if char in "\"'`":
        return _string(text, index)
    return _raw(text, index)


def _object(text: str, index: int, depth: int = 0) -> tuple[dict[str, Any], int]:
    """Parses `{ key: value, ... }` starting at the opening brace; returns the dict and the index after the closing brace."""
    result: dict[str, Any] = {}
    index += 1
    while index < len(text):
        index = _skip(text, index)
        if index >= len(text):
            break
        char = text[index]
        if char == "}":
            return result, index + 1
        if char == ",":
            index += 1
            continue
        if char in "\"'":
            key, index = _string(text, index)
        elif char == "[" or text.startswith("...", index):
            _, index = _raw(text, index)
            continue
        else:
            match = re.match(r"[\w$-]+", text[index:])
            if match is None:
                index += 1
                continue
            key, index = match.group(0), index + match.end()
        index = _skip(text, index)
        if index < len(text) and text[index] == ":":
            value, index = _value(text, index + 1, depth)
            result[key] = value
        # a shorthand entry (`key,`) or a method is skipped by the loop
    return result, index


def objects_named(text: str, key: str) -> list[dict[str, Any]]:
    """Every object literal assigned to `key` in the config (the theme's own and the `extend` one), in the order they appear."""
    found: list[dict[str, Any]] = []
    for match in re.finditer(rf"[\s,{{]{re.escape(key)}\s*:\s*\{{", text):
        parsed, _ = _object(text, match.end() - 1)
        found.append(parsed)
    return found


def _flatten(colours: dict[str, Any]) -> dict[str, str]:
    flat: dict[str, str] = {}
    for name, value in colours.items():
        if isinstance(value, str):
            flat[name] = value
        elif isinstance(value, dict):
            for shade, inner in value.items():
                if isinstance(inner, str):
                    flat[name if shade == "DEFAULT" else f"{name}-{shade}"] = inner
    return flat


def read_config(text: str, variables: dict[str, str]) -> dict[str, Any]:
    """What a Tailwind 3 config says about the design: `colors` (role to hex), `ramps` (names that have a 50 to 950 scale), `fonts` (first family of each key), `radii` (px)."""
    flat: dict[str, str] = {}
    ramps: list[str] = []
    for scale in objects_named(text, "colors"):
        flat.update(_flatten(scale))
        ramps += [
            name
            for name, value in scale.items()
            if isinstance(value, dict) and sum(k.isdigit() for k in value) >= 5
        ]
    resolved = {name: hexed for name, value in flat.items() if (hexed := colour_hex(value, variables))}
    colours: dict[str, str] = {}
    for role, aliases in ROLES.items():
        found = next((resolved[n] for n in aliases if n in resolved), None)
        if found:
            colours[role] = found
    fonts: dict[str, list[str]] = {}
    for families in objects_named(text, "fontFamily"):
        for name, value in families.items():
            items = value if isinstance(value, list) else [value] if isinstance(value, str) else []
            family_names = [str(item).strip() for item in items if isinstance(item, str)]
            if family_names:
                fonts[name] = family_names
    radii: list[float] = []
    for radius in objects_named(text, "borderRadius"):
        for value in radius.values():
            if not isinstance(value, str):
                continue
            reference = PLAIN_REFERENCE.match(value.strip())
            raw = variables.get(reference.group(1), "") if reference else value
            match = re.match(r"^(-?\d+(?:\.\d+)?)(px|rem)?$", raw.strip())
            if match:
                radii.append(float(match.group(1)) * (16 if match.group(2) == "rem" else 1))
    return {
        "colors": colours,
        "ramps": sorted(set(ramps)),
        "fonts": fonts,
        "radii": sorted(set(radii)),
        "shadows": _named_strings(text, "boxShadow"),
        "spacing": _named_strings(text, "spacing"),
        "screens": _screens(text),
        "plugins": sorted(set(re.findall(r"require\(\s*['\"]([^'\"]+)['\"]\s*\)", text))),
        "dark_mode": _dark_mode(text),
    }


def _named_strings(text: str, key: str) -> dict[str, str]:
    """The string entries of every `key: { ... }` object in the config (theme and extend), later ones winning."""
    found: dict[str, str] = {}
    for block in objects_named(text, key):
        found.update({name: value.strip() for name, value in block.items() if isinstance(value, str)})
    return found


def _screens(text: str) -> dict[str, int]:
    """Breakpoints in px (`md: '768px'`); values in rem are converted, other forms skipped."""
    screens: dict[str, int] = {}
    for name, value in _named_strings(text, "screens").items():
        match = re.match(r"^(\d+(?:\.\d+)?)(px|rem)?$", value)
        if match:
            screens[name] = round(float(match.group(1)) * (16 if match.group(2) == "rem" else 1))
    return screens


def _dark_mode(text: str) -> str:
    match = re.search(r"darkMode\s*:\s*(?:\[\s*)?['\"](\w+)['\"]", text)
    return match.group(1) if match else ""

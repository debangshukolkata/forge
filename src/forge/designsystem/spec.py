"""Read a DESIGN.md: YAML front matter (tokens) plus ordered prose sections (D-348).

The format is the open DESIGN.md specification of Google Labs (alpha). Required: a name. Optional: version, description, omitted, and the token
groups colors, typography, rounded, spacing, components. A token reference is a string in braces that names another token, `{colors.primary}`.
Anything the specification does not know (extra keys, extra headings) is kept, not rejected."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import yaml

from forge.errors import ForgeError

FRONT_MATTER = re.compile(r"\A\s*---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)
REFERENCE = re.compile(r"^\{([A-Za-z0-9_.\-]+)\}$")
TOKEN_GROUPS = ("colors", "typography", "rounded", "spacing", "components")
# The specification's section order. Aliases map to the canonical name.
SECTION_ORDER = (
    "overview",
    "colors",
    "typography",
    "layout",
    "elevation",
    "shapes",
    "components",
    "dos-and-donts",
)
SECTION_ALIASES = {
    "overview": "overview",
    "brand & style": "overview",
    "brand and style": "overview",
    "colors": "colors",
    "colours": "colors",
    "color": "colors",
    "typography": "typography",
    "layout": "layout",
    "layout & spacing": "layout",
    "layout and spacing": "layout",
    "elevation & depth": "elevation",
    "elevation and depth": "elevation",
    "elevation": "elevation",
    "shapes": "shapes",
    "components": "components",
    "do's and don'ts": "dos-and-donts",
    "dos and donts": "dos-and-donts",
    "do's & don'ts": "dos-and-donts",
}
# Headings that are part of our extended format and the sites' files: kept, never reported as unknown.
KNOWN_EXTRAS = {
    "responsive behavior",
    "responsive behaviour",
    "known gaps",
    "design read and dials",
    "design read",
    "imagery and icons",
    "inspiration",
    "experience",
    "story",
    "page story",
    "journey",
    "page composition",
    "section composition",
    "motion and interaction",
    "motion",
    "accessibility",
}


class DesignMdError(ForgeError):
    """The file cannot be read as a DESIGN.md; the message says what to change."""


@dataclass
class Section:
    heading: str
    canonical: str | None  # the specification's name, or None for an extra heading
    level: int
    body: str


@dataclass
class DesignSystem:
    name: str = ""
    version: str = ""
    description: str = ""
    omitted: list[str] = field(default_factory=list)
    colors: dict[str, Any] = field(default_factory=dict)
    typography: dict[str, Any] = field(default_factory=dict)
    rounded: dict[str, Any] = field(default_factory=dict)
    spacing: dict[str, Any] = field(default_factory=dict)
    components: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)  # website, seo, ... kept as they are
    sections: list[Section] = field(default_factory=list)
    has_front_matter: bool = True
    invalid_groups: list[str] = field(default_factory=list)  # token groups that are not a mapping

    def group(self, name: str) -> dict[str, Any]:
        value = getattr(self, name, None)
        return value if isinstance(value, dict) else {}

    def lookup(self, path: str) -> Any:
        """The token at a dotted path such as `colors.primary` or `typography.body-md`; None when it does not exist."""
        node: Any = {name: self.group(name) for name in TOKEN_GROUPS}
        for part in path.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return None
        return node

    def resolve(self, value: Any, depth: int = 0) -> Any:
        """A value with its `{reference}` followed to a primitive (a chain of references is followed up to 10 steps)."""
        if isinstance(value, str) and depth < 10:
            match = REFERENCE.match(value.strip())
            if match:
                target = self.lookup(match.group(1))
                return self.resolve(target, depth + 1) if target is not None else None
        return value


def _heading_key(text: str) -> str:
    return re.sub(r"^\d+[.)]?\s*", "", text.strip()).lower()


def parse_sections(body: str) -> list[Section]:
    sections: list[Section] = []
    heading: tuple[str, int] | None = None
    lines: list[str] = []
    in_code = False

    def close() -> None:
        if heading is not None:
            key = _heading_key(heading[0])
            sections.append(
                Section(heading[0].strip(), SECTION_ALIASES.get(key), heading[1], "\n".join(lines).strip())
            )

    for line in body.splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
        match = None if in_code else re.match(r"^(#{2,3})\s+(.+?)\s*#*\s*$", line)
        if match and len(match.group(1)) == 2:
            close()
            heading, lines = (match.group(2), 2), []
        elif heading is not None:
            lines.append(line)
    close()
    return sections


def parse_design_md(text: str) -> DesignSystem:
    """Parses the text; raises `DesignMdError` only when the front matter is not valid YAML. Missing parts are the linter's business."""
    text = text.lstrip("﻿")
    match = FRONT_MATTER.match(text)
    system = DesignSystem()
    if not match:
        system.has_front_matter = False
        system.sections = parse_sections(text)
        return system
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as error:
        raise DesignMdError(
            f"The front matter between the --- lines is not valid YAML: {str(error)[:200]}"
        ) from error
    if not isinstance(data, dict):
        raise DesignMdError("The front matter must be a YAML mapping (name: ..., colors: ...)")
    system.name = str(data.pop("name", "") or "")
    system.version = str(data.pop("version", "") or "")
    system.description = str(data.pop("description", "") or "")
    omitted = data.pop("omitted", []) or []
    system.omitted = [
        str(item.get("section", "")) if isinstance(item, dict) else str(item)
        for item in (omitted if isinstance(omitted, list) else [omitted])
    ]
    for group in TOKEN_GROUPS:
        value = data.pop(group, None)
        if value is not None and not isinstance(value, dict):
            system.invalid_groups.append(group)
        setattr(system, group, value if isinstance(value, dict) else {})
    system.extra = data
    system.sections = parse_sections(text[match.end() :])
    return system

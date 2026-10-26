"""The generated screens as React: HTML to JSX (D-377).

The recipes are written by a generator, so their HTML is regular and a small converter is enough: attribute names become React's (class, for, viewBox, stroke-width ...),
inline `style="a:b"` becomes an object, form values become defaults (`defaultValue`, `defaultChecked`), void elements self-close, comments become JSX comments, and braces in
text are escaped. The page CSS stays one plain stylesheet with the same class names (`screen.css`), imported by `Screen.tsx`."""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser

VOID = {"input", "img", "br", "hr", "meta", "link", "source", "wbr"}
RENAME = {
    "class": "className",
    "for": "htmlFor",
    "tabindex": "tabIndex",
    "contenteditable": "contentEditable",
    "spellcheck": "spellCheck",
    "autocomplete": "autoComplete",
    "autofocus": "autoFocus",
    "maxlength": "maxLength",
    "colspan": "colSpan",
    "rowspan": "rowSpan",
    "readonly": "readOnly",
    "viewbox": "viewBox",
    "preserveaspectratio": "preserveAspectRatio",
    "xmlns:xlink": "xmlnsXlink",
    "gradientunits": "gradientUnits",
    "gradienttransform": "gradientTransform",
    "spreadmethod": "spreadMethod",
    "patternunits": "patternUnits",
    "clippathunits": "clipPathUnits",
    "stddeviation": "stdDeviation",
}
# The HTML parser lowercases every tag; these SVG elements are camel-case in JSX.
SVG_TAGS = {
    name.lower(): name
    for name in (
        "radialGradient",
        "linearGradient",
        "clipPath",
        "textPath",
        "foreignObject",
        "feGaussianBlur",
        "feOffset",
        "feMerge",
        "feMergeNode",
        "feColorMatrix",
        "feBlend",
        "feComposite",
        "feFlood",
        "feDropShadow",
    )
}
BOOLEAN = {"checked", "disabled", "selected", "readonly", "autofocus", "required", "hidden", "multiple"}


def camel(name: str) -> str:
    """`stroke-width` -> `strokeWidth`; custom properties (`--h`) and aria-/data- names stay as they are."""
    if name.startswith(("--", "aria-", "data-")):
        return name
    parts = name.split("-")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def style_object(text: str) -> str:
    items = []
    for declaration in re.split(r";(?![^()]*\))", text):
        if ":" not in declaration:
            continue
        key, _, value = declaration.partition(":")
        key = key.strip()
        name = key if key.startswith("--") else camel(key.lower())
        items.append(f"{json.dumps(name)}: {json.dumps(value.strip())}")
    body = ", ".join(items)
    return (
        "{{ " + body + " } as CSSProperties}" if '"--' in body else "{{ " + body + " }}"
    )  # custom properties are not in React's style type


class Converter(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.out: list[str] = []
        self.skip_text_for: list[str] = []
        self.textarea: list[str] | None = None
        self.textarea_attrs = ""

    def attribute(self, tag: str, name: str, value: str | None) -> str:
        key = RENAME.get(name, camel(name))
        if tag in ("input", "select", "textarea"):
            if name == "value":
                key = "defaultValue"
            elif name == "checked":
                key = "defaultChecked"
        if name == "style":
            return f"style={style_object(value or '')}"
        if name in BOOLEAN or value is None:
            return key if value in (None, "", name) else f"{key}={json.dumps(value)}"
        if name == "contenteditable":
            return f"contentEditable={{{str(value != 'false').lower()}}} suppressContentEditableWarning"
        if name in ("width", "height") and tag == "svg" and value.isdigit():
            return f"{key}={{{value}}}"
        if name in ("colspan", "rowspan") and value.isdigit():  # React types these as numbers
            return f"{key}={{{value}}}"
        return f"{key}={json.dumps(value)}"

    def tag_text(self, tag: str, attrs: list[tuple[str, str | None]], close: bool) -> str:
        parts = [SVG_TAGS.get(tag, tag)] + [self.attribute(tag, n, v) for n, v in attrs]
        return "<" + " ".join(parts) + (" />" if close else ">")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "textarea":
            self.textarea, self.textarea_attrs = [], " ".join(self.attribute(tag, n, v) for n, v in attrs)
            return
        self.out.append(self.tag_text(tag, attrs, tag in VOID))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.out.append(self.tag_text(tag, attrs, True))

    def handle_endtag(self, tag: str) -> None:
        if tag == "textarea" and self.textarea is not None:
            value = "".join(self.textarea).strip()
            attrs = (" " + self.textarea_attrs) if self.textarea_attrs else ""
            self.out.append(
                f"<textarea{attrs} defaultValue={json.dumps(value)} />" if value else f"<textarea{attrs} />"
            )
            self.textarea = None
            return
        if tag not in VOID:
            self.out.append(f"</{SVG_TAGS.get(tag, tag)}>")

    def handle_data(self, data: str) -> None:
        if self.textarea is not None:
            self.textarea.append(data)
            return
        self.out.append(data.replace("{", "{'{'}").replace("}", "{'}'}"))

    def handle_entityref(self, name: str) -> None:
        text = f"&{name};"
        (self.textarea if self.textarea is not None else self.out).append(text)

    def handle_charref(self, name: str) -> None:
        text = f"&#{name};"
        (self.textarea if self.textarea is not None else self.out).append(text)

    def handle_comment(self, data: str) -> None:
        self.out.append("{/* " + data.strip().replace("*/", "* /") + " */}")


def html_to_jsx(fragment: str) -> str:
    converter = Converter()
    converter.feed(fragment)
    converter.close()
    return "".join(converter.out)


def screen_component(body_html: str, screen_id: str) -> str:
    """`Screen.tsx` for one screen: the converted body in a fragment, with its stylesheet imported."""
    jsx = html_to_jsx(body_html.strip())
    types = 'import type { CSSProperties } from "react";\n' if "as CSSProperties" in jsx else ""
    return (
        f"// Screen recipe `{screen_id}` (React): the structure and class names of the HTML recipe, with the same sample content. Split it into components, replace the sample\n"
        "// data with your own and keep the class names or turn them into the project's utility classes. The colours come from CSS variables (see screen.css).\n"
        + types
        + 'import "./screen.css";\n\n'
        "export default function Screen() {\n  return (\n    <>\n"
        + "\n".join("      " + line for line in jsx.splitlines())
        + "\n    </>\n  );\n}\n"
    )

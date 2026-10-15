"""One micro-interaction: what the catalogue says, its CSS, a demo snippet and how a browser test can prove it works (D-382)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Effect:
    id: str  # catalogue id, also the class name: "mi-btn-fill-sweep"
    kind: str  # loader, toggle, button, input or card
    title: str
    summary: str
    css: str
    demo: str  # markup that uses the class; the class of the root element is the id
    action: str  # none (a running animation), hover, focus, check, press or invalid
    probe: (
        str  # CSS selector of the element whose property is read, relative to the demo root ("" = the root)
    )
    prop: str  # the computed property that must differ after the action (animation-name for a running animation)
    note: str  # one sentence of usage advice
    moods: tuple[str, ...] = ("clear", "modern")
    products: tuple[str, ...] = ("apps", "forms", "marketing")

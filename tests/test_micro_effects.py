"""D-382: the forty micro-interactions. Each one is proven in Edge from the same definitions that generate the stylesheet: its action (hover, focus, check, press or an invalid value)
changes the probed property, or its animation runs; under prefers-reduced-motion nothing animates. The catalogue knows all forty."""

from __future__ import annotations

import re
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parent.parent / "src" / "forge" / "skills" / "ui-design-quality"
CSS = SKILL / "recipes" / "motion-micro.css"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "dev"))
from micro_effects.defs_controls import CONTROLS  # noqa: E402
from micro_effects.defs_surfaces import SURFACES  # noqa: E402

EFFECTS = [*CONTROLS, *SURFACES]
PAGE = (
    '<!doctype html><meta charset="utf-8"><title>{id}</title><link rel="icon" href="data:,">'
    '<style>{css}</style><style>body{{margin:40px;font:16px system-ui;background:#fff;color:#111}}</style><main id="demo" style="width:320px">{demo}</main>'
)


def longest_seconds(value: str) -> float:
    """The longest duration in a computed transition-duration or animation-duration list such as '0.01ms, 0.2s'.
    The browser may print a tiny value in exponent form ('1e-05s' for 0.01ms), so the number pattern allows it."""
    pattern = r"(\d*\.?\d+(?:e-?\d+)?)(ms|s)"
    found = [float(n) * (0.001 if unit == "ms" else 1) for n, unit in re.findall(pattern, value)]
    return max(found, default=0.0)


@pytest.fixture(scope="module")
def browser() -> Iterator[object]:
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as playwright:
        try:
            launched = playwright.chromium.launch(channel="msedge", headless=True)
        except Exception as error:
            pytest.skip(str(error))
        yield launched
        launched.close()


def open_demo(browser: object, effect: object, reduced: bool = False) -> object:
    page = browser.new_page(
        viewport={"width": 480, "height": 400}, reduced_motion="reduce" if reduced else "no-preference"
    )  # type: ignore[attr-defined]
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.set_content(PAGE.format(id=effect.id, css=CSS.read_text(encoding="utf-8"), demo=effect.demo))  # type: ignore[attr-defined]
    page.errors = errors
    return page


def read(page: object, effect: object) -> str:
    selector = f"#demo {effect.probe}".strip() if effect.probe else "#demo > *"  # type: ignore[attr-defined]
    return str(
        page.evaluate(
            "([s, p]) => getComputedStyle(document.querySelector(s)).getPropertyValue(p)",
            [selector, effect.prop],
        )
    )  # type: ignore[attr-defined]


def act(page: object, effect: object) -> None:
    name, _, target = effect.action.partition(":")  # type: ignore[attr-defined]
    root = page.locator("#demo > *").first  # type: ignore[attr-defined]
    if name == "hover":
        root.hover()
    elif name == "focus":
        (page.locator(f"#demo {target}").first if target else root).focus()  # type: ignore[attr-defined]
    elif name == "check":
        if target:
            page.locator(f"#demo label[for={target.lstrip('#')}]").click()  # type: ignore[attr-defined]
        else:
            page.locator("#demo input").first.check(force=True)  # type: ignore[attr-defined]
    elif name == "press":
        root.hover()
        page.mouse.down()  # type: ignore[attr-defined]
    elif name == "invalid":
        root.fill("not-an-email")
        page.keyboard.press("Tab")  # type: ignore[attr-defined]


@pytest.mark.parametrize("effect", EFFECTS, ids=[e.id for e in EFFECTS])
def test_an_effect_does_what_it_says_and_stops_under_reduced_motion(browser: object, effect: object) -> None:
    page = open_demo(browser, effect)
    before = read(page, effect)
    if effect.action == "none":  # type: ignore[attr-defined]
        assert before not in ("none", ""), f"{effect.id} does not animate"  # type: ignore[attr-defined]
    else:
        act(page, effect)
        page.wait_for_timeout(120 if effect.action == "invalid" else 900)  # type: ignore[attr-defined]
        after = read(page, effect)
        assert after != before, f"{effect.id}: {effect.prop} stayed {before!r} after {effect.action}"  # type: ignore[attr-defined]
    assert page.errors == []  # type: ignore[attr-defined]
    page.close()  # type: ignore[attr-defined]
    calm = open_demo(browser, effect, reduced=True)
    probe = f"#demo {effect.probe}".strip() if effect.probe else "#demo > *"  # type: ignore[attr-defined]
    animation = str(calm.evaluate("(s) => getComputedStyle(document.querySelector(s)).animationName", probe))  # type: ignore[attr-defined]
    assert animation == "none", f"{effect.id} still animates under reduced motion"  # type: ignore[attr-defined]
    for target in ("#demo > *", probe):
        duration = str(
            calm.evaluate("(s) => getComputedStyle(document.querySelector(s)).transitionDuration", target)
        )  # type: ignore[attr-defined]
        assert longest_seconds(duration) < 0.05, (
            f"{effect.id}: transitions still run under reduced motion ({duration})"
        )  # type: ignore[attr-defined]
    calm.close()  # type: ignore[attr-defined]


def test_the_catalogue_knows_all_forty() -> None:
    from forge.parity.assets import build_catalogue

    ids = {a.id for a in build_catalogue(SKILL).assets if a.id.startswith("mi-")}
    assert ids == {e.id for e in EFFECTS} and len(ids) == 40
    assert len({e.id for e in CONTROLS}) == 24 and len({e.id for e in SURFACES}) == 16

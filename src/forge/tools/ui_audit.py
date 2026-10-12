"""Automatic look-and-feel audit of the page in the browser, run by browser_screenshot (D-245).

A model that only reads the DOM snapshot cannot see that the page is unstyled; a screenshot it glances at is
easy to wave through. So this audit measures the rendered page (computed styles, not source code) and returns
plain findings the model must fix. The first and worst finding is "the stylesheet framework produced nothing":
utility classes (Tailwind and similar) present in the markup whose effect is missing."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# Runs in the page. Returns {"findings": [...], "stats": {...}}; kept dependency-free and read-only.
AUDIT_SCRIPT = r"""
() => {
  const findings = [];
  const all = Array.from(document.body ? document.body.querySelectorAll('*') : []);
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const label = (el) => {
    const text = (el.innerText || el.alt || el.value || '').trim().replace(/\s+/g, ' ').slice(0, 30);
    return el.tagName.toLowerCase() + (text ? ' "' + text + '"' : '');
  };
  const sample = (list) => list.slice(0, 4).map(label).join(', ') + (list.length > 4 ? ', ...' : '');

  // 1. Utility classes with no effect: the CSS framework is not generating anything.
  let expected = 0, missing = 0;
  const expectations = [
    [/^(sm:|md:|lg:)?flex$/, (s) => s.display.includes('flex')],
    [/^(sm:|md:|lg:)?grid$/, (s) => s.display.includes('grid')],
    [/^p[xytblr]?-\d/, (s) => ['paddingTop', 'paddingBottom', 'paddingLeft', 'paddingRight']
      .some((k) => parseFloat(s[k]) > 0)],
    [/^rounded/, (s) => ['borderTopLeftRadius', 'borderTopRightRadius'].some((k) => parseFloat(s[k]) > 0)],
    [/^bg-(?!transparent|none)/, (s) => s.backgroundColor !== 'rgba(0, 0, 0, 0)' || s.backgroundImage !== 'none'],
    [/^text-(xs|sm|lg|xl|\dxl)$/, (s) => parseFloat(s.fontSize) !== 16],
    [/^gap-\d/, (s) => parseFloat(s.columnGap) > 0 || parseFloat(s.rowGap) > 0],
  ];
  for (const el of all) {
    const s = getComputedStyle(el);
    for (const token of (el.getAttribute('class') || '').split(/\s+/)) {
      for (const [pattern, holds] of expectations) {
        if (pattern.test(token)) { expected++; if (!holds(s)) missing++; }
      }
    }
  }
  const bodyStyle = getComputedStyle(document.body);
  const browserDefaultLook = bodyStyle.margin === '8px' && /times/i.test(bodyStyle.fontFamily);
  if (expected >= 5 && missing / expected > 0.5) {
    findings.push('BLOCKER: ' + missing + ' of ' + expected + ' utility classes in the markup (flex, p-4, ' +
      'rounded, bg-...) have no effect, so the CSS framework is not generating styles. Fix the setup first ' +
      '(Tailwind v4: @tailwindcss/vite plugin in vite.config and @import "tailwindcss" in the CSS file ' +
      'main imports; Tailwind v3: tailwind.config content globs, postcss config and the three @tailwind ' +
      'directives), then rebuild/restart and screenshot again. Do not tune the design until this is fixed.');
  } else if (browserDefaultLook) {
    findings.push('BLOCKER: the page still has the browser default look (8px body margin, Times font): no ' +
      'base stylesheet is applied. Check that the CSS file is imported and loads (browser_network).');
  }

  // 2. Horizontal scroll bar.
  const doc = document.documentElement;
  if (doc.scrollWidth > doc.clientWidth + 1) {
    findings.push('Horizontal overflow: the page is ' + doc.scrollWidth + 'px wide in a ' + doc.clientWidth +
      'px window, so it scrolls sideways. Constrain widths (max-w-*, w-full, flex-wrap, break-words).');
  }

  // 3. Browser-default links and buttons.
  const links = all.filter((el) => el.tagName === 'A' && visible(el) && getComputedStyle(el).color === 'rgb(0, 0, 238)');
  if (links.length) findings.push('Default blue underlined links (unstyled): ' + sample(links) + '. Style them.');
  const buttons = all.filter((el) => el.tagName === 'BUTTON' && visible(el)
    && getComputedStyle(el).backgroundColor === 'rgb(239, 239, 239)');
  if (buttons.length) findings.push('Default grey browser buttons (unstyled): ' + sample(buttons) + '.');

  // 4. Bordered or filled boxes whose text touches the edge (no padding).
  const cramped = all.filter((el) => {
    if (!visible(el) || !(el.innerText || '').trim()) return false;
    const s = getComputedStyle(el);
    const boxed = ['borderTopWidth', 'borderLeftWidth'].some((k) => parseFloat(s[k]) > 0)
      || s.backgroundColor !== 'rgba(0, 0, 0, 0)';
    const noPad = ['paddingLeft', 'paddingRight', 'paddingTop', 'paddingBottom'].every((k) => parseFloat(s[k]) === 0);
    const hasOwnText = Array.from(el.childNodes).some((n) => n.nodeType === 3 && n.textContent.trim());
    return boxed && noPad && hasOwnText && s.display !== 'inline';
  });
  if (cramped.length) findings.push('Text touching the edge of its box (no padding): ' + sample(cramped) + '.');

  // 5. Siblings jammed together with no gap (pills, buttons, cards in a row).
  let jammed = [];
  for (const el of all) {
    const next = el.nextElementSibling;
    if (!next || !visible(el) || !visible(next)) continue;
    const a = el.getBoundingClientRect(), b = next.getBoundingClientRect();
    const sameRow = Math.abs(a.top - b.top) < 4 && a.width > 20 && b.width > 20;
    const boxed = (n) => { const s = getComputedStyle(n);
      return parseFloat(s.borderTopWidth) > 0 || s.backgroundColor !== 'rgba(0, 0, 0, 0)'; };
    if (sameRow && b.left - a.right < 2 && b.left >= a.right - 1 && boxed(el) && boxed(next)) jammed.push(el);
  }
  if (jammed.length) findings.push('Boxed elements touching side by side (no gap): ' + sample(jammed) + '.');

  // 6. Contrast of text against its background (WCAG AA, 4.5:1; 3:1 for large text).
  // Any CSS colour (rgb, hex, oklch, color-mix, color(display-p3)...) to [r, g, b, alpha] in sRGB, via a 1x1 canvas.
  const swatch = document.createElement('canvas').getContext('2d', { willReadFrequently: true });
  swatch.canvas.width = swatch.canvas.height = 1;
  const parse = (c) => { swatch.clearRect(0, 0, 1, 1); swatch.fillStyle = '#000'; swatch.fillStyle = c; swatch.fillRect(0, 0, 1, 1);
    const d = swatch.getImageData(0, 0, 1, 1).data; return [d[0], d[1], d[2], d[3] / 255]; };
  const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const backdrop = (el) => { for (let n = el; n; n = n.parentElement) {
      const c = parse(getComputedStyle(n).backgroundColor); if (c.length < 4 || c[3] > 0.9) return c; }
    return [255, 255, 255, 1]; };
  const lowContrast = [];
  for (const el of all) {
    if (!visible(el) || !Array.from(el.childNodes).some((n) => n.nodeType === 3 && n.textContent.trim())) continue;
    const s = getComputedStyle(el);
    if (getComputedStyle(el).backgroundImage !== 'none' || (el.closest('[style*="gradient"]'))) continue;
    const fg = parse(s.color), bg = backdrop(el);
    const l1 = lum(fg) , l2 = lum(bg);
    const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
    const large = parseFloat(s.fontSize) >= 24 || (parseFloat(s.fontSize) >= 18.66 && parseInt(s.fontWeight) >= 700);
    if (ratio < (large ? 3 : 4.5)) lowContrast.push(el);
  }
  if (lowContrast.length) findings.push('Low text contrast (below WCAG AA): ' + sample(lowContrast) + '.');

  // 7. Tiny text, broken images, missing alt text.
  const tiny = all.filter((el) => visible(el) && parseFloat(getComputedStyle(el).fontSize) < 12
    && Array.from(el.childNodes).some((n) => n.nodeType === 3 && n.textContent.trim()));
  if (tiny.length) findings.push('Text smaller than 12px: ' + sample(tiny) + '.');
  const broken = Array.from(document.images).filter((i) => i.complete && i.naturalWidth === 0);
  if (broken.length) findings.push('Broken images: ' + broken.slice(0, 4).map((i) => i.getAttribute('src')).join(', ') + '.');
  const noAlt = Array.from(document.images).filter((i) => !i.hasAttribute('alt'));
  if (noAlt.length) findings.push(noAlt.length + ' image(s) without alt text (accessibility).');

  // 8. Empty-looking sections: big headings/labels with nothing under them (e.g. stats with no values).
  const emptyStats = all.filter((el) => visible(el) && el.children.length === 0 && !(el.innerText || '').trim()
    && el.getBoundingClientRect().height > 40 && !el.closest('svg, [aria-hidden="true"], details:not([open])')
    && !['img', 'svg', 'canvas', 'video', 'iframe', 'input', 'hr', 'br', 'textarea', 'select'].includes(el.tagName.toLowerCase())
    && getComputedStyle(el).backgroundImage === 'none' && getComputedStyle(el).backgroundColor === 'rgba(0, 0, 0, 0)');
  if (emptyStats.length > 2) findings.push(emptyStats.length + ' tall empty elements: a value, chart or image may be missing.');

  // 9. A page with only one font size has no hierarchy.
  const sizes = new Set(all.filter(visible).map((el) => Math.round(parseFloat(getComputedStyle(el).fontSize))));
  if (sizes.size < 3) findings.push('Almost no type hierarchy (' + sizes.size + ' font size(s)): use a clear scale for headings, body and captions.');

  // 10. Design-system discipline: too many fonts, sizes, colours or radii means there is no system.
  const textEls = all.filter((el) => visible(el) && Array.from(el.childNodes).some((n) => n.nodeType === 3 && n.textContent.trim()));
  const families = new Set(textEls.map((el) => getComputedStyle(el).fontFamily.split(',')[0].replace(/["']/g, '').trim().toLowerCase())
    .filter((f) => !/mono|courier|consolas|menlo/.test(f)));
  if (families.size > 3) findings.push(families.size + ' different font families in use (' + Array.from(families).join(', ') + '): use at most two.');
  const textSizes = new Set(textEls.map((el) => Math.round(parseFloat(getComputedStyle(el).fontSize))));
  if (textSizes.size > 10) findings.push(textSizes.size + ' different text sizes: use one scale (12/14/16/18/20/24/30/36/48/60).');
  const textColours = new Set(textEls.map((el) => getComputedStyle(el).color));
  if (textColours.size > 9) findings.push(textColours.size + ' different text colours: reduce to a few neutrals plus the accent.');
  const radii = new Set(all.filter(visible).map((el) => getComputedStyle(el).borderTopLeftRadius).filter((r) => r !== '0px' && !r.includes('%') && parseFloat(r) < 999));
  if (radii.size > 6) findings.push(radii.size + ' different corner radii: pick two or three and reuse them.');
  const heading = document.querySelector('h1');
  if (!heading) findings.push('No h1 on the page: every page needs one clear main heading.');
  else if (parseFloat(getComputedStyle(heading).fontSize) < 28) findings.push('The h1 is only ' + Math.round(parseFloat(getComputedStyle(heading).fontSize)) + 'px: the main heading should dominate (36px or more).');
  const paragraphs = all.filter((el) => el.tagName === 'P' && visible(el) && el.getBoundingClientRect().width > 0);
  const wide = paragraphs.filter((el) => { const w = el.getBoundingClientRect().width, f = parseFloat(getComputedStyle(el).fontSize); return (el.innerText || '').length > 120 && w / f > 52; });
  if (wide.length) findings.push('Text lines are too long (more than about 80 characters): ' + sample(wide) + '. Limit with max-w-prose or max-w-2xl.');

  // 12. Things that look broken in screenshots: see-through sticky bars, invisible form fields, clipped text.
  const ratioOf = (a, b) => { const l1 = lum(a), l2 = lum(b); return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05); };
  const over = (fg, bg) => { const a = fg.length > 3 ? fg[3] : 1; return [0, 1, 2].map((i) => fg[i] * a + bg[i] * (1 - a)); };
  const seeThrough = all.filter((el) => {
    const s = getComputedStyle(el), box = el.getBoundingClientRect();
    if (!visible(el) || !['sticky', 'fixed'].includes(s.position) || box.width < window.innerWidth * 0.5 || box.height > 140 || box.top > 1) return false;
    const bg = parse(s.backgroundColor);
    return (bg.length > 3 ? bg[3] : 1) < 0.6 && !/blur/.test(s.backdropFilter || '') && s.backgroundImage === 'none';
  });
  if (seeThrough.length) findings.push('The sticky/fixed bar ' + sample(seeThrough) + ' has a see-through background: page text scrolls underneath and collides with it. Give it a solid background or backdrop-blur with a tinted fill and a bottom border.');
  const faintFields = all.filter((el) => {
    if (!['INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName) || !visible(el) || ['checkbox', 'radio', 'hidden', 'submit', 'button', 'range', 'color', 'file'].includes(el.type)) return false;
    // The visible outline may be on the input itself (border or fill), on a sibling fieldset (MUI), or on a wrapper
    // that hugs the input (border only: a page or card background is not a field outline).
    const edgeOf = (box) => {
      const style = getComputedStyle(box), around = backdrop(box.parentElement || box);
      return parseFloat(style.borderTopWidth) > 0 ? ratioOf(over(parse(style.borderTopColor), around), around) : 1;
    };
    const own = getComputedStyle(el), ownAround = backdrop(el.parentElement || el);
    let best = Math.max(edgeOf(el), ratioOf(over(parse(own.backgroundColor), ownAround), ownAround));
    const fieldBox = el.getBoundingClientRect();
    const outline = el.parentElement && el.parentElement.querySelector(':scope > fieldset');
    if (outline) best = Math.max(best, edgeOf(outline));
    for (let up = el.parentElement, i = 0; up && i < 3; up = up.parentElement, i++) {
      const box = up.getBoundingClientRect();
      if (box.height <= fieldBox.height + 16 && box.width <= fieldBox.width + 40) best = Math.max(best, edgeOf(up));
    }
    return best < 1.4;
  });
  if (faintFields.length) findings.push(faintFields.length + ' form field(s) are nearly invisible (border and fill barely differ from the background): ' + sample(faintFields) + '. Use a clear 1px border (about ink-300 on light, white/20% on dark) and a visible focus ring.');
  const clippedText = all.filter((el) => visible(el) && /(hidden|clip)/.test(getComputedStyle(el).overflowX) && el.clientWidth > 8 && el.scrollWidth > el.clientWidth + 2
    && (el.innerText || '').trim() && !getComputedStyle(el).textOverflow.includes('ellipsis') && !el.closest('.marquee, svg'));
  if (clippedText.length) findings.push('Text is cut off by its container (overflow hidden): ' + sample(clippedText) + '. Let it wrap (min-w-0, break-words) or enlarge the box.');

  // 11. Taste checks (distilled from common "generic AI page" tells).
  const firstAction = all.find((el) => (el.tagName === 'A' || el.tagName === 'BUTTON') && visible(el) && !el.closest('header, nav')
    && getComputedStyle(el).backgroundColor !== 'rgba(0, 0, 0, 0)');
  if (firstAction && firstAction.getBoundingClientRect().top + window.scrollY > window.innerHeight) {
    findings.push('The first primary action ' + label(firstAction) + ' is below the fold at ' + window.innerWidth + 'x' +
      window.innerHeight + ': the hero must show the headline and the main action without scrolling.');
  }
  if (heading && window.innerWidth >= 1024) {
    const lineHeight = parseFloat(getComputedStyle(heading).lineHeight) || parseFloat(getComputedStyle(heading).fontSize) * 1.2;
    const lines = Math.round(heading.getBoundingClientRect().height / lineHeight);
    if (lines > 3) findings.push('The h1 wraps over ' + lines + ' lines at desktop width: shorten the headline or widen its box.');
  }
  const bodyText = document.body.innerText || '';
  const emDashes = (bodyText.match(/—/g) || []).length;
  if (emDashes >= 2) findings.push(emDashes + ' em dashes in the copy (a common machine-writing tell): use commas, colons or full stops.');
  const placeholder = bodyText.match(/lorem ipsum|john doe|jane doe|\bacme\b|your (company|name|text) here|sample text|coming soon/i);
  if (placeholder) findings.push('Placeholder content on the page ("' + placeholder[0] + '"): write real copy.');

  return { findings, stats: { elements: all.length, utilityClasses: expected, ineffective: missing, viewport: window.innerWidth + 'x' + window.innerHeight } };
}
"""

DESIGN_REMINDER = (
    "Now look at the image with view_image and judge it as a designer would: clear visual hierarchy, one accent "
    "colour, consistent spacing scale, aligned grid, readable type, real content (no empty cards), a hero or first "
    "screen that makes the purpose obvious, visible hover/focus/empty/error states. If it would not pass in a "
    "portfolio review, improve it and screenshot again. The ui-design-quality skill has the checklist."
)


async def audit_page(page: Any, root: Path | None = None) -> str:
    """The audit as text for the model: numbered findings, or a clean line; never raises."""
    try:
        result = await page.evaluate(AUDIT_SCRIPT)
    except (
        Exception
    ) as error:  # a page that blocks scripts or is mid-navigation must not break the screenshot
        return f"Style audit could not run: {str(error).splitlines()[0]}"
    findings: list[str] = list(result.get("findings", []))
    if root is not None:
        findings.extend(source_taste_problems(root))
    stats = result.get("stats", {})
    header = f"Style audit ({stats.get('viewport', '?')}, {stats.get('elements', 0)} elements)"
    if not findings:
        return f"{header}: no measurable problems."
    numbered = "\n".join(f"{index}. {finding}" for index, finding in enumerate(findings, start=1))
    return f"{header}: {len(findings)} problem(s) to fix before this counts as done:\n{numbered}"


SKIPPED_FOLDERS = {"node_modules", "dist", "build", ".git", ".venv", "venv", "__pycache__"}


def _project_files(root: Path, pattern: str) -> list[Path]:
    return [p for p in root.rglob(pattern) if not SKIPPED_FOLDERS.intersection(p.relative_to(root).parts)]


def tailwind_setup_problem(root: Path) -> str | None:
    """Reads the project files (no browser) and says what is wrong with a Tailwind setup, or None when it is
    fine or there is no Tailwind. The usual cause of an unstyled page is v3 syntax with v4 installed or a
    missing plugin/import, which a screenshot alone does not tell the model."""
    for package_json in _project_files(root, "package.json"):
        try:
            data = json.loads(package_json.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        if "tailwindcss" not in deps:
            continue
        folder = package_json.parent
        match = re.search(r"\d+", str(deps["tailwindcss"]))
        major = int(match.group()) if match else 4
        styles = " ".join(
            p.read_text(encoding="utf-8", errors="replace")
            for suffix in ("css", "scss")
            for p in _project_files(folder, f"*.{suffix}")
        )
        where = folder.relative_to(root).as_posix() or "."
        if major >= 4:
            if "@tailwindcss/vite" not in deps and "@tailwindcss/postcss" not in deps:
                return (
                    f"Tailwind v4 in {where}/package.json has no @tailwindcss/vite (or @tailwindcss/postcss): "
                    "npm i -D @tailwindcss/vite and add tailwindcss() to the plugins in vite.config."
                )
            if "@tailwindcss/vite" in deps and not any(
                "tailwindcss" in p.read_text(encoding="utf-8", errors="replace")
                for p in _project_files(folder, "vite.config.*")
            ):
                return f"vite.config in {where} does not use the @tailwindcss/vite plugin: import it and add it to plugins."
            if not re.search(r"""@import\s+["']tailwindcss""", styles):
                return (
                    f'Tailwind v4 in {where}: no CSS file contains @import "tailwindcss"; add it as the first '
                    "line of the CSS file that main.tsx imports (the v3 @tailwind directives do nothing in v4)."
                )
        else:
            if not _project_files(folder, "tailwind.config.*"):
                return f"Tailwind v3 in {where} has no tailwind.config.js with content globs."
            if "@tailwind base" not in styles and "@tailwind utilities" not in styles:
                return f"Tailwind v3 in {where}: no CSS file has the @tailwind base/components/utilities directives."
    return None


SOURCE_SUFFIXES = {".tsx", ".jsx", ".ts", ".js", ".vue", ".svelte", ".html", ".css"}
SOURCE_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\b(?:window\.)?alert\s*\("),
        "alert() is used: show a designed toast or inline message instead",
    ),
    (
        re.compile(r"addEventListener\(\s*[\"']scroll"),
        "a scroll listener: use IntersectionObserver or CSS (scroll handlers cause jank)",
    ),
    (
        re.compile(r"transition:\s*all\b"),
        "`transition: all`: animate named properties (transform, opacity, colour)",
    ),
    (re.compile(r"\bh-screen\b"), "`h-screen`: use min-h-dvh so mobile browser bars do not cut the layout"),
    (
        re.compile(r"lorem ipsum|john doe|jane doe", re.IGNORECASE),
        "placeholder text in the source: write real copy",
    ),
    (re.compile(r"<img(?![^>]*\balt=)[^>]*>"), "an <img> without alt text"),
]


def source_taste_problems(root: Path) -> list[str]:
    """Static scan of the project's own UI source for patterns that make a page feel unfinished (no browser)."""
    counts: dict[str, list[str]] = {}
    for path in root.rglob("*"):
        if path.suffix not in SOURCE_SUFFIXES or SKIPPED_FOLDERS.intersection(path.relative_to(root).parts):
            continue
        if "test" in path.name.lower() or path.stat().st_size > 400_000:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for pattern, message in SOURCE_RULES:
            if pattern.search(text):
                counts.setdefault(message, []).append(path.relative_to(root).as_posix())
    return [
        f"Source: {message} ({', '.join(files[:3])}{', ...' if len(files) > 3 else ''})."
        for message, files in counts.items()
    ]

"""Overlap check for drawn diagrams (D-484): labels hidden behind a shape or on top of each other, and drawing that runs outside its <svg>.

The page audit in ui_audit.py reads HTML boxes; a diagram is one <svg> whose text and shapes it never compares, so the models' own screenshots
passed diagrams with a label half hidden behind a box and a legend cut off at the bottom (the diagram-design live runs). Here every text of a
drawing of a useful size is measured against the others, and a label counts as hidden only when a filled shape is the top element at several points of it
(a label that merely straddles a box edge, like the tabs and ring numbers of well-made diagrams, is legible and is left alone)."""

from __future__ import annotations

from typing import Any

SVG_SCRIPT = r"""
() => {
  const findings = [];
  const area = (r) => Math.max(0, r.width) * Math.max(0, r.height);
  const overlap = (a, b) => area({
    width: Math.min(a.right, b.right) - Math.max(a.left, b.left),
    height: Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top),
  });
  const shown = (el) => { const s = getComputedStyle(el); return s.display !== 'none' && s.visibility !== 'hidden' && parseFloat(s.opacity) > 0.05; };
  const say = (list) => list.slice(0, 3).map((t) => '"' + t.slice(0, 28) + '"').join(', ') + (list.length > 3 ? ' and ' + (list.length - 3) + ' more' : '');
  for (const svg of document.querySelectorAll('svg')) {
    const frame = svg.getBoundingClientRect();
    if (frame.width < 160 || frame.height < 100 || !shown(svg)) continue;
    const words = (el) => (el.textContent || '').replace(/\s+/g, ' ').trim();
    const texts = [...svg.querySelectorAll('text')].filter((t) => words(t) && shown(t) && !t.closest('defs, symbol, [aria-hidden="true"]'))
      .map((t) => ({ label: words(t), box: t.getBoundingClientRect() })).filter((t) => t.box.width > 2 && t.box.height > 2);
    if (texts.length < 2) continue;

    const outside = texts.filter((t) => t.box.left < frame.left - 2 || t.box.right > frame.right + 2 || t.box.top < frame.top - 2 || t.box.bottom > frame.bottom + 2);
    if (outside.length) findings.push('Drawing text runs outside its <svg> and is cut off: ' + say(outside.map((t) => t.label)) + '. Enlarge the viewBox (and height) or move it inside.');

    // A label is hidden when a filled shape drawn after it is the top element at several points of its box (elementFromPoint ignores unfilled shapes).
    const hidden = texts.filter((t) => {
      let covered = 0;
      for (const fx of [0.2, 0.5, 0.8]) for (const fy of [0.3, 0.7]) {
        const x = t.box.left + t.box.width * fx, y = t.box.top + t.box.height * fy;
        if (x < 0 || y < 0 || x > window.innerWidth || y > window.innerHeight) continue;
        const top = document.elementFromPoint(x, y);
        if (top && svg.contains(top) && /^(rect|polygon|ellipse|circle|path)$/i.test(top.tagName)) covered++;
      }
      return covered >= 2;
    });
    if (hidden.length) findings.push('Drawing labels are hidden behind a shape: ' + say(hidden.map((t) => t.label)) + '. Draw the label after the shape or move it clear.');

    const stacked = [];
    for (let i = 0; i < texts.length; i++) for (let j = i + 1; j < texts.length; j++) {
      const shared = overlap(texts[i].box, texts[j].box) / Math.min(area(texts[i].box), area(texts[j].box));
      if (shared > 0.4) stacked.push(texts[i].label + ' / ' + texts[j].label);
    }
    if (stacked.length) findings.push('Drawing labels overlap each other: ' + say(stacked) + '. Space them out.');
  }
  return findings;
}
"""


async def svg_findings(page: Any) -> list[str]:
    """Findings for the drawings on the page; empty when there is none or the page cannot be evaluated."""
    try:
        found = await page.evaluate(SVG_SCRIPT)
    except Exception:  # a page mid-navigation must not break the screenshot
        return []
    return [str(item) for item in found]

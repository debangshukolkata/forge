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

from forge.tools.token_lint import token_lint_problems

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
  const toHex = (c) => '#' + c.slice(0, 3).map((v) => Math.round(v).toString(16).padStart(2, '0')).join('');
  const contrastOf = (a, b) => (Math.max(lum(a), lum(b)) + 0.05) / (Math.min(lum(a), lum(b)) + 0.05);
  // The nearest text colour that passes: the same colour moved toward black or white in small steps.
  const fixedText = (fg, bg, need) => { const to = lum(bg) > 0.5 ? [0, 0, 0] : [255, 255, 255];
    for (let t = 0.05; t <= 1.0001; t += 0.05) {
      const c = fg.slice(0, 3).map((v, i) => v + (to[i] - v) * t); if (contrastOf(c, bg) >= need) return c; }
    return to; };
  const lowContrast = [], contrastFixes = [];
  for (const el of all) {
    if (!visible(el) || !Array.from(el.childNodes).some((n) => n.nodeType === 3 && n.textContent.trim())) continue;
    const s = getComputedStyle(el);
    if (getComputedStyle(el).backgroundImage !== 'none' || (el.closest('[style*="gradient"]'))) continue;
    const fg = parse(s.color), bg = backdrop(el);
    const l1 = lum(fg) , l2 = lum(bg);
    const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
    const large = parseFloat(s.fontSize) >= 24 || (parseFloat(s.fontSize) >= 18.66 && parseInt(s.fontWeight) >= 700);
    if (ratio < (large ? 3 : 4.5)) {
      lowContrast.push(el);
      if (contrastFixes.length < 3) contrastFixes.push(label(el) + ' is ' + toHex(fg) + ' on ' + toHex(bg) + ' (' +
        ratio.toFixed(1) + ':1); use ' + toHex(fixedText(fg, bg, large ? 3 : 4.5)));
    }
  }
  if (lowContrast.length) findings.push('Low text contrast (below WCAG AA): ' + sample(lowContrast) +
    '. Fix the token, not the single element. Nearest passing colours: ' + contrastFixes.join('; ') + '.');

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

  // 12. Design studio rules (D-351): banned looks and missing interaction states.
  const parseRgb = (c) => { const m = (c || '').match(/rgba?\(([^)]+)\)/); if (!m) return null;
    const p = m[1].split(/[ ,\/]+/).filter(Boolean).map(parseFloat); return p.length >= 3 ? { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 } : null; };
  const hsl = ({ r, g, b }) => { r /= 255; g /= 255; b /= 255; const max = Math.max(r, g, b), min = Math.min(r, g, b), l = (max + min) / 2;
    if (max === min) return { h: 0, s: 0, l }; const d = max - min, s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    const h = max === r ? ((g - b) / d + (g < b ? 6 : 0)) : max === g ? (b - r) / d + 2 : (r - g) / d + 4; return { h: h * 60, s, l }; };
  const between = (h, lo, hi) => h >= lo && h <= hi;
  const badGradients = [];
  for (const el of all) {
    if (!visible(el)) continue;
    const image = getComputedStyle(el).backgroundImage;
    if (!image || !image.includes('gradient')) continue;
    const stops = (image.match(/rgba?\([^)]+\)/g) || []).map(parseRgb).filter((c) => c && c.a > 0.3).map(hsl).filter((c) => c.s > 0.4 && c.l > 0.15 && c.l < 0.9);
    if (stops.length < 2) continue;
    const hues = stops.map((c) => c.h);
    const purpleBlue = hues.some((h) => between(h, 255, 300)) && hues.some((h) => between(h, 190, 265) && !hues.every((x) => between(x, 255, 300)));
    const pinkCyan = hues.some((h) => between(h, 300, 350)) && hues.some((h) => between(h, 165, 205));
    const rainbow = new Set(hues.map((h) => Math.floor(h / 60))).size >= 4;
    if (purpleBlue || pinkCyan || rainbow) badGradients.push(el);
  }
  if (badGradients.length) findings.push('A purple-blue, pink-cyan or rainbow gradient is used (' + sample(badGradients) + '): the most common generic-AI look. Use a flat colour from DESIGN.md, or a gradient of two close tones of the one accent.');
  const greyBoxes = all.filter((el) => { if (!visible(el) || !['DIV', 'SPAN', 'FIGURE', 'SECTION'].includes(el.tagName)) return false;
    const r = el.getBoundingClientRect(); if (r.width < 80 || r.height < 80 || el.children.length > 0 || (el.innerText || '').trim()) return false;
    const c = parseRgb(getComputedStyle(el).backgroundColor); if (!c || c.a < 0.9) return false; const v = hsl(c);
    return v.s < 0.15 && v.l > 0.55 && v.l < 0.93 && getComputedStyle(el).backgroundImage === 'none'; });
  if (greyBoxes.length >= 1) findings.push(greyBoxes.length + ' empty grey box(es) stand in for an image (' + sample(greyBoxes) + '): use a real picture, a drawn SVG or an honest empty state, never a placeholder block.');
  const accentArea = new Map(); const viewportArea = window.innerWidth * window.innerHeight;
  for (const el of all) { if (!visible(el)) continue; const c = parseRgb(getComputedStyle(el).backgroundColor); if (!c || c.a < 0.9) continue; const v = hsl(c);
    if (v.s > 0.45 && v.l > 0.25 && v.l < 0.8) { const r = el.getBoundingClientRect(); const area = Math.max(0, Math.min(r.bottom, window.innerHeight) - Math.max(r.top, 0)) * Math.min(r.width, window.innerWidth);
      const bucket = Math.round(v.h / 40) % 9; accentArea.set(bucket, (accentArea.get(bucket) || 0) + area); } }
  const accents = [...accentArea.values()].filter((a) => a / viewportArea > 0.012).length;
  if (accents >= 4) findings.push(accents + ' different saturated colour families fill parts of this screen: keep one accent (and one signal colour for status) so the page has a single voice.');
  const rules = []; for (const sheet of Array.from(document.styleSheets)) { try { for (const rule of Array.from(sheet.cssRules || [])) rules.push(rule.cssText || ''); } catch (e) { /* a cross-origin stylesheet */ } }
  const cssText = rules.join('\n');
  const interactive = all.filter((el) => visible(el) && (el.tagName === 'BUTTON' || el.tagName === 'A' && el.hasAttribute('href') || el.tagName === 'INPUT' || el.tagName === 'SELECT' || el.tagName === 'TEXTAREA'));
  if (cssText && interactive.length >= 2) {
    if (!/:hover/.test(cssText)) findings.push('No hover style exists for the ' + interactive.length + ' buttons, links and fields: add a visible hover state (colour or lift).');
    if (!/:focus-visible|:focus\b|:focus-within/.test(cssText)) findings.push('No focus style exists for the buttons, links and fields: add a visible :focus-visible ring (keyboard users cannot see where they are).');
    if (all.some((el) => el.matches(':disabled')) && !/:disabled|\[disabled\]|aria-disabled/.test(cssText)) findings.push('Disabled controls look the same as enabled ones: style :disabled (lower contrast, no pointer).');
  }
  const genericFamily = /^(system-ui|-apple-system|blinkmacsystemfont|segoe ui|segoe ui variable|arial|helvetica|helvetica neue|times new roman|times|verdana|tahoma|trebuchet ms|sans-serif|serif|monospace|ui-sans-serif|ui-serif|ui-monospace|sf pro|sf pro text|roboto|noto sans|noto serif|georgia)$/i;
  const loadedFamilies = new Set([...document.fonts].filter((f) => f.status === 'loaded').map((f) => f.family.replace(/["']/g, '').toLowerCase()));
  let designedChars = 0, allChars = 0; const usedFamilies = new Map();
  for (const el of all) { if (!visible(el)) continue;
    const own = [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent.trim()).join('').length; if (!own) continue;
    const name = getComputedStyle(el).fontFamily.split(',')[0].replace(/["']/g, '').trim().toLowerCase();
    allChars += own; usedFamilies.set(name, (usedFamilies.get(name) || 0) + own);
    if (loadedFamilies.has(name) || !genericFamily.test(name)) designedChars += own; }
  if (allChars > 200 && designedChars / allChars < 0.1) {
    const names = [...usedFamilies.entries()].sort((a, b) => b[1] - a[1]).slice(0, 2).map((x) => x[0]).join(', ');
    findings.push('All the text is set in the system font stack (' + names + '): the page has no designed typography, which is the first thing that makes a page look machine-made. Choose a display font and a text font that suit the product, its mood and its language (find_font, or find_asset type font-pairing; fetch_font saves the files), load them with @font-face, and use them from the DESIGN.md typography tokens.');
  }
  const hasPicture = all.some((el) => visible(el) && ((el.tagName === 'IMG' && el.naturalWidth >= 200) || el.tagName === 'VIDEO' || el.tagName === 'CANVAS' || el.tagName === 'PICTURE'
    || (el.tagName === 'svg' && el.getBoundingClientRect().width >= 150 && el.getBoundingClientRect().height >= 120 && el.querySelectorAll('path, circle, rect, polygon, ellipse, line').length >= 4)
    || /url\(/.test(getComputedStyle(el).backgroundImage)));
  if (!hasPicture && all.length >= 30 && (document.body.innerText || '').length > 600) {
    findings.push('The page has no imagery at all: no photograph, illustration, drawn SVG scene or video, only text and boxes. Designed pages carry visual content that belongs to the product (findimage for a licensed photograph, generate_image, or draw an SVG illustration), at least in the hero.');
  }
  const small = all.filter((el) => visible(el) && window.innerWidth >= 768 && [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim().length > 24) && parseFloat(getComputedStyle(el).fontSize) < 13);
  if (small.length >= 3) findings.push(small.length + ' blocks of running text are under 13px at desktop width (' + sample(small) + '): body text should be 14px or larger.');

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
        findings.extend(token_lint_problems(root))
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
    (
        re.compile(
            r"(?:from|via|to)-(?:purple|violet|indigo|fuchsia)-\d+[^\"'`]*\bto-(?:blue|cyan|sky|pink|teal)-\d+"
        ),
        "a purple-to-blue (or pink, cyan) Tailwind gradient: the most common generic-AI look; use a flat colour from DESIGN.md",
    ),
]
# Checks of the whole file rather than one pattern: a form needs an error state and a sending state (the 8-state model, D-351).
FORM = re.compile(r"<form\b|onSubmit|handleSubmit")
STATE_CHECKS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"aria-invalid|role=[\"']alert|\berror\b", re.IGNORECASE),
        "a form with no error state (aria-invalid, an error message with role=alert): say what went wrong and what to do",
    ),
    (
        re.compile(r"disabled|loading|pending|submitting|isLoading|aria-busy", re.IGNORECASE),
        "a form with no sending state (disabled or loading while the request runs)",
    ),
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
        if path.suffix in (".tsx", ".jsx", ".vue", ".svelte", ".html") and FORM.search(text):
            for satisfied, message in STATE_CHECKS:
                if not satisfied.search(text):
                    counts.setdefault(message, []).append(path.relative_to(root).as_posix())
    return [
        f"Source: {message} ({', '.join(files[:3])}{', ...' if len(files) > 3 else ''})."
        for message, files in counts.items()
    ]

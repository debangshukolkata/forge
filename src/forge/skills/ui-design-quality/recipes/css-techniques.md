# Modern CSS techniques (use these instead of hacks or libraries). Check caniuse/MDN if a target browser is old.

Browser baseline on a managed Windows laptop: current Edge/Chrome (Chromium) supports everything below. Firefox/Safari
gaps are noted. Always give a graceful fallback (the page must look right without the effect).

## Layout
```css
/* fluid type and spacing without media queries */
h1 { font-size: clamp(2.25rem, 1.2rem + 4vw, 4.5rem); line-height: 1.05; text-wrap: balance; }
p  { text-wrap: pretty; max-width: 65ch; }
section { padding-block: clamp(4rem, 8vw, 7rem); }

/* auto-fit grid: as many 16rem columns as fit, no breakpoints */
.grid-auto { display: grid; gap: 1.5rem; grid-template-columns: repeat(auto-fit, minmax(min(16rem, 100%), 1fr)); }

/* container queries: a component adapts to the space it is given, not the window */
.card-wrap { container-type: inline-size; }
@container (min-width: 28rem) { .card { display: grid; grid-template-columns: 8rem 1fr; gap: 1rem; } }

/* subgrid: align inner rows across sibling cards (titles, text, buttons line up) */
.cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem; }
.cards > .card { display: grid; grid-row: span 3; grid-template-rows: subgrid; }

/* full height that respects mobile browser bars */
.hero { min-height: 100dvh; }

/* sticky sidebar / header */
.sticky-col { position: sticky; top: 6rem; align-self: start; }

/* aspect ratio and object fit for any image/video/map */
.media { aspect-ratio: 4 / 3; object-fit: cover; width: 100%; border-radius: 1rem; }
```

## Selectors that remove JavaScript
```css
.field:has(input:user-invalid) { --ring: var(--color-brand-600); }          /* style a parent by its child's state */
form:has(:invalid) button[type="submit"] { opacity: .6; }                   /* disable-look until valid */
.nav a:is(:hover, :focus-visible) { color: var(--color-brand-600); }        /* group selectors */
li:not(:last-child) { border-bottom: 1px solid var(--color-ink-200); }
input:user-invalid { border-color: var(--color-brand-600); }                /* only after the user interacted */
details[open] summary svg { transform: rotate(180deg); }                    /* accordion state */
```

## Colour
```css
:root { --accent: oklch(55% 0.2 25); }                                       /* perceptual colour: easy tints and shades */
.btn:hover { background: color-mix(in oklab, var(--accent) 88%, black); }    /* derive hover/tint without extra tokens */
.tint { background: color-mix(in oklab, var(--accent) 10%, white); }
.gradient { background: linear-gradient(135deg in oklch, oklch(70% .2 25), oklch(60% .22 330)); }  /* smooth, no grey mud */
:root { color-scheme: light dark; }                                           /* native form controls follow the theme */
@media (prefers-color-scheme: dark) { :root { --bg: #0b0d12; --fg: #e5e7eb; } }
/* manual toggle: set data-theme on <html> and define the same tokens under [data-theme="dark"] */
```

## Depth, surfaces, effects
```css
.shadow-layered { box-shadow: 0 1px 1px rgb(0 0 0 / .05), 0 4px 8px rgb(0 0 0 / .05), 0 16px 32px rgb(0 0 0 / .08); }
.ring-soft { box-shadow: 0 0 0 1px rgb(0 0 0 / .06), 0 8px 24px -8px rgb(0 0 0 / .18); }
.mask-fade { mask-image: linear-gradient(to bottom, #000 70%, transparent); }    /* fade an image/list edge */
.noise::after { /* see .grain in motion.css */ }
.text-gradient { background: linear-gradient(90deg, #6366f1, #ec4899); -webkit-background-clip: text; color: transparent; }
.blur-bg { backdrop-filter: blur(14px) saturate(160%); }                      /* needs a translucent background */
.dots { background-image: radial-gradient(rgb(0 0 0 / .12) 1px, transparent 1px); background-size: 20px 20px; }
.grid-lines { background-image: linear-gradient(rgb(0 0 0 / .05) 1px, transparent 1px), linear-gradient(90deg, rgb(0 0 0 / .05) 1px, transparent 1px); background-size: 40px 40px; }
.hero-bg { background: radial-gradient(60rem 30rem at 80% -10%, color-mix(in oklab, var(--accent) 22%, transparent), transparent), var(--bg); }
```

## Animation techniques
- Only `transform`, `opacity` (and filter for one-off effects) are cheap. Never animate width/height/top/left; for height
  use `grid-template-rows: 0fr -> 1fr` or `<details>`.
- Scroll-driven (no JS): `animation-timeline: scroll()` for a reading-progress bar; `animation-timeline: view()` with
  `animation-range: entry 0% cover 30%` for reveals (see `.reveal-scroll`). Wrap in `@supports (animation-timeline: view())`.
```css
.progress { position: fixed; inset: 0 0 auto 0; height: 3px; background: var(--accent); transform-origin: 0 50%; animation: grow linear; animation-timeline: scroll(root); }
@keyframes grow { from { transform: scaleX(0); } to { transform: scaleX(1); } }
```
- Entry animation for elements that appear (dialogs, popovers, toasts) with `@starting-style`:
```css
.toast { transition: opacity .3s, transform .3s; }
@starting-style { .toast { opacity: 0; transform: translateY(8px); } }
```
- Animate to/from `display: none` and `height: auto`: `transition-behavior: allow-discrete` and `interpolate-size: allow-keywords` (Chromium).
- Custom property animation with `@property` (rotating gradient border, number counters via `counter-reset` + `content: counter()`).
- View Transitions: `document.startViewTransition(() => setState(...))` gives a cross-fade or shared-element morph between
  states; give shared elements the same `view-transition-name`. Multi-page: `@view-transition { navigation: auto; }`.
- Easing: `cubic-bezier(.22,1,.36,1)` (smooth out), `cubic-bezier(.34,1.56,.64,1)` (bouncy), `ease-in-out` for loops.
  Durations: micro 120-200 ms, UI 200-350 ms, entrances 500-800 ms, ambient 6-20 s. Stagger 60-100 ms per item.
- Always: `@media (prefers-reduced-motion: reduce)` disables parallax, loops and big movement.

## Native HTML that replaces widgets
`<dialog>` (modal, focus trap, Esc), `popover` attribute with `popovertarget` (tooltips, menus, no JS), `<details name="faq">`
(exclusive accordion), `<input type="date|range|color">`, `inert` (disable a region), `loading="lazy"` and `decoding="async"` on
images, `<picture>` for art direction, `fetchpriority="high"` on the hero image, `scroll-snap-type` for carousels.
```css
.carousel { display: flex; overflow-x: auto; scroll-snap-type: x mandatory; gap: 1rem; scrollbar-width: none; }
.carousel > * { flex: 0 0 min(22rem, 85%); scroll-snap-align: start; }
```

## Typography details
```css
body { font-feature-settings: "ss01", "cv11"; font-variant-numeric: tabular-nums; -webkit-font-smoothing: antialiased; }
h1, h2 { letter-spacing: -0.02em; }
.eyebrow { text-transform: uppercase; letter-spacing: .14em; font-size: .75rem; }
.drop-cap::first-letter { float: left; font: 700 4rem/1 var(--font-display); padding-right: .5rem; }
@font-face { font-family: "Inter"; src: url(/fonts/InterVariable.woff2) format("woff2"); font-display: swap; font-weight: 100 900; }
```
Offline-safe fonts: `npm i @fontsource-variable/inter @fontsource-variable/fraunces` (OFL licence) and import them in main.tsx, so the page
looks right even with no internet.

## Responsive and accessibility basics
- Mobile first; breakpoints 640 / 768 / 1024 / 1280. Test 375 and 1280. Touch targets >= 44 px.
- `:focus-visible` ring on everything interactive; never `outline: none` without a replacement.
- `forced-colors` and `prefers-contrast` are cheap wins: keep borders on controls, do not rely on shadows alone.
- `@media (hover: hover)` around hover-only effects; `@media (pointer: coarse)` to enlarge targets.

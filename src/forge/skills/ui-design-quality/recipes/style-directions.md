# Visual directions (pick ONE per product; variants of one page must use different directions)

Each direction is a complete point of view: palette, type, shape, depth, layout habit, motion, and a CSS recipe. They
change the whole feel, not just colours. Name the chosen direction in DESIGN.md. Mix at most one idea from another.

## 1. Soft editorial (warm, humane, trustworthy)
Palette: warm off-white #faf8f6, ink #1d1a17, one deep accent. Type: a serif display (Fraunces, Playfair) with Inter.
Shape: radius 20px, hairline borders, very soft shadows. Layout: generous whitespace, asymmetric two-column sections,
big pull numbers. Motion: slow fades, 600-700 ms. Use for: health, charity, education, boutique.
```css
.card { border-radius: 1.25rem; border: 1px solid var(--color-ink-200); box-shadow: 0 12px 32px -16px rgb(29 26 23 / .18); }
```

## 2. Bold campaign / poster
Palette: near-black #0b0b0c + one hot colour (#e11d48 or #ffd400) + white. Type: huge grotesk (Space Grotesk, Archivo
Black) at 72-140 px, tight tracking -0.04em, uppercase labels. Shape: sharp corners or one big radius, thick 2-3 px
borders, hard offset shadows. Layout: full-bleed colour blocks, oversized numerals, diagonal or rotated tags,
a countdown as the hero visual. Motion: snappy 200 ms, marquee strips. Use for: events, drives, launches, sport.
```css
.poster-btn { border: 3px solid #0b0b0c; box-shadow: 6px 6px 0 #0b0b0c; transition: transform .15s, box-shadow .15s; }
.poster-btn:hover { transform: translate(3px, 3px); box-shadow: 3px 3px 0 #0b0b0c; }
```

## 3. Neo-brutalist
Palette: flat saturated colours (#ffde59, #ff6b6b, #4ecdc4) on cream #fffaf0, black outlines. Type: chunky sans or
mono. Shape: 0-8 px radius, 3 px black borders, hard shadows 4-8 px. Layout: visible grid, stickers, tilted cards
(`rotate(-1.5deg)`). No gradients, no blur. Use for: creative tools, indie products, playful brands.

## 4. Glass and aurora (modern product, dark)
Palette: #0a0b10 base, glass panels rgba(255,255,255,.06) with 1px rgba(255,255,255,.12) borders, indigo/violet/cyan
glow used sparingly. Type: Inter or Geist, light weights for display, tight tracking. Shape: radius 16-24. Depth:
backdrop-filter blur 16-24 px, inner top highlight, soft coloured shadow. Layout: centred hero over aurora blobs,
bento grid below. Motion: slow drift, spotlight cards, border beam on the hero card. Use for: SaaS, AI, developer tools.
```css
.panel { background: rgb(255 255 255 / .06); border: 1px solid rgb(255 255 255 / .12); backdrop-filter: blur(20px);
  box-shadow: inset 0 1px 0 rgb(255 255 255 / .08), 0 24px 48px -24px rgb(99 102 241 / .35); }
```
(see `.aurora`, `.spotlight`, `.beam` in motion.css)

## 5. Clean product (Stripe/Linear spirit, light)
Palette: white and #f6f9fc, one saturated accent (#635bff or #5e6ad2), navy text #0a2540. Type: Inter with
tabular figures, -0.02em tracking on headings. Shape: radius 8-12, 1px borders, layered soft shadows. Layout: left-aligned
hero with a product mockup right, logo strip, feature rows alternating, pricing cards with one highlighted. Motion:
subtle, 200 ms, hover lifts. Use for: B2B, fintech, dashboards.

## 6. Bento and cards
Layout built from an unequal grid of rounded tiles (2x2, 1x2, 1x1) each holding one idea: a number, a chart, a quote,
a mini illustration. Palette: neutral tiles with two tinted accents. Use CSS grid with `grid-template-areas` or
`col-span-2 row-span-2`. Works for: feature overviews, personal sites, dashboards' home.
```css
.bento { display: grid; gap: 1rem; grid-template-columns: repeat(4, 1fr); grid-auto-rows: 12rem; }
.bento > :nth-child(1) { grid-column: span 2; grid-row: span 2; }
@media (max-width: 767px) { .bento { grid-template-columns: 1fr; grid-auto-rows: auto; } .bento > * { grid-column: auto !important; grid-row: auto !important; } }
```

## 7. Playful and friendly
Palette: bright but friendly (#ff7a59, #ffd166, #06d6a0 on #fffdf7), big rounded shapes (radius 28px, pills),
illustrated blobs (SVG), emoji-free icons with thick strokes. Type: rounded sans (Nunito, Baloo, Fredoka) for headings.
Motion: bouncy easing `cubic-bezier(.34,1.56,.64,1)`, wiggle on hover. Use for: kids, food, community, consumer apps.

## 6b. Claymorphism and soft 3D
Pastel fills, radius 24-32, double inner shadows: `box-shadow: inset 6px 6px 12px rgb(255 255 255 / .6),
inset -6px -6px 12px rgb(0 0 0 / .08), 12px 12px 24px rgb(0 0 0 / .1)`. Chunky icons, no borders. Use sparingly: onboarding,
games, kids' products.

## 8. Dark dashboard (data heavy)
Palette: #0b0d12 / #12151c surfaces, borders #1f2330, text #e5e7eb / #9ca3af, accent #818cf8, status colours
(green #34d399, amber #fbbf24, red #f87171). Density high (VISUAL_DENSITY 7-9), 13-14 px body, tabular figures, mono
for ids. Charts with thin lines, 1 accent + muted greys, area gradient fills at 15% opacity. Left nav 240 px, sticky
table headers, keyboard shortcuts hint. Use for: analytics, ops, monitoring.

## 9. Retro / terminal / pixel
Monospace type, 1 px borders, scanline or dot-grid background, limited 3-4 colour palette (phosphor green on black,
or amber), blinking caret, ASCII dividers. Use for: developer tools, games, nostalgic brands. Keep contrast high.

## 10. Minimal monochrome
Black, white, one grey, one accent used once per screen. Large type, huge margins, thin rules, no shadows, no
gradients, real photography or none. Layout: strict grid with a visible baseline. Use for: portfolios, architecture,
luxury. Warning: minimal is not empty: it needs excellent type and real content.

## Choosing and varying
- Match the direction to the audience and mood, not to what is trendy. Health and charity: 1 or 6; events: 2 or 3; SaaS: 4 or 5.
- For several variants of one page choose directions at least two numbers apart on mood (for example 1, 2, 4) and change
  type, layout and motion together, not just colour.
- Whatever you choose: one accent, a real type pairing, designed states, contrast 4.5:1, 375 px that looks intentional.

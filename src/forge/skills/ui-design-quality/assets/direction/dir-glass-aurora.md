---
id: dir-glass-aurora
type: direction
title: Glass and aurora
summary: "Dark base, frosted glass panels, soft glow and slow drifting colour: modern product feel."
moods: [modern, dark, premium, techy]
products: [saas, ai, developer tools]
tags: [visual direction, Inter or Geist]
density: balanced
dependencies: []
licence: original
source: authored for DebCraft (style-directions.md, D-251)
tested: "text direction used in the three-design task (D-251, D-252); not yet rendered as its own preview"
---

## Glass and aurora

Palette: #0a0b10 base, glass panels rgba(255,255,255,.06) with 1px rgba(255,255,255,.12) borders, indigo/violet/cyan
glow used sparingly. Type: Inter or Geist, light weights for display, tight tracking. Shape: radius 16-24. Depth:
backdrop-filter blur 16-24 px, inner top highlight, soft coloured shadow. Layout: centred hero over aurora blobs,
bento grid below. Motion: slow drift, spotlight cards, border beam on the hero card. Use for: SaaS, AI, developer tools.
```css
.panel { background: rgb(255 255 255 / .06); border: 1px solid rgb(255 255 255 / .12); backdrop-filter: blur(20px);
  box-shadow: inset 0 1px 0 rgb(255 255 255 / .08), 0 24px 48px -24px rgb(99 102 241 / .35); }
```
(see `.aurora`, `.spotlight`, `.beam` in motion.css)

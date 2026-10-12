---
id: dir-bold-poster
type: direction
title: Bold campaign poster
summary: "Near-black with one hot colour, huge tight type, hard offset shadows, snappy motion: urgent and loud."
moods: [bold, urgent, loud, energetic]
products: [events, drives, launches, sport]
tags: [visual direction, Space Grotesk or Archivo Black]
density: balanced
dependencies: []
licence: original
source: authored for DebCraft (style-directions.md, D-251)
tested: "text direction used in the three-design task (D-251, D-252); not yet rendered as its own preview"
---

## Bold campaign poster

Palette: near-black #0b0b0c + one hot colour (#e11d48 or #ffd400) + white. Type: huge grotesk (Space Grotesk, Archivo
Black) at 72-140 px, tight tracking -0.04em, uppercase labels. Shape: sharp corners or one big radius, thick 2-3 px
borders, hard offset shadows. Layout: full-bleed colour blocks, oversized numerals, diagonal or rotated tags,
a countdown as the hero visual. Motion: snappy 200 ms, marquee strips. Use for: events, drives, launches, sport.
```css
.poster-btn { border: 3px solid #0b0b0c; box-shadow: 6px 6px 0 #0b0b0c; transition: transform .15s, box-shadow .15s; }
.poster-btn:hover { transform: translate(3px, 3px); box-shadow: 3px 3px 0 #0b0b0c; }
```

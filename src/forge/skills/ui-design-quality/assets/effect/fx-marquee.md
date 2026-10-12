---
id: fx-marquee
type: effect
title: Marquee strip
summary: "An endless horizontal strip for logos or short phrases, pausing on hover."
moods: [bold, playful, energetic]
products: [logos, campaign, events]
tags: [animation, motion]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (motion kit, D-251)"
tested: "kit built with Vite + Tailwind v4, audit clean at 1280 and 375 px, reduced-motion safe (D-251)"
files:
  - {from: recipes/motion.css, to: src/motion.css}
  - {from: recipes/motion.tsx, to: src/motion.tsx}
---

## Marquee strip

`<Marquee>{items}</Marquee>`; the component duplicates the children so the loop is seamless. Keep the strip to one line of short items.

Effect budget: count it against the page's MOTION_INTENSITY dial; one signature effect per page.

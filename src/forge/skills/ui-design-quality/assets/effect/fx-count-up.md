---
id: fx-count-up
type: effect
title: Count-up numbers
summary: A number that counts up once when it scrolls into view.
moods: [bold, energetic, trustworthy]
products: [stats, landing, dashboard]
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

## Count-up numbers

`<CountUp to={450} suffix="+" />`. Use tabular figures in the surrounding CSS. Respects reduced motion (shows the final number).

Effect budget: count it against the page's MOTION_INTENSITY dial; one signature effect per page.

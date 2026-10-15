---
id: mi-loader-heartbeat
type: effect
title: "Heartbeat"
summary: "A heart-shaped pulse: two quick beats and a rest."
moods: [warm, caring]
products: [health, charity, care]
tags: [animation, motion, micro-interaction, loader, css, no build step]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (micro-interaction kit, D-382)"
tested: "demo page in Edge: the action (hover, focus, check, press or invalid) changes the probed property or the animation runs, and it is switched off under reduced motion (tests/test_micro_effects.py, D-382)"
files:
  - from: recipes/motion-micro.css
    to: src/motion-micro.css
---

## Heartbeat

A heart-shaped pulse: two quick beats and a rest. Health, care and donation products; it is a meaning, not just a spinner.

Markup:

```html
<span class="mi-loader-heartbeat" role="status" aria-label="Loading"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s-7.5-4.6-9.6-9.2C.9 8.5 2.8 5 6.2 5c2 0 3.5 1 4.5 2.6l1.3 1.9 1.3-1.9C14.3 6 15.8 5 17.8 5c3.4 0 5.3 3.5 3.8 6.8C19.5 16.4 12 21 12 21z"/></svg></span>
```

Import the stylesheet once, after index.css: `import "./motion-micro.css"` (it holds all forty micro-interactions; keep the classes you use). It reads the project's tokens with fallbacks and stops under `prefers-reduced-motion`; do not rely on motion alone to say something (show a text state too).

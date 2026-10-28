---
id: app-react-calendar
type: section
title: "React app screen: Calendar: week view"
summary: "A week calendar: a mini month and calendar toggles on the side, a time grid with positioned, colour-coded events, today's column marked and a Day, Week, Month switch. (React, TSX with one plain stylesheet.)"
moods: [organised, calm, light]
products: [scheduling, booking, planning, team calendar, appointments]
tags: [calendar, week view, schedule, side panel, app screen, react, tsx, plain css, light]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-366, application screens for plain HTML apps)"
tested: "built with Vite and React (type-checked), rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing (tests/test_app_screens_react.py, D-377)"
files:
  - from: recipes/app-react/calendar/Screen.tsx
    to: src/screens/calendar/Screen.tsx
  - from: recipes/app-react/calendar/screen.css
    to: src/screens/calendar/screen.css
  - from: recipes/app-react/calendar/tokens.css
    to: src/screens/calendar/tokens.css
preview: assets/preview/app-calendar-desktop.jpg
---
The React version of the HTML screen `app-calendar`: `Screen.tsx` holds the same structure and class names with the same sample content, `screen.css` the stylesheet (one plain
file, class names as in the HTML recipe), `tokens.css` the `:root` token block of the example. Copy the files, then:
1. Replace `tokens.css` with the tokens exported from DESIGN.md (`design_md_export css-variables`) and import it once in `src/main.tsx` or `index.css`; the screen reads only those CSS variables.
2. Split `Screen.tsx` into components (the layout, the table, the chart cards), feed them real data instead of the sample, change every word and number to the product's own, and delete what it does not have.
3. The icons are one inline sprite at the top of the component: keep the ones you use. A project that already uses Tailwind may turn the class names into utility classes; the structure stays.
4. Check it at 1280 and 375 px with `browser_screenshot`.

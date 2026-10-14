---
id: app-react-table-data
type: section
title: "React app screen: Table: people with filters and bulk actions"
summary: "A full data table: search, status segments, a bulk-action bar for selected rows, avatars, status pills, row actions and pagination. (React, TSX with one plain stylesheet.)"
moods: [precise, plain, light]
products: [admin, team management, saas, hr, back office]
tags: [table, filters, bulk actions, pagination, top navigation, app screen, react, tsx, plain css, light]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-366, application screens for plain HTML apps)"
tested: "built with Vite and React (type-checked), rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing (tests/test_app_screens_react.py, D-377)"
files:
  - from: recipes/app-react/table-data/Screen.tsx
    to: src/screens/table-data/Screen.tsx
  - from: recipes/app-react/table-data/screen.css
    to: src/screens/table-data/screen.css
  - from: recipes/app-react/table-data/tokens.css
    to: src/screens/table-data/tokens.css
---
The React version of the HTML screen `app-table-data`: `Screen.tsx` holds the same structure and class names with the same sample content, `screen.css` the stylesheet (one plain
file, class names as in the HTML recipe), `tokens.css` the `:root` token block of the example. Copy the files, then:
1. Replace `tokens.css` with the tokens exported from DESIGN.md (`design_md_export css-variables`) and import it once in `src/main.tsx` or `index.css`; the screen reads only those CSS variables.
2. Split `Screen.tsx` into components (the layout, the table, the chart cards), feed them real data instead of the sample, change every word and number to the product's own, and delete what it does not have.
3. The icons are one inline sprite at the top of the component: keep the ones you use. A project that already uses Tailwind may turn the class names into utility classes; the structure stays.
4. Check it at 1280 and 375 px with `browser_screenshot`.

---
id: app-table-editable-grid
type: section
title: "App screen: Table: editable grid for fast entry"
summary: "A grid whose number cells are inputs: scan or type a SKU, tab through counts, low-stock status, and a sticky save bar that says how many cells changed."
moods: [practical, fast, light]
products: [inventory, warehouse, data entry, spreadsheet, back office]
tags: [table, editable, data entry, inputs, sticky save bar, app screen, plain html, css, no build step, light]
density: dense
dependencies: []
licence: original
source: "authored for DebCraft (D-366, application screens for plain HTML apps)"
tested: "rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing, looked at (tests/test_app_screens.py, D-366)"
files:
  - from: recipes/app-screens/table-editable-grid.html
    to: screens/table-editable-grid.html
preview: assets/preview/app-table-editable-grid-desktop.jpg
---
A complete, working application screen in plain HTML and CSS: repetitive data entry where speed matters: counts, timesheets, prices, scores; keyboard first, with a clear unsaved-changes bar. Open the file to see it, then bring it into the project and make it the
product's own. Do not ship it as it is.
1. Replace the `:root` block with the tokens exported from DESIGN.md (`design_md_export css-variables`); the screen only uses those variables, so the
   look follows the design system. Fetch and link the fonts the tokens name (`fetch_font`).
2. Change every word, name and number to the product's real content (no placeholder names left), keep the structure that fits the data, and remove what
   the product does not have. The icons are one inline sprite: keep the ones you use.
3. In a framework project, split it into components (the layout, the table, the chart cards) and keep the same classes or turn them into the project's
   utility classes. The charts are SVG shapes with HTML labels: feed them real series instead of the sample numbers.
4. Check it at 1280 and 375 px with `browser_screenshot`; on a phone the side navigation becomes a strip and tables scroll inside their frame.

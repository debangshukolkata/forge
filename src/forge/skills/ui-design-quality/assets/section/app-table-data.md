---
id: app-table-data
type: section
title: "App screen: Table: people with filters and bulk actions"
summary: "A full data table: search, status segments, a bulk-action bar for selected rows, avatars, status pills, row actions and pagination."
moods: [precise, plain, light]
products: [admin, team management, saas, hr, back office]
tags: [table, filters, bulk actions, pagination, top navigation, app screen, plain html, css, no build step, light]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-366, application screens for plain HTML apps)"
tested: "rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing, looked at (tests/test_app_screens.py, D-366)"
files:
  - from: recipes/app-screens/table-data.html
    to: screens/table-data.html
preview: assets/preview/app-table-data-desktop.jpg
---
A complete, working application screen in plain HTML and CSS: any list of records people manage in bulk: users, customers, orders, assets; the table, its filters and the bulk bar are the pattern. Open the file to see it, then bring it into the project and make it the
product's own. Do not ship it as it is.
1. Replace the `:root` block with the tokens exported from DESIGN.md (`design_md_export css-variables`); the screen only uses those variables, so the
   look follows the design system. Fetch and link the fonts the tokens name (`fetch_font`).
2. Change every word, name and number to the product's real content (no placeholder names left), keep the structure that fits the data, and remove what
   the product does not have. The icons are one inline sprite: keep the ones you use.
3. In a framework project, split it into components (the layout, the table, the chart cards) and keep the same classes or turn them into the project's
   utility classes. The charts are SVG shapes with HTML labels: feed them real series instead of the sample numbers.
4. Check it at 1280 and 375 px with `browser_screenshot`; on a phone the side navigation becomes a strip and tables scroll inside their frame.

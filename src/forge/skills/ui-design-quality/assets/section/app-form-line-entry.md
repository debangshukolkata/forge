---
id: app-form-line-entry
type: section
title: "App screen: Form: invoice with line items"
summary: "A document-style data entry screen: header fields, an editable lines table with live amounts, notes and a totals block, with save, preview and send actions."
moods: [businesslike, efficient, light]
products: [invoicing, quotes, orders, expenses, timesheets]
tags: [form, data entry, line items, totals, side navigation, app screen, plain html, css, no build step, light]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-366, application screens for plain HTML apps)"
tested: "rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing, looked at (tests/test_app_screens.py, D-366)"
files:
  - from: recipes/app-screens/form-line-entry.html
    to: screens/form-line-entry.html
preview: assets/preview/app-form-line-entry-desktop.jpg
---
A complete, working application screen in plain HTML and CSS: entering a document made of repeated lines: invoices, quotes, purchase orders, expense reports. Open the file to see it, then bring it into the project and make it the
product's own. Do not ship it as it is.
1. Replace the `:root` block with the tokens exported from DESIGN.md (`design_md_export css-variables`); the screen only uses those variables, so the
   look follows the design system. Fetch and link the fonts the tokens name (`fetch_font`).
2. Change every word, name and number to the product's real content (no placeholder names left), keep the structure that fits the data, and remove what
   the product does not have. The icons are one inline sprite: keep the ones you use.
3. In a framework project, split it into components (the layout, the table, the chart cards) and keep the same classes or turn them into the project's
   utility classes. The charts are SVG shapes with HTML labels: feed them real series instead of the sample numbers.
4. Check it at 1280 and 375 px with `browser_screenshot`; on a phone the side navigation becomes a strip and tables scroll inside their frame.

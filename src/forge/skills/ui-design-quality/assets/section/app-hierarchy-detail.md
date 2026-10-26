---
id: app-hierarchy-detail
type: section
title: "App screen: Hierarchy: expandable tree with a detail panel"
summary: "A department tree on the left (a coloured dot for each level, chevrons, code badges, the head of each, edit on hover) and the selected department on the right with a header, tabs with counts and note cards."
moods: [businesslike, calm, light]
products: [organisation, departments, hierarchy, org chart, directory, categories, back office]
tags: [tree, hierarchy, detail panel, tabs, notes, expand collapse, side navigation, app screen, plain html, css, no build step, light]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-366, application screens for plain HTML apps)"
tested: "rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing, looked at (tests/test_app_screens.py, D-366)"
files:
  - from: recipes/app-screens/hierarchy-detail.html
    to: screens/hierarchy-detail.html
---
A complete, working application screen in plain HTML and CSS: browsing a structure and acting on one part of it: departments, teams, accounts, categories, locations, charts of accounts. Open the file to see it, then bring it into the project and make it the
product's own. Do not ship it as it is.
1. Replace the `:root` block with the tokens exported from DESIGN.md (`design_md_export css-variables`); the screen only uses those variables, so the
   look follows the design system. Fetch and link the fonts the tokens name (`fetch_font`).
2. Change every word, name and number to the product's real content (no placeholder names left), keep the structure that fits the data, and remove what
   the product does not have. The icons are one inline sprite: keep the ones you use.
3. In a framework project, split it into components (the layout, the table, the chart cards) and keep the same classes or turn them into the project's
   utility classes. The charts are SVG shapes with HTML labels: feed them real series instead of the sample numbers.
4. Check it at 1280 and 375 px with `browser_screenshot`; on a phone the side navigation becomes a strip and tables scroll inside their frame.

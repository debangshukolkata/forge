---
id: app-helpdesk-queue
type: section
title: "App screen: Support queue: tickets with reply deadlines"
summary: "A ticket queue sorted by what is due: priority and reply-by pills that turn red as the deadline nears, assignee avatars, status tabs with counts, team workload meters and quick replies."
moods: [practical, calm, light]
products: [support, tickets, helpdesk, customer service, sla, back office]
tags: [queue, tickets, deadline, workload, tabs, quick replies, side navigation, app screen, plain html, css, no build step, light]
density: dense
dependencies: []
licence: original
source: "authored for DebCraft (D-366, application screens for plain HTML apps)"
tested: "rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing, looked at (tests/test_app_screens.py, D-366)"
files:
  - from: recipes/app-screens/helpdesk-queue.html
    to: screens/helpdesk-queue.html
preview: assets/preview/app-helpdesk-queue-desktop.jpg
---
A complete, working application screen in plain HTML and CSS: working through a queue against a clock: support desks, IT service desks, claims, requests with service levels. Open the file to see it, then bring it into the project and make it the
product's own. Do not ship it as it is.
1. Replace the `:root` block with the tokens exported from DESIGN.md (`design_md_export css-variables`); the screen only uses those variables, so the
   look follows the design system. Fetch and link the fonts the tokens name (`fetch_font`).
2. Change every word, name and number to the product's real content (no placeholder names left), keep the structure that fits the data, and remove what
   the product does not have. The icons are one inline sprite: keep the ones you use.
3. In a framework project, split it into components (the layout, the table, the chart cards) and keep the same classes or turn them into the project's
   utility classes. The charts are SVG shapes with HTML labels: feed them real series instead of the sample numbers.
4. Check it at 1280 and 375 px with `browser_screenshot`; on a phone the side navigation becomes a strip and tables scroll inside their frame.

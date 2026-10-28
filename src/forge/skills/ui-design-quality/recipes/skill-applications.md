# 0i. Applications: start from a screen recipe, not a blank file
For an application (dashboard, table, form, settings, inbox, calendar, record page, board) do not write the screen from nothing: that is thousands of output
tokens and it looks generic. `find_asset` with type `section` and the tag `app screen` lists 38 complete screens in plain HTML and CSS with believable content, drawn
charts (SVG shapes with HTML labels) and an icon sprite. Families: **dashboards** (sales KPIs, operations board, dark analytics, personal day view), **tables**
(people table with filters and bulk actions, master and detail, kanban board, editable grid for fast entry), **forms** (multi-step wizard, invoice with line items,
long form with an error summary, sign-in split screen, quick capture), **settings** (account and API keys, notification matrix, plan and billing, roles and
permissions), **web-app screens** (inbox, chat, week calendar, customer record, map with a list, document editor, empty / error / offline / loading states) and **back-office screens** (approval queue with a decision panel, audit log with before and after, order fulfilment, stock levels with reorder, receivables ageing, support queue with reply deadlines, CSV import with column mapping, report builder, background jobs monitor, resource timeline with conflicts).
- Forge reads the brief for you: `design_candidates` says whether it reads as an application screen or a brand page and names the three closest screens. For an application, name one as
  `composition: app-...` (or `composition: custom <one line>` when none fits); the first page or screen is refused until `add_asset` has copied the screen you named, so run it
  as soon as you have chosen, and build from the copy instead of from a blank file.
- Pick by the job the user does on the screen, not by the product's industry; then `add_asset` copies the file (it lands in `screens/`) and `view_image` its
  reference pictures. Name it in the candidate's front matter as `composition: app-dashboard-kpi` (or the id you chose).
- Make it the product's own: replace the `:root` block with the tokens from `design_md_export css-variables`, fetch the fonts the tokens name, change every
  word, name and number to the product's real content, delete what the product does not have, add what it does. Never ship the sample copy or numbers.
- Reuse the shell: the other screens of the same app use the same classes (`.app`, `.side`, `.topbar`, `.card`, `.table-wrap`, `.field`, `.pill`), so copy
  the first screen, then write only what differs; keep one shell for the whole app. Every list, search and fetch also needs its empty, no-results, error and
  loading states: `app-empty-states` has them. **In a React project use the React version** (`app-react-<id>`: dashboard-kpi, table-data, form-wizard, settings-account, inbox: `Screen.tsx` + `screen.css` + `tokens.css`, type-checked and built with Vite) and split it into components; for the other screens copy the HTML recipe and convert it the same way.
- Screens must work on a phone: the side navigation becomes a strip and tables scroll inside their frame. Check at 375 px with `browser_screenshot`.

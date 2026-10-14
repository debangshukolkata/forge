# Application screens (D-366)

DebCraft's design studio had seven complete layouts for marketing pages (`lay-*`) and nothing for applications. Dashboards, tables, forms, settings and
web-app screens were written from a blank file every time: thousands of output tokens per page (see docs/SPEED_BENCHMARK.md, speed-6) and a generic result.
The skill `ui-design-quality` now ships **24 application screens** the model copies and edits.

| Family | Screens (catalogue id `app-<name>`) |
|---|---|
| Dashboards | `dashboard-kpi` (sales KPIs, chart, ring, orders), `dashboard-ops` (status counters, shipments, exceptions), `dashboard-analytics` (dark, sparklines, funnel), `dashboard-personal` (day view, goal rings) |
| Tables | `table-data` (filters, bulk bar, pagination), `table-master-detail`, `table-kanban`, `table-editable-grid` (fast entry, unsaved bar) |
| Forms | `form-wizard`, `form-line-entry` (invoice), `form-long` (sections, error summary), `form-sign-in`, `form-quick-capture` |
| Settings | `settings-account` (profile, security, API keys, danger zone), `settings-notifications` (matrix), `settings-billing`, `settings-roles` (permission grid) |
| Web app | `inbox`, `chat`, `calendar`, `record`, `map-list`, `editor`, `empty-states` |

How they are made: `scripts/dev/app_screens/` holds the shared kit (`kit.py`: five palettes, bundled font stacks, an icon sprite drawn for this project, the
base stylesheet, SVG-and-HTML chart builders) and one definition per screen. `python scripts/dev/make_app_screens.py` writes
`recipes/app-screens/<id>.html` (standalone, no build step, no network), `assets/section/app-<id>.md` and two pictures per screen;
`python scripts/build_asset_catalogue.py` regenerates the catalogue; `python scripts/dev/app_screens_look.py` prints the audit and writes full-page pictures
to `test-artifacts/app-screens/` to look at. The files are original work (no third-party code or catalogue was used).

Rules every screen keeps (tests/test_app_screens.py): audit clean at 1280 px, no sideways scroll at 375 px, one `h1`, body text 14 px or more, colours only through
the `:root` tokens (the block the model replaces with `design_md_export css-variables`), readable chart labels (HTML, not scaled SVG text), working keyboard
focus, a phone layout in which the side navigation becomes a strip and tables scroll inside their frame. Retrieval: 24 of 24 test prompts find their screen in
the first three results.

How the model uses them: system prompt line and skill section 0i: `find_asset` (type `section`, tag `app screen`) by the job on the screen, `add_asset` copies
the file to `screens/`, name it as `composition: app-...` in the candidate DESIGN.md, replace the tokens, rewrite the content, reuse the shell for the other screens.

Audit changes made with it (tests/test_ui_audit_studio.py): a `role="img"` chart of 150 x 80 px or more counts as imagery; a page that looks like an application
(eight or more controls, or an aside, tab list or header navigation with three or more) is not asked for pictures or a 36 px landing headline (20 px is enough).

React versions (D-377): five screens (`app-react-dashboard-kpi`, `-table-data`, `-form-wizard`, `-settings-account`, `-inbox`) with `Screen.tsx`, `screen.css` and `tokens.css`, made from the same definitions by a small HTML-to-JSX converter (`scripts/dev/app_screens/jsx.py`) so the structure cannot drift; `tests/test_app_screens_react.py` type-checks and builds each with Vite, audits it at both widths and compares its text with the HTML recipe.

Open: React versions of the other 19 screens (copy and convert the HTML recipe the same way); live measurement of the output tokens saved on the dashboard brief.

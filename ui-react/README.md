# Forge web UI

Forge's only web UI (React 19 + TypeScript + Tailwind CSS 4, built with Vite). The older classic UI was removed
on 2026-09-28 (DECISIONS D-117).

## Using it

```powershell
forge ui
```

Edge opens `http://127.0.0.1:8765`. No Node.js is needed: the built files ship inside Forge
(`src/forge/web/react/`). Loopback only, a per-run session token in an HttpOnly cookie, Host/Origin checks and
a strict Content-Security-Policy (`'self'` only).

## Changing it (needs Node.js 20+ and access to the npm registry)

```powershell
cd ui-react
npm install
# terminal 1: Forge, accepting the Vite dev server as a second origin (loopback only)
forge ui --dev
# terminal 2: the dev server with hot reload on http://127.0.0.1:5173
npm run dev
```

Open the link Forge prints once (it sets the session cookie and forwards you to the dev server). Vite forwards
`/api` and `/ws` to Forge on 8765.

When you're done:

```powershell
npm run build     # type-checks, then writes the static files to ../src/forge/web/react
```

Commit `ui-react/` and `src/forge/web/react/` together. `node_modules/` is never committed.

## Design

Generated with the ui-ux-pro-max skill: "Minimalism & Swiss Style" for developer tools, dark first with a light
theme, palette "code dark + run green" (slate `#0F172A`, surface `#1B2336`, accent `#22C55E`), IBM Plex Sans for
text and JetBrains Mono for code (bundled, no Google Fonts — the laptop may be offline and the CSP allows only
`'self'`). Semantic tokens live in `src/index.css` (`bg`, `surface`, `raised`, `fg`, `fg-muted`, `accent`,
`danger`, `warn`, `info`); components use the tokens, never raw colours.

Rules kept throughout: visible focus rings, 4.5:1 text contrast in both themes, SVG icons (lucide) instead of
emoji, 150–200 ms colour transitions, `prefers-reduced-motion` respected, errors announced with `role="alert"`,
every model/tool text rendered as text or as Markdown sanitised with DOMPurify.

## Layout

- `src/useForge.ts` — the connection: `/api/state`, the WebSocket with replay, events → chat timeline.
- `src/components/` — TopBar (animated cost), Sidebar (projects), Home (New project form + environment
  check), Chat (timeline, tool cards, approval / question / action cards), Composer (attachments, `/` and `@`
  suggestions, history), Activity (progress stepper with cost/time per step, live activity line), RunMap (task
  graph with React Flow + dagre, SVG timeline), FailureDrawer, `ui.tsx`.
- `src/runmap.ts` — the Run map's model, derived only from the event list (so replay and live draw the same).
- `src/panels/Panels.tsx` — Tasks, Files, Diffs, DB, Evals, Learning, Usage, Settings; collapses to an icon rail.

## Licences of what ships in the build

react, react-dom (MIT) · lucide-react (ISC) · marked (MIT) · dompurify (MPL-2.0 or Apache-2.0) · highlight.js
(BSD-3-Clause) · diff2html (MIT) · @xyflow/react (MIT) · @dagrejs/dagre (MIT) · IBM Plex Sans, JetBrains Mono via @fontsource (SIL OFL 1.1).

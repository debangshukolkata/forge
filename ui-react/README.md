# Forge React UI

The new web UI (React 19 + TypeScript + Tailwind CSS 4, built with Vite). It runs **next to** the classic UI
until it has been tested; both talk to the same Forge API.

| | Classic UI | React UI |
|---|---|---|
| Start | `forge ui` | `forge ui --react` |
| Port | 8765 | 8766 |
| Needs Node.js to use? | no | no — the built files ship inside Forge (`src/forge/web/react/`) |

## Using it

```powershell
forge ui --react
```

Edge opens `http://127.0.0.1:8766`. Everything else (token, cookie, security policy, loopback only) works exactly
like the classic UI; each UI has its own session cookie, so both can run at the same time.

## Changing it (needs Node.js 20+ and access to the npm registry)

```powershell
cd ui-react
npm install
# terminal 1: Forge, accepting the Vite dev server as a second origin (loopback only)
forge ui --react --dev
# terminal 2: the dev server with hot reload on http://127.0.0.1:5173
npm run dev
```

Open the link Forge prints once (it sets the session cookie and forwards you to the dev server). Vite forwards
`/api` and `/ws` to Forge on 8766.

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
- `src/components/` — TopBar, Sidebar (projects), Home (New project form + environment check), Chat
  (timeline, tool cards, approval / question / action cards, composer with slash-command hints), `ui.tsx`.
- `src/panels/Panels.tsx` — Tasks, Files, Diffs, DB, Evals, Learning, Context, Settings.

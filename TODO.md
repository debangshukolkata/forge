# TODO — Forge build

Status: `[ ]` not started · `[~]` in progress · `[x]` done (acceptance passed + user sign-off)

## Step 1 — Pre-build review
- [x] Understanding, risks, ambiguities, order proposal
- [x] User answers recorded (DECISIONS D-001…D-015), spec amended (§0.2), docs created
- [x] Local Postgres `forge_dev` (D-018), Python 3.13 (D-006), D-008, D-013, D-016, D-017 settled
- [ ] User runs `scripts/dev/import_orchestrix_azure.py` to fill Azure values in `.env` (D-019)
- [x] User approves M0 + M1 brief

## Milestones (order per D-002)
- [x] **M0** Scaffolding — pyproject, src layout, tooling, vendored tiktoken, fixture repo, docs
- [x] **M1** Foundations — config + per-role models, Azure adapter (Responses/Chat), event bus, tokens, retries, streaming, cost, REPL, doctor
- [x] **M2** Workspace — copy, baseline, write jail, redaction core, checkpoints, output generator
- [x] **M3** Core tools + loop — files, search, PowerShell shell, background procs, permission gate, shell classifier v1
- [x] **M4** Context management — §10 (+ sandbox D-050)
- [x] **M5** Knowledge Base — extractors, index, LLM docs, refresh
- [x] **M6** Orchestrator — phases, approvals, tasks, resume, restructure (original, phased design)
- [x] **M6 rework** Flat loop (D-128, D-129, D-130, D-131, D-132) — done 2026-09-29, see below
- [x] **M7** Database — local/remote targets, access levels, scratch per requirement, DB requests, guards
- [x] **M8** Verification & self-correction
- [x] **M9W** Web UI core
- [x] **M9** Diagnose mode
- [x] **M10** Web, browser, memory, UX
- [x] **M10B** Mode B standalone — done 2026-09-28 (D-096, D-102, D-105; live acceptance 1–3, see REMAINING_TASKS)
- [x] **M10C** Learning & self-improvement — done 2026-09-28 (D-089..D-094; live acceptance passed)
- [x] **M10E** Claude Code parity — done 2026-09-28 (D-095; offline gate 10 pass)
- [x] **M10D** Multimodal & evals (general) — done 2026-09-28 (D-097)
- [x] **M11** Hardening & packaging — done 2026-09-28 (D-098..D-106); open: "tables exist in scratch" check (SPEC_DEVIATIONS)
- [x] **UI** React web UI (only UI) — project form, uploads, live progress, cost counter, per-phase/task usage,
  Run map (task graph + timeline, failures drawer, waiting bars), stepper with cost/time per step, collapsible
  side panel — done 2026-09-28 (D-113..D-124)

## Open items
- **M6 rework — flat loop, cadence, judgment-based verification, Contracts store (D-128, D-129, D-130,
  D-131, D-132) — done 2026-09-29:**
  - `agent/orchestrator.py`/`state.py` rewritten: no `Phase` enum, no mandatory CLARIFY/PLAN/REVIEW gates.
    `propose_requirements`/`propose_plan` are optional, non-blocking tools. Verification (§13) is
    judgment-based — the mandatory full-suite-plus-reviewer gate and `MAX_REVIEW_FIX_ROUNDS` are gone.
  - Cadence (D-130) is a persisted `state.cadence` field, set by `detect_cadence()` recognising phrases
    like "go ahead, don't ask me" / "ask me before every step" in chat, or `/mode`; survives a restart
    (D-132). Never waives the always-ask/critical list (§14.2).
  - Resume is automatic and silent (D-132): `state.exported` (not a phase) tracks whether a workspace is
    resume-safe; the resume greeting is `state.resume_summary()`.
  - Wired through `session_host.py`, `cli.py`, `headless.py`, `slash_commands.py`, `console.py`,
    `web/server.py` (kept a backward-compat `phase` key in `/api/state`, mapped to `resume_summary()`, so
    the not-yet-rebuilt React UI degrades instead of breaking).
  - Mode B Contracts store (§6A.2A, D-129): `src/forge/modeb/contracts.py` (`ContractRegister`, per host
    profile), `contract_pin`/`contract_read` tools, `/contracts` command, pinned into context alongside
    profile essentials, and pinning proposes a lesson (scoped to the profile) so Forge recommends a known
    contract on a later requirement. The **web UI Contracts panel** (the other half of the D-129 UI
    decision) is NOT built — chat/`/contracts` is the only interface today; deferred with the rest of the
    React UI work (below).
  - All 6 affected test files rewritten/fixed (`test_orchestrator.py` fully rewritten, `test_db.py`,
    `test_m10_wiring.py`, `test_live_orchestrator.py` updated, `test_web_e2e.py`'s two Run-map/stepper
    tests marked `@pytest.mark.skip` citing D-131) plus new `tests/test_contracts.py` (8 tests). ruff,
    mypy and `check_secrets.py` clean. Full non-live/non-pg suite (~400+ tests, `test_sandbox.py`/
    `test_hardening.py` excluded to save time, not for correctness) passes cleanly end to end in ~15
    minutes, exit code 0, only the two deliberate D-131 skips — a first pass mistakenly reported this as
    a "hanging" test-infrastructure issue because of timeouts (40–250s) too short for the fixtures' real
    filesystem/git I/O; corrected after a run with a realistic budget.
- UI: Run map/stepper redesign (D-133) — **milestones 1–3 done 2026-09-29.**
  - **M1** (`runmap.ts` + `RunMap.tsx`): `planGraph()`'s fixed phase skeleton replaced by `buildGraph()`, a
    live-growing DAG built purely from `RunModel` (start/task/agent/deliver nodes appear only once their event
    has fired; `depends_on` edges unchanged; agent nodes attach to their task or to start via a `spawned` edge;
    the `deliver` node appears once `task_list_updated.exported` is true — new field, D-133a). `ProgressHeader`
    (the stale phase stepper) and its dead plumbing (`STEPS`/`STEP_OF_PHASE`/`stepOf` in `activity.ts`,
    `PHASE_LABEL`/`phaseWorkMs`/`planGraph`/`Marker`/`Span`/lanes in `runmap.ts`) deleted, along with the
    separate SVG timeline pane (`Timeline`/`SpanBar`/`MarkerGlyph`/`Legend`); failure/stuck counts moved onto
    task-node badges (agent nodes show a failed-icon badge; no numeric per-agent count yet — no such signal
    exists today).
  - **M2** (`RunMap.tsx`, `index.css`): CSS-only animated relayout — `.react-flow__node` gets a `transform`
    transition so dagre's full relayout-on-structural-change glides instead of snapping; new nodes/edges get a
    fade/scale-in entrance (`prefers-reduced-motion`-aware). Auto-fit now gates on user interaction:
    `onMoveStart`'s `event` is null for programmatic moves (fitView) and non-null for real user gestures, so a
    manual pan/zoom disables further auto-fit until a new `ControlButton` ("Recenter", `data-testid
    ="run-map-recenter"`) re-fits and re-arms it. Along the way, fixed a bug where `AutoFit` was gated on
    `useNodesInitialized()`, which never became true in this app (nodes are sized via inline style, not
    measured) — silently meaning the effect never actually fired; removed that dependency since dagre already
    positions nodes before mount. Manually verified against a live server with a throwaway Playwright script
    (not committed): pan disables auto-fit, Recenter re-fits and re-arms it.
  - **M3** (`Activity.tsx`, `Composer.tsx`): `ActivityLine` gained a per-task cost/time badge
    (`by_task[current_task]` + elapsed derived from the first event where `where.task` matches, since M1's
    rewrite dropped the old per-task start-timestamp plumbing) and a new `RunTotals` strip (`cost.project.total`
    — already exposed, no manual summing needed — + `runStartedAt`), shown only while busy, styled quieter than
    the activity line. Call site added in `Composer.tsx` (not `Chat.tsx` — that's where `ActivityLine`/the old
    `ProgressHeader` actually lived).
  - `npm run build` (tsc -b + vite build) passes clean after all three milestones combined; targeted backend
    tests (`-k "orchestrator or task_list or publish_tasks"`) 15 passed for the `orchestrator.py` `exported`
    field.
  - **Still open:** `agent_finished` gaining `cost_usd` (documented fast-follow, backend — no per-agent cost
    number yet, only duration/ok). Re-enabling the two skipped `test_web_e2e.py` Run-map/stepper tests (D-131)
    — deferred; they target the old pre-D-133 DOM and need rewriting against the new graph structure, not just
    un-skipping. Also still needs: the Contracts panel (D-129, above). D-123 (phase-row-for-multi-day-runs) is
    folded into this redesign, not separate — the growing DAG loads pre-laid-out for old runs.
- UI: the chat column showed a horizontal scrollbar in the user's runmap-demo (some wide content); not yet
  investigated.
- Bug fixed 2026-09-29 (D-135): `propose_plan`/`update_plan` now end the turn so `_run_agent` can call
  `_start_task` right after a plan is (re)created — previously, if the model never naturally paused after
  `propose_plan`, `current_task` stayed `None` all session and every `task_update` was rejected (reproduced
  in the `new-demo` test run: all 5 tasks stuck `pending`, model gave up and reported itself blocked in chat).
- UI: still open — a requirement that finishes (or gets blocked) and correctly goes idle looks visually
  identical to a stuck session: "Idle", pending tasks, no cue either way. Needs a clear idle-with-a-final-
  reply state (vs. idle-and-actually-stuck) so this isn't mistaken for a hang again; surfaced by testing D-135.
- Feature done 2026-09-29 (D-136): project-creation setup now shows real phase labels ("Creating workspace
  folders…" → "Creating the Python environment…" → "Installing the test runner (pytest)…" for Mode B; file
  count + current path for Mode A's repo copy) instead of one static "Setting up…" string for the whole
  blocking call. New `GET /api/setup-progress`, polled by `Home.tsx` every 400ms while creating a project.
- M7: embedded-Postgres fallback (`pgserver`) not built (SPEC_DEVIATIONS); "every table the code touches
  exists in scratch before DB-backed runs" check not built; `db_schema` results not yet cached into the KB.
- New initiative, scoped 2026-09-29 (D-137): frontend support (React/Angular/CSS), so Forge can eventually
  build a 3-tier app. Deliberately scoped down to a first proving slice — **React support in Mode A only**
  (extending an existing repo's React app, not designing one from scratch), with headless-browser verification
  (Playwright) in scope from the start. Explicitly deferred, not decided: Angular, any other framework, Mode B
  for frontends (from-scratch design with no existing repo to read conventions from), and the general
  tech-agnostic abstraction the user originally asked for — each needs its own design pass once phase 1 is
  real. See D-137 for the full reasoning on why the full-scope request was scoped down first.
- D-138/D-139 (2026-09-29): phase 1 built — `workspace/nodeenv.py` (Node/React app detection: package
  manager from lockfile, node binary, real script names from the app's own package.json),
  `verify/react_ladder.py` (typecheck/lint/unit-tests/build rungs, each skipping when the repo doesn't
  configure that tool), and `verify/ladder.py`'s `VerifyLadder.run()` dispatcher (routes `.py` changes to the
  existing Python ladder and `.ts`/`.tsx`/`.js`/`.jsx`/`.css` changes to the new React ladder, combining
  reports; a Python-only workspace is unaffected — regression-tested).
- D-140 (2026-09-29): the browser smoke-check rung's call site is now built — `agent/frontend_smoke.py`
  (new), called from `Orchestrator._export()` only when `workspace.info.node_env is not None`. Starts the
  repo's own dev/start/preview script (new `NodeEnvironment.dev_command`, D-139's "read the repo's own
  scripts" rule extended) as a background process on a free port, loads it with the existing headless
  `BrowserSession` (tools/browser.py), checks for `[pageerror]` console entries and a non-blank body, and
  always stops the server afterward. Informational only (D-132): pass/fail/skip is appended as a
  `## Frontend smoke check` section in reports/final.md, mirroring the existing Restructure-check block, and
  never fails or blocks `_export()` — a Python-only workspace's export is untouched (regression-tested).
  **Phase 1 (D-137) is now complete** in the sense originally scoped: node detection, the React verify
  ladder, the dispatcher, and the checkpoint-only browser smoke check are all built. Still open, explicitly
  out of scope, carried forward to phase 2 or a later pass: `npm install` automation (left to the agent via
  the existing approved `run_command` tool), Angular, Mode B frontend support, monorepo auto-discovery of a
  frontend folder separate from the Python `app_subfolder`, real import-graph-based targeted-test selection
  for React (the ladder currently runs its whole test command, not a per-change selector), and the general
  tech-agnostic verify-rung/environment/contract abstraction (D-137) itself.
- D-141/D-142 (2026-09-29): phase 2 piece built — **Mode B frontend-from-scratch scaffolding.**
  `create_standalone_workspace` stays Python-only (lazy, not eager, per D-141); new `tools/frontend_setup.py`
  (`SetupFrontend`, tool name `setup_frontend`, Mode B only — registered via `tools/modeb.py`'s
  `modeb_tools()`, the same conditional-registration path as the Contracts panel tools) lets the model
  scaffold a frontend on demand via the real `npm create vite@latest` (or a free-form `create_command` for
  Angular/anything else), through the normal `run_command` shell/approval gate, then calls
  `detect_node_environment()` on the result and persists `WorkspaceInfo.node_env` — phase 1's React verify
  ladder then applies automatically, no further wiring needed. Idempotency: a second call is rejected
  (`node_env` already set, or the target folder non-empty) rather than clobbering — the model is told to work
  in the existing folder or ask the user first, not silently overwritten. Confirmed, not just assumed:
  redaction/sensitive-terms (`safety/redact.py`'s `flag()`, `ToolContext.sensitive_terms`) apply to every tool
  result at the `agent/loop.py` level regardless of which tool ran, so `setup_frontend`'s output needed no
  special handling. Still open for frontend-from-scratch: no UI-component-library scaffolding beyond whatever
  the chosen create-command's own template provides (e.g. no Tailwind/MUI auto-setup); no monorepo layout
  question arose in practice (frontend just becomes `project/<folder>/` beside the Python code, both under
  the same `project/` root the harness already expects); Angular's own CLI would go through the
  `create_command` escape hatch (untested with a real Angular CLI invocation, only unit-tested with a
  mocked shell call); real npm/network was not exercised (per the task brief, only the shell call is mocked).
- D-143/D-144 (2026-09-29): **Angular support built** (D-137's "Angular" deferred item, Mode A only, same
  scope as phase 1's React work). New `verify/angular_ladder.py` (`AngularVerifyLadder`, `is_angular_project`
  — detects via `angular.json` at the app root), separate from `react_ladder.py` for the same "rungs don't
  decompose the same way" reason that module isn't a `VerifyLadder` subclass. Typecheck now goes through
  `ng build` (with `--configuration=development` when declared) instead of bare `tsc`, since Angular has no
  typecheck-only CLI command and `ng build` is the only path that exercises template type-checking. Test
  framework detection recognises Karma+Jasmine (dependencies or a standalone `karma.conf.js`) and Jest.
  **The load-bearing fix**: a Karma-detected project's test rung always appends `--watch=false
  --browsers=<launcher>` (never runs the bare `test_command`, which would hang forever in `ng test`'s default
  watch-mode-against-a-real-browser) — the launcher prefers a custom name found in the repo's own
  `karma.conf.js` `customLaunchers` block (e.g. `ChromeHeadlessCI`), falling back to `ChromeHeadless`.
  Lint/build confirmed (not assumed) to need no special handling — both are ordinary npm scripts in a
  standard `ng generate` project. `workspace/nodeenv.py` confirmed to need no changes (detection is already
  generic over script names). `verify/ladder.py`'s dispatcher now picks Angular vs. React per-project via
  `is_angular_project()`; a plain React project (no `angular.json`) is regression-tested unaffected. New
  `tests/test_angular_ladder.py` (24 tests, all subprocess calls mocked). Still open, real gaps for a later
  pass if evidence calls for it: Angular's newer esbuild/Vitest-backed test runner and
  `@angular/build:karma`-vs-legacy-builder distinctions aren't builder-aware (only dependency/config-file
  detected); Nx monorepo conventions aren't handled (`is_angular_project` only checks a literal `angular.json`
  at the app root, so an Nx workspace falls through to the React ladder — no worse than before this pass, but
  still wrong); Mode B Angular support (only Mode A is in scope here, matching D-137's original React scoping);
  no real Angular CLI/npm was exercised (mocked throughout, per the task brief).

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
    contract on a later requirement. The **web UI Contracts panel** (built 2026-10-03, D-194; the other half of the D-129 UI
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

- D-145/D-146 (2026-09-29): **Guided first-run setup screen built** — the UI/backend piece of D-145.
  New `config.write_secret_values`, new `doctor.required_secret_names`/`missing_secret_names`, new endpoints
  `GET /api/setup` and `POST /api/setup/secrets`, `GET /api/doctor` gained `?offline=` (default unchanged),
  new `ui-react/src/components/Setup.tsx` shown by `App.tsx` before Home/Chat only when required secrets are
  missing (zero-flash on the already-configured path). No restart needed: confirmed `WebSessionManager` caches
  no `Secrets`/`LLMRouter` before a project is opened, so `load_secrets` re-reading `.env` from disk is already
  sufficient. Tests, ruff, mypy, `npm run build`, `check_secrets.py` all clean — see D-146 for full detail.
  **Done 2026-09-29 (D-147)**: `scripts/run_forge.ps1`, a new sibling script (not a rewrite of
  `install_forge.ps1`, kept separate on purpose — see D-147) — creates/reuses a `.venv` inside the unzipped
  folder itself (no PATH shim, no shared install location, so it can't shadow or be shadowed the way the
  triggering bug happened), installs from the unzipped source (or a bundled wheelhouse if present), and
  launches `forge ui` directly into D-146's setup screen. Actually run end-to-end against this build machine's
  repo, not just written: caught and fixed a real failure (a previous `forge ui` window locking its own
  `forge.exe` during reinstall) with a clear error message instead of a raw pip WinError.

- **RESUMED 2026-10-04 (user sent the office-laptop signatures)** (D-150, started 2026-09-30): **Gemini as a second model provider** (Vertex AI direct SDK,
  `google-genai`, no LangChain — assignable to any role, not just vision). Live-verified on the user's office
  laptop (this dev machine has no GCP credentials): ADC auth, text calls, tool-calling round-trip, streaming,
  image vision, video input, and which models are actually callable on the user's project (`gemini-2.5-pro`,
  `gemini-2.5-flash`, `gemini-2.5-flash-lite`; `2.0-flash`/`2.0-flash-lite`/`3-pro-preview` are 404 — listed
  in Model Garden but not provisioned). See D-150 for the full picture.
  - [x] `config.py`: `GeminiProviderConfig`, `ModelConfig.provider`/`model_name` generalized — done, mid-review.
  - [x] `doctor.required_secret_names`: provider-conditional (Azure vars only if Azure in use, Gemini's
    `project_env`/`location_env` only if Gemini in use) — done, mid-review.
  - [x] `llm/translate_gemini.py`: message/tool-call translation to/from `google-genai` types.
  - [x] `llm/gemini.py`: `GeminiProvider` (implements the same `LLMProvider` protocol as
    `AzureOpenAIProvider`), error mapping (`google.genai.errors` → Forge's `LLMError` subclasses, including
    `DefaultCredentialsError` → a clear ADC-setup `LLMAuthError`), `automatic_function_calling.disable=True`
    set explicitly (Forge's loop must own every tool call, never the SDK).
  - [x] `llm/router.py`: `_create_azure_provider` → a provider-dispatching factory reading `model.provider`.
  - [ ] `doctor.check_models` needs no change (already generic over every model in use) — a Gemini model
    assigned to any role gets the live "reply: ready" startup/connectivity check for free once the router
    can dispatch to it.
  - [x] `.env.example`: document `GOOGLE_CLOUD_PROJECT`/`GOOGLE_CLOUD_LOCATION` names only, no values.
  - [x] Unit tests for the translator (message/tool round-trip, image parts) with no live calls; a
    `@pytest.mark.live` round-trip test gated on ADC being present (skipped otherwise, same pattern as
    Azure's live tests) — can only really be run on the office laptop, not this dev machine.
  - [ ] **Blocked on the user**: `view_video` tool — whether Vertex AI video input goes through the Files
    API (`client.files.upload`, confirmed to exist on the SDK's Vertex client object, but unconfirmed
    whether the backend endpoint actually serves it — Vertex more commonly expects a `gs://` Cloud Storage
    URI instead) or inline bytes (works for small files on any backend, no upload step). Asked the user to
    run a two-path probe on the office laptop; the rest of this milestone doesn't depend on the answer and
    proceeds in parallel.


## Revamp (2026-10-02) — Forge replicates Claude Code (D-151..D-156)
- [x] D-151 run log: `llm_call` events + `forge log-summary`
- [x] D-152/D-154 modules: tiers, MODULE.md per module, boundary test; agent split into agent/subagents/workflow
- [x] D-153 a chat message answers open approval cards; build id in `forge --version` / `forge doctor`
- [x] D-155 no stuck detector or escalation ladder; the model improvises failure recovery
- [x] D-156 docs: spec §0.2 + banners, SPEC_DEVIATIONS, CLAUDE.md, MODULES.md, memory
- [x] D-156 code step 1 (D-158, 2026-10-03): `learning` retired; memory = FORGE.md + auto-memory (typed files + MEMORY.md, user and project scope). The empty Lessons panel was removed from the React UI on 2026-10-03 (D-198)
- [x] D-156 code step 2 (D-159, 2026-10-03): verify ladders, tools, test guard, export smoke check retired; Mode B harness kept (PYTEST_ADDOPTS)
- [x] D-156 code step 3 (D-160, 2026-10-03): `kb` retired; credential-table detection kept in `db`; `/init` now has the model explore and write FORGE.md
- [x] Timeline UI (D-189, D-190, D-192): narration, folded Read/Grep runs, Bash/Edit with output, inline diffs, nested subagents, failures open. The rail was dropped (superseded by the Conversation look).
- [x] Run map (D-193): the D-133 redesign was already built; its two skipped tests are rewritten (`test_web_runmap_e2e.py`) and per-agent cost added
- [ ] MCP review and security design (Mode B) before extending; LSP design
- [x] **DROPPED (D-161)**: role-specific toolsets, lazy tool schemas, prompt fragments. Forge does not optimise token cost at runtime; accuracy and speed first
- [ ] Full test run after the revamp code steps; commit in logical parts
- [ ] D-150 Gemini provider: code + unit tests done (uncommitted); run `scripts/dev/gemini_smoke.py` on the office laptop to verify live

- [x] First Mode B end-to-end campaign (2026-10-03): attendance, bakery, invoice projects; D-162..D-170; report in docs/E2E_CAMPAIGN_2026-10-03.md
- [ ] Next campaign ideas: a project with a database and a REST API (verifier on an API), a CLI tool, a Mode A repo; watch whether the verifier is called on larger features
- [ ] Unattended runs: decide how a headless run may install dependencies (today always-ask)

## Codex comparison gaps (2026-10-03) — spec in docs/SPEC_CODEX_GAPS.md
- [x] G1 Parallel subagents: first test whether concurrent `spawn_subagent` calls already run in parallel; parallel only for read-only agents; cap; subagent id in events
- [x] G2 `pre_compact` / `post_compact` hooks in `HooksConfig`
- [x] G4 Per-agent settings in custom agent files (max_steps, role, write folder)
- [x] G6 `todo_write` tool: lightweight model-kept todo list (no approval), event + UI, survives compaction
- [x] G7 `monitor` tool: wait on a background process for a pattern, exit or timeout (replaces poll loops)
- [ ] G3 Compaction robustness (summariser-failure fallback, image budget) — only if real runs need it
- [ ] G5 Task breakdown — decide only if the campaign shows lost steps (no build under D-155)

## Later, only if real runs need it
- [ ] Parallel pytest in built apps: Forge runs `python -m pytest` sequentially (no xdist, no `-n`). Add a prompt line to use pytest-xdist only for large suites (needs a pip install approval; beware shared ports and SQLite files) once a real project shows slow test runs.
- [ ] Campaign case: Forge builds a small MCP-using tool and tests it with a dummy stdio MCP server it writes itself (needs the `mcp` package via an approved pip install; the server is not wired into Forge's own `config.yaml`). Not yet run live.
- [x] (done 2026-10-03, D-189) UI: Claude Code layout for tool calls in the web chat (user chose option A, 2026-10-03): each call a card in order with the tool name, an IN block (command/path/arguments) and an OUT block, long output collapsed behind "show more" (about 15 lines), edits shown as diffs, failures open, reasoning summaries dim, subagent calls nested and collapsed (D-181). Redaction applies. Check with headless Edge screenshots.

## UI redesign (D-184..D-204, 2026-10-03 / 2026-10-04) — done
- [x] Login, home, project list with memory summary, account screen (change password), Apple-style design on the whole app (D-184..D-197)
- [x] Setup: first-run guide for the `.env` file (path, template, what is filled in), keys never typed into the app (D-204); Environment drawer with a test per
  connection incl. the Forge database and the read-only Development database; model plan to confirm; Tesseract/Gemini asked first (D-186, D-201)
- [x] Chat: welcome, Conversation look, tool-call blocks, diffs, folded read/search runs, nested subagents, todo strip, full tool output (D-188..D-192, D-195)
- [x] Run map tests rewritten and per-agent cost (D-193); Contracts panel (D-194); Learning tab removed (D-198); cleanups (D-199)
- [x] Shell: indirect `.env` reads always ask (D-187); Forge's own variables hidden from commands (D-202)
- [x] Tesseract: the `ocr_image` tool the model can call (D-203)
- [x] Gemini provider built and pushed (D-150, D-205): adapter, router dispatch, drawer real call + (i) steps; project/location optional
- [ ] Gemini: run `scripts/dev/gemini_smoke.py` / the drawer test on the office laptop (never called live here); `view_video` waits for the video probe
- [x] gpt-4o on a second Azure resource as the optional fallback model (D-206), pushed 2026-10-04
- [ ] Optional: Azure AI Vision / Document Intelligence for handwriting OCR (user has no key yet; would need a yes in the drawer)
- [x] Pushed 2026-10-04: the redesign (953e2c5 .. 38c6912, 24 commits) is on origin/main
- [ ] The full test suite takes ~6 min (browser tests); consider splitting browser tests into a marker run if it gets slower
- [ ] `write_secret_values` in config.py is no longer used by the web app; remove it

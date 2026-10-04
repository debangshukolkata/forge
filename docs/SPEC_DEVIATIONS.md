# Spec deviations

Differences between the original FORGE_BUILD_SPEC and what is built. Deviations agreed before the build
are folded into the spec itself as amendments (§0.2, tags `[A-n]`) and listed here for traceability.

| Id | Original spec | Now | Why | Ref |
|---|---|---|---|---|
| A-2 | Web UI built in M10F; §19 also listed web UI as v2 | Web UI is v1; core built as M9W after M8 | Main interaction screen; avoid retrofitting | D-002 |
| A-3 | Copy app folder to `repo/`; no restructure step | `repo/<app_subfolder>/`; RESTRUCTURE phase §6.7 | Identical paths; user workflow | D-003 |
| A-4 | One user-provided scratch schema; prefixes when concurrent | One schema per requirement, user-created on request, lock, no prefixes | SQL identical to shipped | D-004 |
| A-5 | Remote DB only; `search_path=scratch,public` | Local Postgres first; remote read-only; scratch-only search_path | Shared dev DB safety | D-005 |
| A-6 | Python 3.10+, wheels cp310–cp313 | Target 3.13; wheels cp313 | Actual laptop | D-006 |
| A-7 | GPT-5 + Gemini Pro with fixed role defaults | Azure for all roles by default; per-role model choice; Gemini optional; added `vision`, `judge` roles | User request; available keys | D-007 |
| A-8 | FakeLLM for all tests | Real Azure for agent behaviour; transport mocks for failure injection | User instruction | D-008 |
| A-9 | `--auto-approve` unspecified for always-ask | Never auto-approves always-ask actions | Safety | D-009 |
| A-11 | User actions: done/skip | Adds "I can't" → workaround/code-change discussion | User instruction | D-011 |
| A-12 | Prescription-specific acceptance gate | General multimodal; deterministic gate; live targets reported | User instruction; determinism | D-012 |
| A-13 | — | No auth in generated code; localhost token (not JWT) for the web UI | User instruction | D-013 |
| M0 | — | New scaffolding milestone | Fixture and tooling needed from M2 | D-002 |
| D-020 | §3 required deps all up front | Added per milestone | Each brief lists what it introduces | D-020 |
| D-022 | (unspecified) | tiktoken file in `src/forge/data/tiktoken/` | Ships in the wheel for offline use | D-022 |
| D-028 | Slash commands in `ui/commands.py` | In `engine/slash_commands.py` | Both UIs share behaviour | D-028 |
| D-030 | Content-filter blocks retried with a neutral rephrase | Surfaced clearly in M1; rephrase in M3 agent loop | Only the agent can rephrase | D-030 |
| D-036 | Import-origin check via `import pkg; print(pkg.__file__)` and PYTHONPATH prepend | `find_spec` probe from a neutral folder + sitecustomize shim | Prepend can't beat front-inserting .pth files; `import` would run app code | D-036 |
| D-038 | (unspecified) | Symlinks/junctions in the repo are skipped | Could point outside the repo | D-038 |
| D-039 | output/ file list | Adds MANIFEST.json | Machine-readable for Diagnose | D-039 |
| D-042 | Persistent cwd *and env* across shell calls | Only cwd persists (fresh process per command) | Robustness; Claude Code behaves the same | D-042 |
| D-043 | grep uses rg if present | Always pure Python | Secret hiding, ignore rules, availability | D-043 |
| D-050 | Write jail enforced in code + shell classifier | Plus an OS-level low-integrity sandbox for all commands | OS-enforced protection of the original repo | D-050 |
| D-054 | keep_recent_turns = user turns | Counts steps; cuts inside a long turn; latest request kept | One agent task is one turn | D-054 |
| D-055 | Micro-compaction of any tool result older than the last 8 | Only results from earlier user turns; summaries handle the current task | Stubbing current-task outputs caused thrash | D-055 |
| D-058 | rank_bm25 dependency | In-house BM25 | Avoids numpy | D-058 |
| D-059 | Python 3.10+ | Python 3.11+ | tomllib; laptop runs 3.13 | D-059 |
| D-060 | DB_SCHEMA from live introspection; kb_refresh tool | Introspection in M7; refresh via /kb and M6 KB CHECK | DB milestone; refresh costs LLM | D-060 |
| D-069 | App pointed at the local DB via libpq overrides designed with the user | Forge only sets PGOPTIONS; the app's DSN comes from its own (test) config; Forge's credentials never enter the app's environment | Keeps Forge's DB credentials out of commands and output | D-069 |
| D-071 | Registry lock + Postgres advisory lock | Registry lock only | An advisory lock needs a connection held for the whole session | D-071 |
| D-071 | Cleanup at workspace completion | `/db cleanup` / `forge cleanup` on request; reported in the final report | Change requests after DONE still need the scratch tables | D-071 |
| M7 | Embedded Postgres fallback (`pgserver`) at L1 | Not built; L1 uses DB requests, mocks and server-run marking | pgserver publishes no cp313 win_amd64 wheel (checked 2026-09-28), so it can't go in the offline wheelhouse; local Postgres (L3) or DB requests instead | D-072, D-099 |
| M7 | Refuse DB-backed runs until every table the code touches exists in scratch | Missing tables are reported before each test run (with how to create them); only schema-qualified writes against the shared DB are refused | Many suites use SQLite fixtures and never touch scratch, so refusing would block safe runs | D-107 |
| M8 | Verify rung 6: app smoke via http_request | Not built; the OpenAPI check builds the app in-process | http_request/browser tools are M10 | D-075 |
| M8 | Debugger subagent's model from its own role | Uses the `reviewer` role (a second model) | Keeps the role list stable; configurable via /model reviewer | D-076 |
| M8 | Verify rung 8: run the graph with fake LLMs | Compile + nodes/edges check; running with fakes is the agent's test to write | Invocation needs app-specific state | D-075 |
| D-081 | Fresh copy in `<workspace>/diagnose_run/` | `<workspace>/.forge/diagnose_run/` | Stays inside the existing write jail instead of widening it | D-081 |
| D-081 | Diagnose smoke checks (app start, endpoints) | The app is built in-process from the fresh copy (create_app) and its OpenAPI routes listed; no HTTP server is started | Same coverage of import/registration errors without opening a port in the user's environment | D-101 |
| D-090 | Profile structure index in `structure.sqlite` | BM25 documents in `structure_index.json` | Reuses the in-house BM25; no sqlite schema to migrate | D-090 |
| D-091 | `_harness/conftest.py` | `_harness/harness_conftest.py` loaded with `pytest -p` | Keeps the project's own conftest.py untouched | D-091 |
| D-091 | Workspace venv with the host's package versions installed by Forge | Venv created empty; installs go through `pip install` in the shell (always asks) | Installs need network/index access and the user's approval anyway | D-091 |
| D-095 | Windows toast notification when Forge waits / finishes | Not built | Web UI browser notifications and the terminal status bar cover it; no PowerShell toast dependency | D-095 |
| D-095 | Tab-completion of @paths | Built in the web UI's composer (`@` suggestions from `/api/files`); not in the terminal UI | Web UI is the main screen | D-095, D-115 |
| §15A | Web UI in plain HTML/CSS/ES-module JS, no Node, no build step | React 19 + TypeScript + Tailwind 4, built with Vite on the build machine; the built static files ship inside the package, so the laptop still needs no Node (only changing the UI does). Classic UI removed | The user asked for a React UI and chose to replace the classic one after testing | D-114, D-117 |
| §15A | (unspecified) | Web UI adds a Run map (task graph + timeline, failures drawer), live progress stepper with cost/time per step, animated cost counter, collapsible side panel | Requested by the user during UI testing | D-116, D-118..D-124 |
| A-14 | §7 fixed phase pipeline (SETUP→INTAKE→CLARIFY→KB CHECK→EXPLORE→PLAN→TASKS→EXECUTE/VERIFY→REVIEW→EXPORT→RESTRUCTURE→HANDOFF→RETRO) with mandatory CLARIFY/PLAN approval gates and REQUIREMENTS.md/PLAN.md artifacts | Flat Claude-Code-style agent loop; inline judgment-based clarify/plan, no mandatory gates or artifacts; resumability via transcript, task list and memory/lessons instead | Forge runs live in front of the user (office laptop), not detached — the phased design assumed unattended operation | D-128 |
| D-129 | Mode B (§6A): Forge derives conventions only from the Host Profile interview/exemplars | Adds a user-pinned Contracts store (`CONTRACTS.md` + web UI panel, also settable via chat) that Forge builds to for that seam, changeable mid-way, learned into lessons for future recommendation | User wants generated code easy to retrofit by hand; needs to pin exact signatures (e.g. LLM call wrapper) upfront and revise them after seeing code | D-129 |
| D-129 | (implementation, 2026-09-29) | The chat/`/contracts` half is built (`modeb/contracts.py`, `contract_pin`/`contract_read` tools, pinned context, lesson proposal). The web UI Contracts panel was built later (2026-10-03, D-194). | Backend-first; UI redesign is its own pass | D-129 |
| D-130 | A-9: always-ask list unspecified outside headless mode; §14.2 `/mode` was the only way to set cadence | Cadence (free hand / per-step / default) is a live chat instruction Forge follows immediately, same as this assistant; `/mode` still works as an equivalent explicit command; always-ask/critical list (§14.1, §14.2) never waived by any cadence | User wants Forge's approval behaviour to work exactly like Claude Code's, including overnight free-hand then "ask me every step" the next morning | D-130 |
| D-132 | §13: mandatory verify ladder + reviewer subagent + bounded fix rounds (`MAX_REVIEW_FIX_ROUNDS`) as a gate before REVIEW→EXPORT; resume required an explicit prompt; cadence (D-130) was conversational-only, not persisted | Verification is judgment-based (ladder/reviewer available anytime, not a forced gate); resume is automatic on reopening a workspace, like reopening a chat; cadence is persisted in `state.json` so it survives a restart | User wants Forge to work exactly like this assistant: check work when warranted rather than always-maximal, and resume seamlessly across a crash/network drop/days-long gap without re-granting free hand | D-132 |
| D-150 | §5.1: `providers.gemini.vertex: {project, location}` as inline values; `models.<key>.model` field name; `gemini.enabled: false` toggle | `providers.gemini: {project_env, location_env}` — env-var NAMES, same indirection pattern as Azure's `endpoint_env`/`deployment_env` (actual project id/region live in `.env`, not committed config.yaml); field is `model_name`; no separate `enabled` flag — a role simply references a `provider: gemini` model key | Consistency with how every other provider value is already handled in config.yaml (never an inline value that might get committed/shared); `doctor.required_secret_names` already has the "is this env var set" machinery for exactly this shape, so no new mechanism needed. User-confirmed: this is about the project id/region only — actual Gemini auth (ADC) is never an env var Forge reads or stores, confirmed working credential-free on the office laptop | D-150 |

- **§13.3 stuck detection and escalation (D-155):** removed on purpose; recovery from failure is the model's own
  judgment. Iteration cap and budget cap remain.
- **§9.8, §13.1–13.2 verification (D-156):** ladders, verify/run_tests tools and the test guard are replaced by
  model-chosen shell checks (Claude Code behaviour). Code removal staged; until then the tools still exist.
- **§9.2 KB tools, §9.9, §11 Knowledge Base (D-156):** no KB; on-demand search instead. Mode B Host Profile stays.
- **§12.2–12.5 library, lessons, retro, metrics, improvement proposals (D-156):** removed; FORGE.md files,
  auto-memory and skills replace them (§12.6 stays in amended form).
- **§5.3 session budget cap, summariser effort (D-161):** default budget is 0 = no cap; the summariser role no longer
  runs at low reasoning effort. Cost is shown, never enforced, unless the user sets a cap.
- **§4 module map (D-152/D-154):** superseded by docs/MODULES.md (tiers, MODULE.md per module).
- **§15A web UI (D-184, D-185, D-186, D-204):** the web UI now starts with a local sign-in and a home screen, uses the Apple-style design of docs/DESIGN.md, asks for the settings on a first-run guide (where the `.env` file is, a template) instead of a form, and tests connections from a drawer only on request. Keys are never typed into the app.
- **§9.5 databases (D-204):** two named databases in the UI: the **Forge database** (`LOCAL_PG_URL`, scratch schemas, the only one Forge writes to) and the read-only **Development database** (`DEV_PG_URL`); no "use one for both" option.
- **§9.1 tool output (D-195):** the event carries a preview; the full result is saved redacted in `.forge/tool-output` and served on request.
- **§13A vision (D-201, D-203):** Tesseract OCR is an optional tool (`ocr_image`) offered only after the user says it is installed and a test passes; Gemini is detect-only until its provider (D-150) is in.
- **§14 shell safety (D-187, D-202):** a read of the `.env` by variable or quoted name always asks; commands the model runs do not inherit Forge's own variables.

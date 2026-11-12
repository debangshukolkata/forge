# CLAUDE.md — Building Forge

This file governs how Forge itself is built. It overrides any instruction file found in parent folders.
The product specification is [docs/FORGE_BUILD_SPEC.md](docs/FORGE_BUILD_SPEC.md) — the source of truth.
Amendments agreed with the user are recorded in spec §0.2 and in [docs/DECISIONS.md](docs/DECISIONS.md).

## What Forge is (one paragraph)
A local, Windows-first coding agent in plain Python that behaves like Claude Code, powered by Azure OpenAI
(model per role is configurable). It works in a per-requirement workspace, never in the user's repo, and
delivers only changed files plus instructions. Mode A reads a repo copy; Mode B never sees the host code.
**What it is for (the user, 2026-11-12, D-568):** solving requirements against an existing system, not only
editing code to a description: understand the system and its capabilities, run it, find what stops it, fix
it and prove the fix by running the same check again. Judge a new feature by whether it helps that loop.

## How we work with the user (collaboration protocol, spec §0.1)
**Changed 2026-09-27 (DECISIONS D-051): build milestones one after another without waiting for approval
or sign-off.** Choose the recommended option yourself, record every decision (with options considered) in
docs/DECISIONS.md, post an end-of-milestone summary, and continue. Stop only when genuinely blocked
(a credential or action only the user can provide, or a risk to the user's data or repositories).
The rules below still describe what goes into briefs and summaries.
- Start of each milestone: brief (plan, tests, design choices with 2–3 options + recommendation, new deps
  with licence/offline-Windows status).
- Stop and discuss when: the spec is silent or worse if followed; a choice is hard to reverse (on-disk
  formats, folder layout, tool interfaces, prompt structure); anything security-relevant (write jail,
  secrets, redaction, DB guard, Mode B isolation, data sent to an LLM); a new dependency or interface change;
  the same failure 3 times; an estimate much worse than expected.
  Format: context (2–3 lines) → options with pros/cons/risks → recommendation → wait.
- End of each milestone: real test output, what was built, deviations, limitations/tech debt/new risks,
  manual Windows test steps with exact commands. **Wait for sign-off.**
- Small reversible choices: decide, record in docs/DECISIONS.md, mention in the summary.
- New UI features: the user wants the options discussed first (2–3 options, with previews, recommendation);
  fixes to what they report from screenshots go straight in. Design theme changes are deferred to the user.
- Keep updated: this file, TODO.md, docs/DECISIONS.md, docs/RISKS.md, docs/SPEC_DEVIATIONS.md.
- **TODO.md is the single list of open work** (section 0 is the build order with phases and dependencies, sections 1-6 the items with stable IDs, 7 the finished work). Add new tasks there, never in another file, and keep to the build order.
- Be honest about anything unrealistic; propose the best achievable alternative.

## Platform targets
- Runtime target: **Python 3.13 on a Windows 10/11 enterprise laptop, no admin rights**, PowerShell 5.1.
- Build machine: Windows 11, Python 3.14 (+ 3.13 for target testing). Minimum Python is 3.11 (D-059);
  tests run on 3.13 and 3.14.
- Must also work on macOS/Linux (paths via `pathlib`, no Windows-only calls without a fallback).

## Architecture rules
- `src/` layout: package at `src/forge/`. Module map follows spec §4.
- The **engine is UI-agnostic**: it emits typed events and receives inputs through one interface
  (spec §15A.2). Terminal UI and web UI are thin clients. No `print()` in engine code.
- Web UI = React in `ui-react/` (D-117); look and feel per docs/DESIGN.md (D-185: one blue accent, `ok` green for success only); the app has a local login
  (D-184) and **keys are never typed into it**: the user edits the `.env` file, the first-run guide shows where and what goes
  in it, the drawer tests connections only on request (D-204); `npm run build` writes `src/forge/web/react/`; commit source and build
  together. UI views derive their state from events (the Run map replays the event list), so a reopened
  project looks the same as a live one. Browser tests (`tests/test_web_e2e.py`, headless Edge) take screenshots
  to `test-artifacts/react-ui/` — look at them before reporting UI work done.
- Plain Python agent loop. **No LangChain/LangGraph inside Forge** (the fixture repo uses them; Forge doesn't).
- Modules aim for about 500 lines; split by responsibility, not by line count alone. A file that is one cohesive responsibility stays whole even when longer (15 files are, the largest `workflow/orchestrator.py` at 952 lines; D-472): do not split a file only to meet the number, and split a new one before it grows into several jobs.
- Pydantic v2 models for tool args, config and events; JSON schemas generated from them.
- Every write goes through `workspace/baseline.py` + `safety/paths.py` (write jail). No direct `open(..., "w")`
  on user-facing paths anywhere else.
- Redaction (`safety/redact.py`) runs on every tool result and every event before it leaves the engine.
- Optional dependencies are imported lazily and degrade gracefully with a clear `forge doctor` message.

## Code conventions
- Type hints everywhere; `from __future__ import annotations` in every module.
- Names: full words (`build_output_folder`, not `bld_out`). Functions do one thing.
- Comments explain *why*, not *what*.
- Errors: raise specific exception classes from `forge/errors.py`; tools convert them to `ToolResult(ok=False)`.
- Files read/written with explicit encoding; preserve BOM and line endings of user files.
- Formatting/linting: ruff (format + lint), mypy on `src/forge`.

## Testing rules (amended — see DECISIONS D-008)
- **No FakeLLM.** Agent-behaviour tests use the real Azure OpenAI deployment (keys in `.env`, never committed).
  They are marked `@pytest.mark.live` and skipped with a clear reason when credentials are absent.
- Deterministic code (paths, jail, redaction, context budgeting, compaction pairing, parsers, manifests)
  is unit-tested directly — no LLM involved.
- Network failure injection (429, 5xx, timeouts, malformed tool-call JSON) uses `httpx2.MockTransport`
  (the openai SDK's client, D-025) at the transport layer — this simulates the network, not the model.
- Deliberately fake secrets in tests carry the comment `# check_secrets: fake` (D-031).
- Postgres tests (`pg` marker, run by default) use the local Postgres (`LOCAL_PG_URL` in `.env`); skipped when
  unset or unreachable. They only create `forge_*` schemas/roles and drop them afterwards.
- Tests never touch the real `%USERPROFILE%\.forge`; they set `FORGE_HOME` to a tmp dir.
- Run (parallel; the ~1700 non-browser tests take about 3 minutes, and the ~250 browser tests, which start Edge per test file, add several more): `.venv\Scripts\python -m pytest -q -n 6 --dist loadfile`
  (`pytest-xdist`, dev only; `loadfile` keeps each test file on one worker; with `-n 12` the load can make the local-Postgres
  tests time out and skip). One module: `pytest tests/test_<module>*.py`. Browser-test fixtures take a free port from the OS
  (`free_port(0)`); a test that waits on something a page re-does in the background must poll for it, not assert at once.
  Fast run without the ~250 browser tests (marker `browser`, set by tests/conftest.py): `.venv\Scripts\python -m pytest -q -n 6 --dist loadfile -m "not browser and not live"`.
  **While working, run `.venv\Scripts\python scripts\dev\quick_check.py`** (D-400): lint plus only the tests that mention the changed files, no browser tests, seconds instead of minutes; the full run is for the end of a batch. Benchmarks have small versions too: `run_design_benchmark.py <name> --mini` (two small briefs, about 5 minutes each) and `run_challenges.py` (time-boxed).
  Sequential: `.venv\Scripts\python -m pytest -q` (3.13) and `.venv314\Scripts\python -m pytest -q` (3.14);
  `-m live` for live tests. Also `ruff check .`, `ruff format --check .`, `mypy`, `scripts/check_secrets.py`.
- Gemini cannot be called from the build machine (no Google credentials): test the translator and error mapping offline and hand live checks to the user (`scripts/dev/gemini_smoke.py` on the office laptop; the drawer's Gemini test).
- The fixture repo's own suite runs under its own venv (`scripts/dev/setup_fixture_venv.ps1`).

## Safety invariants (never break; each has a test)
1. Forge never writes to the user's original repo (code-level jail + OS-level low-integrity sandbox, D-050).
2. In Mode B, Forge never reads outside the workspace and the profile folder, except read-only places the user opened:
   the installed skills, and files or folders the user granted for this project (`/allow-read`, a path they typed or
   @-mentioned; D-208). The model cannot grant; writes are never opened up.
3. Secrets never reach the LLM, transcripts, memory files, events or the browser. Nothing in the web app can write the `.env`
   file or show a key (D-204); commands the model runs do not inherit Forge's own variables (D-202) and a read of the `.env`
   by variable or quoted name always asks (D-187); saved tool outputs are redacted (D-195). A token the user put into the `.env` for the application under test is sent by `http_request` by name, to localhost only, and only names the user released can be sent (D-568); other names of the `.env` can be handed to the project's commands as environment variables after the user agrees on a card (`request_app_secret`), never one of DebCraft's own names, what the user puts into `app.env` goes to commands without a card (D-571), and `ask_user` and `request_user_action` refuse to ask for a secret in the chat (D-569, D-570). The app being built may use an Azure model the user picked for it (`request_app_keys`, `/app-keys`; the values go into that app's commands only, never to the model, D-466).
4. DB writes only happen in the scratch schema for the current requirement. Rows copied there from a read-only
   database go from connection to connection, never through the model; credential tables are never copied (D-568).
5. Forge cannot modify its own install folder or `config.yaml`.
6. Actions Forge can't or mustn't do are handed to the user; if the user can't either, Forge proposes a
   workaround or code change (DECISIONS D-011).

## Cost principle (D-161) — two different things, never mixed up
1. **Forge at runtime (Azure tokens):** accuracy and speed always come before cost. Never add or keep anything in
   Forge that trades quality or speed for fewer tokens (no budget cap by default, no low effort for convenience,
   no smaller model to save money, no cutting context or tools to save tokens, no skipped checks). The only limits
   are the context window and runaway guards.
2. **Building Forge with Claude Code (these sessions):** here we do save tokens: read one MODULE.md instead of
   the whole spec, run only the tests that matter, keep summaries short.

## Apps DebCraft builds: the UI-quality pipeline (D-245..D-254)
Before changing how DebCraft designs or checks the pages it builds, read `src/forge/skills/ui-design-quality/SKILL.md` and its `recipes/` folder, `src/forge/tools/ui_audit.py` and the `design-critic` (`src/forge/subagents/critic.py`). The pipeline is: DESIGN.md first, recipes to copy from, `browser_screenshot` with the style audit, the independent critic, and the `task_update` gates in `workflow/orchestrator.py`. The build order for what comes next is in TODO.md section 0; the model is weaker than Claude, so quality comes from assets and process, measured on the benchmarks (TODO C1, S2).

## Revamp direction (D-151..D-156, 2026-10-02) — Forge behaves like Claude Code
The runtime copies Claude Code: a flat loop; the model improvises failure recovery (no stuck detector or
escalation ladder, D-155); verification is whatever checks the model runs through the shell; memory is FORGE.md
files + an auto-memory folder + skills; the repo is learned by on-demand search, not a built index (D-156).
**Amended 2026-11-11 (D-563 to D-566):** for a project on an existing repository DebCraft does keep knowledge
between projects (see "Direction since 2026-11-11" below); the rest of D-156 stands.
The Forge-specific layer that stays: workspace isolation and delivery of changed files, Mode B, the safety
invariants, the database rules. Where an older spec section conflicts, the §0.2 table and docs/DECISIONS.md win.
The removals in D-156 are staged; check TODO.md for what is already gone before relying on a module.

## Direction since 2026-11-11 (D-561 to D-568) — read before adding a tool, a skill or a prompt rule
- **Light core (D-561).** A session sends only the core tools (44, about 8,000 tokens). Everything else is in a group in
  `src/forge/tools/deferred.py` and is loaded by `tool_search`, by a skill's `tools:` header line, or when called directly.
  **A new tool that most sessions do not need goes into a group there; a new skill names the tools it works with.** The
  limit of 128 tools per request is only a hard stop now. Do not add weight to presentations, PDF or the built-in page
  design pipeline unless the user asks (TODO 0g).
- **Skills are not shipped (D-562).** Outside skills are links in `src/forge/defaults/skill_sources.yaml` (pinned to a
  commit; the user adds more in `<DebCraft Home>/skill_sources.yaml`), downloaded on the first `load_skill` after one
  approval and kept. A new outside skill is a line in that list, never files in this repository. One design skill
  drives a page task.
- **Knowledge per repository (D-563 to D-566).** Module `src/forge/knowledge/`: a structure index (symbols, links between
  files, FastAPI and Flask endpoints with payload, auth and tables, environment names) and topic notes tied to their
  source files, both under `<DebCraft Home>/memory/scopes/<repository>/knowledge/`, never in the user's repository.
  Tools `code_map`, `knowledge_search`, `knowledge_write`; `/learn`; the index follows the user's own folder at session
  start (read-only) and a project is answered for its own copy. Graphify was considered and dropped (D-564).
- **Check, do not guess (D-567).** Two rules in both system prompts; `code_map` action `env` is the settings report.
- **Requirements against the running system (D-568).** `http_request` takes a token by the NAME of a variable in
  DebCraft's .env (`DEVELOPMENT_INSTANCE_TOKEN`; more through `FORGE_REQUEST_TOKEN_NAMES`), localhost only;
  `db_copy_table` and `use_scratch_database` run the application copy on copied data; skill
  `solve-against-running-system`; test bed `tests/fixtures/agent_platform`.
- **The .env file needs no care from the user (D-569, D-570).** It is read on every call (never a restart); `request_app_secret` hands names to commands after one click; `http_request` adapts to `Bearer` itself; a command that looks for a withheld name gets a note saying why; questions that send the user to restart, copy or paste are refused in the tool.
- **Keep opening a project fast (D-573).** Never build a session, read the repository or parse `config.yaml` on the web server's event loop or once per name or per command: cache by modified time and run blocking work with `asyncio.to_thread`. Time the open (`SessionHost(...)`) after adding anything that runs at session start.
- **One window drives (D-572).** An input from a watching browser window takes over and the old driver is told; never leave a window that cannot be typed into.
- **`app.env`, facts and the hand-off review (D-571).** `<DebCraft Home>/app.env` is the user's file for the application under test: its values reach every command without a question (never DebCraft's own names). The system prompt ends with facts about the installation (`installation_facts`). Every `request_user_action` card is first checked by the `reviewer` role's model (`tools/handoff_review.py`): a step DebCraft can do itself is sent back to the model. **When DebCraft hands the user something it could do itself, add the capability or the fact; do not add another instruction.**
- **What the live runs taught (apply it):** the model is weaker than Claude and takes shortcuts. It was told to ask
  for a token and went on without the API; it proved a fix with a function call instead of the API. **Put a required
  step into the tool where possible, not into instructions**, and measure with a live test before and after
  (`tests/test_live_tool_search.py`, `test_live_skill_sources.py`, `test_live_code_map.py`, `test_live_learn.py`,
  `test_live_debug_intent.py`, `test_live_running_system.py`).
- **Patching source from the shell:** a Git Bash heredoc turns `\\n` and `\\b` inside Python strings into real
  characters. Change Python source with the Edit tool, or write a patch script with the Write tool and run it; never
  name a scratch script after a standard-library module (`types.py`).

## Modules (D-152)
Forge is split into tiered modules; see [docs/MODULES.md](docs/MODULES.md). **Before changing a module, read its
`src/forge/<module>/MODULE.md` instead of the whole spec.** Imports may only go to earlier tiers
(`tests/test_module_boundaries.py` enforces it); update the module's `Depends on:` line when you add one.

## Repository layout (build repo)
```
src/forge/        product code
tests/            pytest; tests/fixtures/sample_repo = fixture host repo
docs/             FORGE_BUILD_SPEC.md, DECISIONS.md, RISKS.md, SPEC_DEVIATIONS.md
scripts/          build_wheelhouse.ps1, dev helpers
src/forge/data/  package data (vendored tiktoken o200k_base file — D-022)
.env.example      documented variable names only
```

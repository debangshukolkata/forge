# Decisions

Every decision with the options considered. Status: **Agreed** (user approved), **Proposed** (awaiting
the user), **Decided** (small, reversible — made by Claude, reported in the milestone summary).

---

### D-001 — Instruction files · Agreed (2026-09-26)
Forge has its own `CLAUDE.md` in the Forge folder. The parent `c:\Work\Projects\CLAUDE.md` (a React
frontend spec) was removed by the user and does not apply. → Spec A-1.

### D-002 — Web UI is v1; milestone order · Agreed (2026-09-26)
Options: (a) web UI last (spec M10F); (b) web UI core right after M8; (c) web UI from M1.
Chosen: **(b)**. The engine event bus exists from M1, so the UI is a thin client; building its shell after
M8 lets every later milestone add its own screens instead of retrofitting them all at the end. (c) would
churn the UI while the engine interfaces are still moving.
Order: M0 → M1 → … → M8 → M9W (web UI core) → M9 (Diagnose) → M10 → M10B → M10C → M10E → M10D → M11.
Also: add M0 (scaffolding); build redaction + write jail in M2 and a basic shell classifier in M3 rather
than in M11. → Spec A-2, §17.

### D-003 — Output paths and restructure · Agreed (2026-09-26)
Options: (a) copy the app folder to `repo/` (paths relative to the app folder); (b) copy to
`repo/<app_subfolder>/` (paths relative to the repo root).
Chosen: **(b)**, so output paths are literally identical to the real repo.
User addition: after code is developed and tested, the user may instruct Forge to restructure the code
to fit the repo, keeping behaviour intact. New phase RESTRUCTURE and spec §6.7 (behaviour-equivalence
checked by re-running tests, smoke and OpenAPI before/after). → Spec A-3.

### D-004 — Scratch schema per requirement · Agreed (2026-09-26)
Options: (a) one user-provided schema shared by all workspaces with table prefixes when concurrent;
(b) one schema per requirement, created by the user on Forge's request, with a lock.
Chosen: **(b)**. No prefixes, so SQL stays identical to what ships. Forge may create the schema itself
only if its role is allowed and the user approves (typical on the local DB). → Spec A-4.

### D-005 — Database targets · Agreed (2026-09-26)
The remote dev DB is **shared**. Options for DB-backed tests: (a) remote scratch schema with
`search_path=scratch,public`; (b) remote scratch with `search_path=scratch` only; (c) local Postgres.
Chosen: **(c) local first, (b) as fallback**; the remote DB is otherwise read-only. (a) is rejected:
unqualified names for tables not cloned into scratch would resolve to real `public` tables, and the app
connects with its own (write-capable) credentials, which Forge's SQL guard cannot see.
Open for M7: how to point the app (incl. its config-table bootstrap) at the local DB. → Spec A-5.

### D-006 — Python version · Agreed (2026-09-26)
Target laptop: Python 3.13. Build machine: 3.14 + 3.13.15 (installed per-user via winget, 2026-09-26).
Forge code keeps 3.10-compatible syntax; the suite runs on 3.13 (primary) and 3.14. Wheelhouse: cp313 win_amd64. → A-6.

### D-007 — Models per role; providers · Agreed (2026-09-26)
User request: choose the model for coder, KB builder, reviewer, summariser, etc. Roles: coder, kb_builder,
reviewer, summariser, vision, judge, fallback — set in config, `/model <role> <model>`, and web UI
settings. Default: the Azure OpenAI deployment for all roles. Gemini adapter optional, built when keys
exist. Azure API: Responses API default, Chat Completions fallback. Model names only in config. → A-7.

### D-008 — Testing without a FakeLLM · Agreed (2026-09-26)
User instruction: don't use a fake LLM; use the real Azure key (Orchestrix's).
Interpretation (user asked for a leak check on top — see D-016):
- Agent-behaviour tests run against real Azure, marked `live`.
- Deterministic logic (jail, redaction, context budgeting, compaction pairing, manifests, parsers) is
  tested directly — there is no LLM in those tests at all.
- Failure injection (429 + `Retry-After`, 5xx, timeouts, malformed tool-call JSON) uses
  `httpx.MockTransport`: these conditions can't be triggered on demand against the real service.
- The §10.7 500-call stress test feeds synthetic history through the context manager (no LLM), plus one
  live run with a small configured window.
Consequences: live tests cost money, take minutes, and aren't deterministic — acceptance is judged on
outcomes and run at least twice. → A-8.

### D-009 — Headless auto-approve · Agreed (2026-09-26)
`--auto-approve` never covers the always-ask list; Forge asks the user to confirm or to run the step, or
marks the task blocked. → A-9.

### D-010 — Workspace git and secrets · Agreed (2026-09-26)
The workspace `.gitignore` excludes secret files. → A-10.

### D-011 — Access fallback chain · Agreed (2026-09-26)
User instruction: wherever Forge can't run something due to access, it asks the user to run it; if the
user doesn't have access either, a workaround or code change is needed. Implemented as an "I can't"
answer on user-action and DB-request cards, which opens a design-fork discussion. → A-11.

### D-012 — Multimodal is general · Agreed (2026-09-26)
The prescription task is one reference example. M10D gates on deterministic components; live accuracy
targets are reported, and a second, different document task is run. → A-12.

### D-013 — No JWT · Agreed (2026-09-26)
Generated code never implements authentication; it reuses the host's existing JWT decorators.
Forge's own web UI: user allowed JWT since frontend and backend are always local. Options: (a) JWT
(PyJWT dependency, signing key to manage, expiry/refresh logic); (b) a random per-launch session token
(`secrets.token_urlsafe`, stdlib). Both only need to stop *other web pages in the same browser* from
driving Forge (DNS rebinding / CSRF) — there's no second user or separate issuer, so JWT's signed claims
add nothing. Chosen: **(b)** — simpler, no dependency. Revisit if Forge ever becomes multi-user.
→ A-13.

### D-014 — Model names configurable · Agreed (2026-09-26)
No model names or context windows in code; all in config, verified by `forge doctor`.

### D-015 — tiktoken offline · Decided (2026-09-26)
tiktoken downloads `o200k_base` on first use, which fails offline. Vendor the file under `vendor/` and
set `TIKTOKEN_CACHE_DIR` at startup.

### D-016 — Secret-leak checks · Agreed (2026-09-26)
User asked for a check that the Azure key is never leaked. Layers:
1. `.gitignore` excludes `.env*` (except `.env.example`) — done.
2. Value-based redaction: every secret loaded from `.env` (and any `*_KEY`, `*_SECRET`, `*_PASSWORD`,
   `*_TOKEN`, `*_URL` with credentials) is registered with `safety/redact.py` at startup, so its exact
   value is masked in tool output, events, transcripts, logs and LLM requests — on top of pattern rules.
3. Canary test: live tests inject a fake canary secret and assert it never appears in the event log,
   transcripts, tool outputs, compaction summaries or the outbound LLM request bodies.
4. `scripts/check_secrets.py`: scans the repo and Forge Home for the real values from `.env` (compared
   in memory, never printed) plus key/JWT/connection-string patterns; run at every milestone end and in
   the test suite. Fails loudly with file:line only.
5. `forge doctor` never prints secret values (presence and length only).

### D-017 — Forge's internal storage · Agreed (2026-09-26)
User asked whether Forge needs a DB for internal use. Answer: no server DB. Forge's state is files in
folders (Markdown/JSON/JSONL, human-readable, resumable) plus embedded SQLite files (stdlib `sqlite3`,
no server, no install) only where search/indexing is needed: KB `index.sqlite`, library `index.sqlite`,
`lessons.sqlite`, Mode B `structure.sqlite`. Postgres is used only to test the code Forge generates.

### D-018 — Local dev database · Decided (2026-09-26)
Created database `forge_dev` on the local PostgreSQL 18 (`localhost:5432`, user `postgres`). URL in
`.env` as `LOCAL_PG_URL` / `FORGE_PG_URL`. Tests create and drop only their own schemas inside it.

### D-019 — Azure credentials source · Agreed (2026-09-26)
User chose option B (copy from Orchestrix's DB). The auto-mode safety classifier blocked Claude from
running the extraction, so the user runs `scripts/dev/import_orchestrix_azure.py` themselves (it prints
only presence/lengths/host). The user ran it on 2026-09-26; values are in `.env`.
**Verified live (2026-09-26):** the deployment serves **`gpt-4.1-2025-04-14`**, not GPT-5. The stored
API version `2023-08-01-preview` supports Chat Completions only; the Responses API (incl. function
calls) works with `2025-04-01-preview`. GPT-4.1 has no `reasoning_effort`; context ~1M, max output 32k.
Config values per model are settled in the M1 brief; GPT-5 remains the target for the office laptop.

### D-020 — Runtime dependencies added per milestone · Decided (2026-09-26, M0)
Spec §3 lists fastapi, uvicorn, pathspec, rank_bm25 etc. as required. They are added to `pyproject.toml`
in the milestone that first uses them (fastapi/uvicorn in M9W, pathspec in M2, rank_bm25 in M5), so each
milestone's brief lists exactly what it introduces. M0/M1 set: openai, tiktoken, httpx, pydantic, pyyaml,
python-dotenv, rich, prompt_toolkit, psutil.

### D-021 — Fixture repo design · Decided (2026-09-26, M0)
`tests/fixtures/sample_repo` is a monorepo (`backend/` + placeholder `frontend/`). The backend is a claims
API: app factory; class-based view (MethodView) and function-route flask-smorest blueprints; marshmallow schemas; a
service layer; raw-SQL repository (`text()`) *and* an ORM repository; SQLAlchemy models; numbered
`sql/V00n__*.sql` scripts with rollback comments; a bootstrap that exports `DB_*` env vars from the
`app_config` table; a LangGraph triage graph with conditional routing; JWT auth decorator (host-style,
per A-13); fake `.env`. Its tests use LangChain's `FakeListChatModel` — that is host-app code (spec §13.1
step 5), not a Forge test, so it doesn't conflict with D-008. Versions pinned in `requirements.txt`
(Flask 3.1.3, flask-smorest 0.47.0, marshmallow 4.3.1, SQLAlchemy 2.1.1, psycopg 3.3.6, PyJWT 2.15.0,
langgraph 1.2.12, langchain-core 1.6.5). Its venv lives at `backend/venv`, built by
`scripts/dev/setup_fixture_venv.ps1`, like a real host app.

### D-022 — Vendored tiktoken location · Decided (2026-09-26, M0)
Options: repo-level `vendor/` vs inside the package. Chosen: `src/forge/data/tiktoken/` (package data), so
the file ships inside the wheel and the offline laptop needs nothing extra. File name is tiktoken's cache
key (SHA-1 of the source URL); tiktoken 0.14.0 verifies its content hash on load. 3.6 MB. MIT licence
(tiktoken).

### D-023 — Test environments · Decided (2026-09-26, M0)
`.venv` = Python 3.13 (primary, matches the target laptop); `.venv314` = Python 3.14 (secondary). Both
run the full suite at milestone end.

### D-024 — Available models on the dev Azure resource · Decided (2026-09-26)
Listed via the deployments API with the existing key. Chat: `aicloud-gpt-4o` → **gpt-5.1** (Responses API,
`reasoning_effort`, strict function calls verified) and `aicloud-gpt-4` → **gpt-4.1**. Embeddings:
`text-embedding-3-large` (3072 dims) on the same resource. The separately supplied `ai-openai-engg`
embeddings key is rejected (401) on both endpoints, so `.env` uses the main resource instead.
`.env`: `AZURE_OPENAI_DEPLOYMENT=aicloud-gpt-4o` (primary), `AZURE_OPENAI_SECONDARY_DEPLOYMENT=aicloud-gpt-4`.
Proposed role defaults for M1: coder, kb_builder, summariser (low effort), vision → gpt-5.1; reviewer and
judge → gpt-4.1 (a different model catches different mistakes — spec §5.2 rationale); fallback → gpt-4.1.
Note: deployment names don't match the models they serve, so Forge must never infer a model from a
deployment name — `forge doctor` reports the served model.

### D-025 — The openai SDK's HTTP client is `httpx2` · Decided (2026-09-26, M1)
openai 3.x depends on `httpx2` (a maintained fork of httpx) and only accepts `httpx2.AsyncClient`.
The Azure adapter's injectable `http_client` is therefore an `httpx2.AsyncClient`, and transport-level
failure tests use `httpx2.MockTransport`. Forge's own HTTP needs (web fetch, later) keep using `httpx`.

### D-026 — Served model comes from Azure, not from responses · Decided (2026-09-26, M1)
Found live: the Responses API echoes the *deployment name* as `model` ("aicloud-gpt-4o"), while Chat
Completions reports the real model. The adapter now asks Azure's deployment-info route
(`GET /openai/deployments/{name}`, api-version 2022-12-01) once per deployment when a response only
names the deployment. `forge doctor` reports OK only if that served model matches the configured label.

### D-027 — Live tests excluded from the default run · Decided (2026-09-26, M1)
`pytest` runs the offline suite (`-m "not live"` in addopts); `pytest -m live` runs the Azure tests.
Both are run (live twice) at every milestone end.

### D-028 — Engine-owned slash commands · Decided (2026-09-26, M1)
Slash commands are handled in `engine/slash_commands.py`, not in the terminal UI (spec lists
`ui/commands.py`), so the web UI gets identical behaviour for free.

### D-029 — Session event logs before workspaces exist · Decided (2026-09-26, M1)
Until workspaces arrive (M2/M6), each interactive session logs to
`<forge_home>/sessions/<timestamp>/events.jsonl`. Later, sessions log under the workspace's
`.forge/transcripts/` as the spec says.

### D-030 — Content-filter "neutral rephrase" retry deferred · Decided (2026-09-26, M1)
Spec §5.3 says content-filter blocks are "retried once with a neutral rephrase". Re-sending the same
prompt would be blocked again, and only the agent can rephrase its own request, so M1 surfaces the block
clearly (LLMContentFilterError, never retried) and the rephrase is implemented in the agent loop (M3).

### D-031 — Marker for deliberately fake secrets in tests · Decided (2026-09-26, M1)
Lines carrying the comment `# check_secrets: fake` are skipped by the pattern layer of
`scripts/check_secrets.py` (exact `.env` values are still always checked). Regex source code is also not
treated as a credential.

### D-032 — Stateless Responses API with reasoning replay · Decided (2026-09-26, M1)
Verified live: `store=False` + `include=["reasoning.encrypted_content"]` lets Forge own the full history
while gpt-5.1 keeps its reasoning across tool turns. Assistant messages keep the raw output items and
replay them only to the model that produced them; dropping them (e.g. after compaction) still works.

### D-033 — Checkpoints store pre-change file copies · Agreed (2026-09-26, M2 brief)
Options: (a) copy only changed files into `.forge/checkpoints/<id>/` + index; (b) git in the workspace;
(c) diffs only. Chosen (a): works without git; undo = copy back. One checkpoint per file operation (a
move is one checkpoint covering both paths). Git history comes in M10E.

### D-034 — Write jail · Agreed (2026-09-26, M2 brief)
One gate (`safety/paths.py`): real path after resolving `..`, symlinks and junctions must be inside
`repo/`, `output/` or `.forge/` and never inside the original repository. Relative paths from the model
are joined with `resolve_inside`, which rejects absolute paths and escapes. OS-level hardening is the M3
spike (R2).

### D-035 — Encoding detection without a dependency · Agreed (2026-09-26, M2 brief)
BOM (UTF-8/UTF-16) → UTF-8 → cp1252 → latin-1 (never fails); NUL bytes in the first 8 KB = binary.
Line endings: lf/crlf/cr are normalised to "
" for editing and restored on write; *mixed* files are
never normalised. Every sample round-trips byte-exactly (tested).

### D-036 — Import-origin check: worst-case probe + sitecustomize shim · Decided (2026-09-26, M2)
Found while testing: prepending to PYTHONPATH (spec §6.1) cannot beat a `.pth` that inserts the
original app at the front of sys.path (legacy `easy-install.pth`, custom `.pth` hacks), because `.pth`
files run later during startup; modern `pip install -e` finders are appended and don't shadow. Also,
probing with `python -c` from the copy hides shadowing (the cwd goes first) while `pytest.exe` /
`flask.exe` are affected. So: (1) the probe runs as a script from a neutral temp folder and uses
`importlib.util.find_spec` (never executes app code); (2) if a top package resolves outside the copy,
Forge writes `.forge/pyshim/sitecustomize.py` and puts it first on PYTHONPATH — it runs after `.pth`
files, removes the original app path and editable finders for the app's packages, puts the copy first,
and chains to any existing sitecustomize; (3) re-check, and explain the fix to the user if it still fails.

### D-037 — Ancestor .gitignore files are copied · Decided (2026-09-26, M2)
Only the app folder is copied, but .gitignore files above it still apply (e.g. a root `*.tmp`). They are
copied into the workspace (unchanged, in the manifest) so the same ignore rules hold when output/ is built.

### D-038 — Symlinks and junctions are not copied · Decided (2026-09-26, M2)
A link inside the repo can point anywhere (including outside it). Links are skipped and listed in the
copy report; the user copies such content by hand if needed.

### D-039 — output/MANIFEST.json · Decided (2026-09-26, M2)
A machine-readable list of every changed file (status, hash, secret flag, move source) alongside the
Markdown files. Diagnose mode (M9) uses it to compare the real repo against the delivery.

### D-040 — Secret files are never exported · Decided (2026-09-26, M2)
Changed `.env`-type files are not copied to output/ and their content/diff never appears in CHANGES.md or
changes.patch; COPY_INSTRUCTIONS lists them to apply by hand (ENV_CHANGES.md gives key names in M3+).

### D-041 — CLI for workspaces · Decided (2026-09-26, M2)
`forge new --repo R --workspace W [--app-folder F]` (auto-detects the app folder when there is exactly one
candidate; remembers the answer per repo in `<forge_home>/repos.json`), `forge export --workspace W`, and
`forge --workspace W` to attach the interactive session (transcript in `W/.forge/transcripts/`).

### D-042 — Shell model: fresh PowerShell per command · Agreed (2026-09-26, M3 brief)
Options: (a) one persistent PowerShell with output markers; (b) a fresh process per command with Forge
carrying the working directory. Chosen (b), as Claude Code does. The command is wrapped in a generated
script (UTF-8 output, final cwd recorded, exit codes preserved) and passed with `-EncodedCommand`: no
quoting problems, and PowerShell's execution policy (which may block .ps1 files on corporate laptops)
does not apply. Measured cost: 0.5–2 s PowerShell start-up per command. Stdin is closed; Read-Host
fails immediately in -NonInteractive mode.

### D-043 — grep is pure Python · Decided (2026-09-26, M3)
Spec §9.2 says "uses rg if present". Chosen: always the threaded pure-Python search. ripgrep may not be on
the office laptop, and can't apply Forge's ignore rules and secret-file hiding; one code path behaves the
same everywhere. Revisit in M11 if large repos are slow.

### D-044 — Shell classifier design · Agreed (2026-09-26, M3 brief)
Own tokenizer; segments split on `; | && ||`, newlines, braces and parentheses, so commands inside script
blocks and subexpressions are classified on their own. Levels: blocked / ask (with an always-ask flag) /
safe. Unknown commands ask. Writes into the original repository are blocked; writes by shell (even inside
the workspace) ask, because they bypass checkpoints. Reading the original repository and the app's venv is
allowed. PowerShell's own AST parser is evaluated in M11.

### D-045 — "Always allow this prefix" is per workspace · Agreed (2026-09-26, M3 brief)
Stored in `.forge/permissions.json` (first 3 words of the command). Never applies to blocked or
always-ask commands.

### D-046 — Tool output cap is character-based until M4 · Decided (2026-09-26, M3)
24,000 characters, head + tail kept, full output saved to `.forge/tool_outputs/NNNN.txt` with a pointer.
M4 replaces this with per-tool token caps (spec §10.3).

### D-047 — Approvals · Decided (2026-09-26, M3)
The engine publishes `approval_requested` and waits; UIs answer with Approve (scope once|prefix) or
Reject (optional instruction), which bypass the input queue. The instruction is returned to the model as
the tool result. Terminal: the next typed line answers (`y`, `a`, `n <what to do instead>`).

### D-048 — Agent loop details · Decided (2026-09-26, M3)
Consecutive read-only calls run in parallel; state-changing calls run alone, in order. Results are
appended in the original call order; on interrupt, unfinished calls get an "Interrupted by the user"
result so call/result pairs stay valid. Denied calls return "Not allowed: <reason>". Content-filter blocks
are retried once with a note asking the model to rephrase (completes D-030). A per-turn step limit
(`limits.max_iterations_per_task`) stops with a notice.

### D-049 — Low-integrity sandbox spike: works without admin · Agreed: option A (2026-09-27)
Spike result (R2): `icacls <workspace> /setintegritylevel (OI)(CI)low` works without admin; a process
created with a low-integrity copy of the user's token (documented Win32 calls via ctypes) can write in
the workspace but is denied by Windows when writing to the original repository or the user profile; it
can still read everything, and temp files work when TEMP points into the workspace. PowerShell at low
integrity behaved the same. User chose A (on by default, automatic fallback); built as D-050.

### D-050 — Low-integrity sandbox for every shell and background command · Agreed (2026-09-27, option A)
Options: (A) on by default with automatic fallback; (B) opt-in; (C) defer to M11. Chosen A.
- `safety/sandbox.py`: labels folders with `icacls /setintegritylevel (OI)(CI)low /T`; starts PowerShell with
  a low-integrity copy of the user's token (CreateProcessAsUserW via ctypes; documented Win32 only; no
  admin). `SandboxedProcess` mimics asyncio's Process (pid, returncode, stdout, wait).
- Writable at low integrity: `repo/`, `.forge/tmp` (TEMP/TMP) and `.forge/sandbox` (pip cache) only.
  `output/`, checkpoints, baseline, `permissions.json` and the event log stay out of reach, so a command
  cannot grant itself permissions or tamper with the delivery (tested).
- Labelling happens on the first command of a session (marker file `.forge/sandbox/labelled`); files
  created later inherit the label.
- Fallback: if labelling or process creation fails, commands run normally and the model and the user are
  told once ("Sandbox unavailable, commands now run without it: <reason>").
- Commands the user approves still run sandboxed. Anything that must write outside the workspace (e.g.
  installing into the user's own venv) is handed to the user to run (A-11).
- Config: `shell.sandbox: low_integrity | off` (default low_integrity on Windows); also added
  `shell.timeout_s` and `shell.permission_mode`.

### D-051 — Milestones proceed without approval gates · Agreed (2026-09-27)
User instruction: "You create the Milestones one by one, without asking for my approval." From M4 on,
Claude picks the recommended option for each design choice, records it here, runs the full suite at the
end of each milestone, posts a summary, and continues. Stops only when blocked by something only the user
can provide, or when the user's data/repositories would be at risk.

### D-052 — Context: in-place compaction, calibrated estimates · Decided (2026-09-27, M4)
The working history is compacted in place (full record stays in the event log and .forge/compactions/).
Token estimates = tiktoken × calibration, where calibration = provider-reported input tokens ÷ Forge's raw
estimate for the previous request (clamped 0.8–2.0). This folds in encrypted reasoning items and framing
without guessing. The §10.7 stress test uses a deterministic summariser function (budgeting, not the model,
is under test — consistent with D-008); a live test covers the real summariser.

### D-053 — Pinned block goes at the end of the request · Decided (2026-09-27, M4)
Spec §10.2 doesn't say where. Placing it after the history keeps the conversation prefix stable for
prompt caching (the pinned block changes often: files modified, tasks). Slots have a priority order;
over the 8% cap, lowest-priority slots are shortened first.

### D-054 — Compaction cuts at step boundaries and always keeps the latest request · Decided (2026-09-27, M4)
Found in the stress test: one agent task is one user turn with many tool steps, so cutting only at user
messages left nothing to summarise. Cuts now happen at step boundaries (a user message, or an assistant
message together with its tool results) — never inside a call/result group — and the latest user request
is always kept verbatim. Config `context.keep_recent_turns` keeps its spec name but counts steps.

### D-055 — No thrash: micro-compaction scope, summary cooldown, trusted summaries · Decided (2026-09-27, M4)
Found live in a tiny window: stubbing outputs the current task still needed made the model re-read them
until the step limit. Now: (1) micro-compaction only stubs outputs from earlier user turns; within the
current task, space is recovered by summarising (which keeps the findings); (2) after a summary, the next
one waits for keep_recent_turns new steps (otherwise a history hovering at the threshold triggers a paid
summary on every call — observed as a >10 min run); (3) the summariser sees up to 6,000 characters per
tool output with an explicit "shortened for this summary" marker; (4) the system prompt tells the model
to trust summarised findings and re-read only when it needs exact text.

### D-056 — Internal errors don't kill the session · Decided (2026-09-27, M4)
Found while testing: an unexpected exception inside a turn ended the session's input loop silently. Now it
is reported as an `error` event ("the session is still running") with a redacted traceback in
.forge/logs/ (or <forge_home>/logs/).

### D-057 — Token-based output caps, applied centrally · Decided (2026-09-27, M4)
Every tool result is capped in the agent loop: 6,000 tokens (shell tools 4,000; configurable), head + tail
kept, full output saved to .forge/tool_outputs/ with a hint to read it in ranges.

### D-058 — BM25 implemented in-house · Decided (2026-09-27, M5)
Spec §3 lists `rank_bm25`, which requires numpy (~15 MB) for ~30 lines of maths. `kb/bm25.py` implements
Okapi BM25 in plain Python, with identifier splitting (ClaimsService -> claims, service). No new dependency.

### D-059 — Minimum Python raised to 3.11 · Decided (2026-09-27, M5)
`tomllib` (reading pyproject.toml for the stack/commands facts) is standard from 3.11. The target laptop runs
3.13, so `requires-python >= 3.11` instead of adding a TOML dependency; ruff/mypy target 3.11.

### D-060 — Knowledge Base design · Decided (2026-09-27, M5)
- Built from the ORIGINAL repository (read-only), secret files never read; stored at
  `<forge_home>/kb/<repo-slug>-<hash>/` and shared by every workspace for that repo + app folder.
- Deterministic docs (exact, regenerated on every refresh): STACK, COMMANDS, API_CATALOG, DB_SCHEMA, LLM_GRAPHS,
  ESSENTIALS (pinned), and the facts half of modules/<package>.md. LLM docs (kb_builder role): ARCHITECTURE,
  CONVENTIONS, and the narrative half of each package doc, from facts + capped source excerpts; code is data.
- Refresh: facts are always re-extracted; only packages with changed files get new LLM docs; ARCHITECTURE and
  CONVENTIONS are rewritten only when >= 25% of Python files changed, otherwise patched with a
  "Recent changes" section (spec §11.4 "patched rather than rebuilt").
- Hand edits: a document is pinned when one of its lines is exactly `<!-- pinned -->`. (Found in testing: the
  note on generated docs mentioned the marker, which made every generated doc look pinned forever.)
- DB_SCHEMA comes from models + SQL scripts + raw-SQL usage; live Postgres introspection is added in M7.
- The credentials bootstrap (spec §9.5.1) is detected (table + env names) and shown in DB_SCHEMA/essentials.
- Tools: kb_search (BM25 over doc sections + symbol names; docs first, then symbols), kb_read, find_symbol,
  find_references, list_symbols. `kb_refresh` is not a model tool: refreshing costs LLM calls and the KB
  describes the original repo, not the workspace; it runs via /kb and, in M6, the KB CHECK phase.
- CLI `forge kb build|refresh|rebuild|status --repo R [--app-folder F]`; slash `/kb ...`; session start reports
  a missing or stale KB.

### D-061 — Agent loop: continue after cut-off or empty turns · Decided (2026-09-27, M5)
Found live: a reply can hit the output limit with reasoning using the whole budget (no text), or the model can
end a turn with nothing / "I will continue…". Now: a cut-off reply is continued (next call at low reasoning
effort) and an empty turn is nudged, at most twice per stretch; the system prompt says to keep working with
tool calls until done, and the pinned summary header says to continue from its next step directly.

### D-062 — Live compaction test calibration · Decided (2026-09-27, M5)
The extreme 10–13k windows made the model re-read and occasionally lose facts after many summaries (R26). The
live test now uses a small but not starved 20k window with low thresholds, so compaction is exercised without
testing near-starvation; runaway re-reading is bounded (≤ 6 reads per file) and handled properly by M8's
stuck detector.

### D-063 — Orchestrator: engine-driven phases ending on phase tools · Decided (2026-09-27, M6)
Options: (a) one long agent conversation told to follow phases; (b) an engine state machine that runs the
agent loop per phase with a phase-specific toolset and instructions, where a phase ends only when its tool
succeeds (propose_requirements / propose_plan approved; task_update per task). Chosen (b): predictable,
resumable and testable. CLARIFY and PLAN run in plan (read-only) mode; EXECUTE uses a task-scoped reset
(spec §10.6) with the previous task's handoff note; the requirement and task board are pinned.
Phase instructions live in agent/prompts/phases.md.

### D-064 — "No claim without evidence" is enforced · Decided (2026-09-27, M6)
Every tool call advances a step counter. File edits (and file-changing shell commands) record the step;
a passing test command (pytest/unittest) records the step as verified. task_update(done) is refused while
the last edit is newer than the last passing test run (tasks with no edits need no test run).

### D-065 — State and resume · Decided (2026-09-27, M6)
`.forge/state.json` (phase, tasks, current task, approvals, change request) is rewritten atomically after
every transition, with tasks.json, REQUIREMENTS.md, PLAN.md, PROGRESS.md, DECISIONS.md and DISCUSSIONS.md
alongside. Opening a workspace with an unfinished run resumes automatically; an interrupted task restarts
from its brief with a "resumed — check what's done first" note (files modified are pinned).

### D-066 — Review, export, change requests, restructure · Decided (2026-09-27, M6)
REVIEW runs the full test suite from the app folder; a failure adds one fix task and goes back to EXECUTE
(the reviewer subagent and verify ladder come in M8). EXPORT builds output/ and reports/final.md. A message
after DONE is a change request (PLAN with a short plan, no CLARIFY). `/restructure <how>` records the test
result before, plans and executes the reshaping (move_file keeps old -> new paths), and the review compares
before/after results.

### D-067 — Interaction and headless · Decided (2026-09-27, M6)
ask_user (design forks, logged to DISCUSSIONS.md and DECISIONS.md), request_user_action (done / skip /
can't, with verification by command; "can't" leads to a workaround discussion, A-11), approvals of the
requirements and plan show the full Markdown. `forge run --workspace W (-p TEXT | --requirement-file F)
[--auto-approve] [--output-format json]`: auto-approve approves gates and ordinary commands, picks the
recommended option, never approves the always-ask list, answers user actions with "can't"; exit code 0 done,
2 blocked/unfinished, 1 error. `forge resume --workspace W` and `forge --workspace W` resume interactively;
`--direct` gives the old tool chat without the workflow.

### D-068 — Explore subagent · Decided (2026-09-27, M6)
EXPLORE runs a read-only subagent with its own history, context manager and private event bus; only its
report (<= 1.5k tokens) enters the main conversation and .forge/notes/explore.md (spec §10.5).

### D-069 — Database driver and connections · Decided (2026-09-27, M7)
psycopg 3 (`psycopg[binary]`, LGPL, wheels for 3.11-3.14 on Windows) for Forge's own connections only.
Every connection sets statement_timeout, lock_timeout, idle_in_transaction_session_timeout,
application_name=forge, keepalives and sslmode from config; read-only work also sets
default_transaction_read_only. Connections are short-lived and sequential (at most one or two at a time).
Forge never gives its own DB credentials to the app: commands get only `PGOPTIONS=-c search_path=<scratch>`;
the app keeps its own DSN/bootstrap, and pointing it at a different server follows the repo's own test
configuration (asked at a design fork when there is none).

### D-070 — SQL guard · Decided (2026-09-27, M7)
An in-house tokenizer (comments, '' strings, $tag$ bodies, quoted identifiers) splits statements.
Read-only: every statement must start with SELECT/WITH/EXPLAIN/SHOW/VALUES/TABLE, with no write keywords
anywhere (catches data-modifying CTEs and EXPLAIN ANALYZE DELETE), no deny-listed table and no server
file/admin functions. Scratch: any schema-qualified name outside the scratch schema is refused (alias.column
is recognised), system schemas only for reads, and SET search_path, GRANT/REVOKE, roles, DO blocks, COPY
PROGRAM, DROP SCHEMA/DATABASE are refused. The server-side read-only session is the second layer.

### D-071 — Scratch schema, registry and cleanup · Decided (2026-09-27, M7)
One schema per workspace, `forge_<workspace name>`. `<forge_home>/scratch_registry.json` locks it to one
workspace (a live workspace path) and records every object Forge creates. Cleanup (`/db cleanup`,
`forge cleanup --workspace W`, confirmation unless --yes) drops only recorded objects, never CASCADE, and the
schema only when Forge created it and it is empty. With `scratch.create: forge_if_allowed` (default) Forge
creates the schema itself when its role has CREATE on the database; otherwise the agent writes a DB request.
Cleanup is not automatic at EXPORT: change requests after DONE still need the scratch tables.
Deviation: no Postgres advisory lock (it would need a connection held for the whole session); the registry
lock covers Forge-vs-Forge use on one laptop.

### D-072 — Access levels, DB requests, server-run · Decided (2026-09-27, M7)
Access is detected per configured database at KB CHECK / resume / direct session start and by `forge doctor`:
L3 when a probe table can be created and dropped in the scratch schema (or the schema can be created), L2
when connected otherwise, L1 with a one-line human reason. The status is pinned ("Databases") and shown.
DB requests live in `.forge/db_requests/DBR-n/` (request.sql, REQUEST.md, status.json); `/db done` verifies
by running the verification query (L2/L3) or accepts the pasted result (L1), then unblocks tasks whose
blocked_reason names the request and continues the workflow; `/db cant|skip` unblocks them with a note to
find a workaround. `mark_server_run` records DB tests Forge couldn't run: output/SERVER_RUN.md, a note in
COPY_INSTRUCTIONS and "NOT run" in the final report's Database section.

### D-073 — DB_CHANGES.sql · Decided (2026-09-27, M7)
Built from the change set: every added/modified `.sql` file, sorted by folder then file name (the repo's
V004 < V005 convention), concatenated with a run-order header. Each script is also delivered at its own
path. Credential-bootstrap tables found by the KB are stored in the KB manifest and deny-listed.

### D-074 — Live gate once per milestone, not blocking · Decided (2026-09-27, with the user)
The user asked not to block development on long live runs. The end-of-milestone gate is now: ruff, mypy,
offline suites on 3.13 and 3.14, the new milestone's live tests, and ONE full live pass (not two), run when
the milestone's code is final (never while shared code is being edited, which invalidated a run in M7).
The M7 full live pass is folded into M8's.

### D-075 — Verify ladder and verification tools · Decided (2026-09-27, M8)
`verify` runs: py_compile on changed .py files (baseline diff, so shell edits count) → the repo's ruff or
flake8, and mypy, only when the repo configures them AND they are installed in its venv → tests for touched
modules → (full=true) the whole suite; it stops at the first failing rung. Targeted tests = changed test
files + tests importing a touched module or any app module importing it (3 levels, app factory/__init__ not
propagating) + tests whose file name shares a meaningful word with those modules (API tests reach services
through the client); if nothing matches, the whole suite runs rather than reporting no evidence. pytest runs
without our own -q (repos set it in addopts; -qq hides the summary), and the exit code decides when no
summary is printed. `run_tests`, `verify`, `openapi_check`, `langgraph_check` run commands Forge builds
itself, so they skip the shell approval flow (still sandboxed, still denied in plan mode). OpenAPI/LangGraph
checks are scripts in .forge/tmp run with the app's venv; both accept `setup` code (the repo's test config,
a fake LLM) because real app factories and graph builders need arguments. App smoke via http_request
arrives with M10's browser/HTTP tools.

### D-076 — Stuck detection and escalation · Decided (2026-09-27, M8)
Triggers: identical call x3 with no edit in between; identical error signature x3 (signatures strip
numbers, addresses, temp paths); a file returning to an earlier content twice; 25 steps with no new file
content, passing test or new error; more than limits.max_fix_attempts (5) failed verification runs.
Escalation, one level per signal: reflection note -> debugger subagent (fresh context, reviewer role's
model, read-only tools + run_tests/verify) -> web search (skipped until M10) -> ask_user with the diagnosis
(options: try the fix / give a hint / skip) -> block the task and continue. Too many fix attempts jumps to
ask_user. In direct (non-orchestrated) sessions there is nobody to ask: the agent is told to stop and
explain. Counters and level reset per task (orchestrator) — subagents never escalate.

### D-077 — Review phase · Decided (2026-09-27, M8)
REVIEW = the full suite (parsed) -> when it passes, the deterministic test guard (AST diff of changed test
files against baseline: removed/renamed tests, fewer assertions, new skip/xfail, trivially-true asserts;
new tests asserting nothing are minor) -> the reviewer subagent (reviewer role, read-only, gets the
requirement and the diff) reporting `- [blocking|minor] path:line — problem — fix`. Failing tests or blocking
findings add a FIX task; at most 2 fix rounds, then open findings are reported in reports/review.md.

### D-078 — Web UI server and security · Decided (2026-09-27, M9W)
FastAPI + uvicorn (MIT/BSD) with the `websockets-sansio` implementation, in Forge's own process: one active
workspace session (WebSessionManager), opened from the home screen or `forge ui --workspace W`. Binding is
refused for anything but 127.0.0.1. A random per-run token (secrets.token_urlsafe, not a JWT, A-13) arrives
once in the URL, is moved into an HttpOnly SameSite=Strict cookie by a 303 redirect (so it leaves the address
bar), and is required on every request, static files and the WebSocket included. Host must be
127.0.0.1:<port>/localhost:<port> (DNS rebinding) and Origin, when sent, must match. CSP: self only, no inline
script/style, ws only to the loopback port. File endpoints serve only repo/ and output/ of the open workspace,
through the write jail's path checks, never secret files, never venv/.git. Only one WebSocket client controls
the session (sends inputs); others watch read-only and can "take control".

### D-079 — Frontend · Decided (2026-09-27, M9W)
Plain HTML + CSS + ES modules (app.js, chat.js, panels.js, util.js), no build step. Vendored and pinned in
static/vendor with licences and SHA-256 sums: marked 15.0.12 (MIT), DOMPurify 3.2.6 (Apache-2.0/MPL-2.0),
highlight.js 11.11.1 (BSD-3), diff2html 3.4.51 (MIT). All Markdown goes through marked -> DOMPurify; other
model/tool text is inserted as text nodes. A reload or reconnect replays events since the last seq seen
(first load: everything), then asks /api/state which approval/question ids are still pending, so answered
cards stay closed. Cards: approvals (requirements/plan: Approve / Request changes / Reject; permissions: Allow
once / Always allow prefix / Deny + instruction), questions (options with pros/cons/risks, Recommended badge,
Other…, keys 1-9), user actions (copy per step; Done / Skip / I can't / It failed). Panels: Tasks, Files
(lazy tree with change markers, viewer, output.zip, COPY_INSTRUCTIONS with remembered checkboxes), Diffs
(diff2html, checkpoints with Rewind), DB (status, DB requests with Mark done / I can't / paste box), Context &
cost (Compact now), Settings (model per role, permission mode; keys never shown).

### D-080 — Engine events for the UI · Decided (2026-09-27, M9W)
The engine publishes `user_message` (so a replay shows what the user typed) and `task_list_updated` (phase,
current task, tasks) on every orchestrator state save. The terminal UI ignores both.

### D-081 — Diagnose mode · Decided (2026-09-27, M9)
`forge diagnose --workspace W [--error-file F] [--no-run]` and `/diagnose [pasted error]`.
Integrity check, read-only on the real repo, driven by output/MANIFEST.json: missing file (+ same name
elsewhere = wrong location), partial paste = lines of Forge's version absent from the user's file (listed;
lines with register_blueprint/add_url_rule/include_router/add_resource/app.register( make it a
missing_registration), CRLF/encoding-only differences are silent, deleted/moved files still present,
packages: third-party imports in added files that the pre-Forge baseline never imported + new lines in
requirements*.txt, checked with the user's venv interpreter from a neutral folder; env vars: names the new
code reads (os.environ/getenv) that the baseline didn't, looked up in the process environment and the names
(never values) in repo/app .env files; DB: CREATE TABLE / ADD COLUMN in DB_CHANGES.sql checked read-only
by introspection when a database is reachable. Fresh copy run: the real app folder is copied into
.forge/diagnose_run/<n>/ (inside the write jail — the spec said <workspace>/diagnose_run), imports pointed
at the copy (shim when the venv has an editable install), tests run sandboxed. Analysis: a read-only
subagent (reviewer model) only when tests fail or an error was pasted. Report: .forge/reports/diagnose-<n>.md.
Code fixes to Forge's delivered code go through a change request in the session (output/ + COPY_INSTRUCTIONS
rebuilt), not a separate path.

### D-082 — Web tools · Decided (2026-09-27, M10)
web_search = Tavily /search (TAVILY_API_KEY in Forge's .env; without it the tool says how to enable it).
web_fetch = Tavily /extract when a key exists, else httpx GET + an in-house HTML-to-text converter (stdlib
html.parser; html2text is GPL-3 and was not added). Both cache 24 h in <forge_home>/cache/web, redact
queries, and prefix results with an "untrusted content" marker (spec §14.4). Pages over 12k characters are
summarised by the summariser role, focused on the question. Both tools are read-only (no approval needed).

### D-083 — Browser tools and http_request · Decided (2026-09-27, M10)
Playwright async API, one headless browser per session started on first use: msedge -> chrome -> bundled
chromium. Tools: browser_open (with optional wait_for text/selector), browser_snapshot (aria snapshot, 12k
chars), browser_click / browser_fill (CSS selector or visible text/label), browser_screenshot
(.forge/screenshots), browser_console, browser_network, browser_close; http_request (httpx) for API smoke
tests. v1 use is the app Forge built, so both browser and http_request only reach localhost/127.0.0.1/::1;
external pages go through web_fetch. Acceptance is covered by an e2e test that starts the fixture app with a
new endpoint and finds it in Swagger UI in headless Edge (Swagger UI's own assets come from a CDN: the test
skips when offline).

### D-084 — User memory and custom commands · Decided (2026-09-27, M10)
<forge_home>/memory/M<timestamp>.md, one preference per file (title = first line), redacted before saving.
The index (titles) is pinned (memory_index slot); memory_read / memory_write tools (memory_write only for
explicit, lasting user preferences — it writes to Forge Home, not the workspace, so no approval); `/remember
<text>`, `/memory [delete <id>]`. Custom commands: <forge_home>/commands/<name>.md, `/name args` sends the
file's text with $ARGUMENTS replaced. Lessons (scoped, approved, retrieved per task) are M10C.

### D-085 — DuckDuckGo as the no-key search provider · Decided (2026-09-27, with the user)
`web.search_provider: auto | tavily | duckduckgo | off` (default auto): Tavily when TAVILY_API_KEY is set,
otherwise DuckDuckGo's HTML results page (html.duckduckgo.com, POST q=...), parsed with the stdlib HTML parser,
redirect links unwrapped, ads dropped. No new dependency (the duckduckgo-search package does the same
scraping). It is unofficial: it may be rate-limited ("anomaly" page -> a clear error) or blocked by a
corporate proxy; queries are redacted, results cached 24 h and marked untrusted, exactly as with Tavily.

### D-086 — SerpAPI provider · Decided (2026-09-27, with the user)
`web.search_provider` gains `serpapi` (Google results via serpapi.com/search.json, engine=google,
SERPAPI_API_KEY in Forge's .env). `auto` order: Tavily -> SerpAPI -> DuckDuckGo, the first with a key.
Errors report the HTTP status and SerpAPI's message only (the request URL carries the key); the key is a
registered secret, so the redactor removes it from every event, log and model input.

### D-087 — Azure OpenAI's built-in web search as a provider · Decided (2026-09-27, with the user)
Verified on the gpt-5.1 deployment (api-version 2025-04-01-preview): the Responses API accepts
`tools=[{"type":"web_search"}]` and returns a web_search_call plus an answer with url_citation annotations.
`web.search_provider: azure` sends the query to the `web.azure_search_role` model (default summariser) with
that hosted tool, through Forge's router (cost, retries, redaction, budget apply); the result is the model's
cited answer + de-duplicated source URLs, cached 24 h. It is never chosen by `auto`: each call costs model
tokens plus Azure's per-search fee, and the answer is a model summary rather than raw results. The chat-
completions fallback refuses hosted tools with a clear error. Mechanism: ChatRequest.hosted_tools,
LLMResponse.citations.

### D-088 — Search order with fallback · Decided (2026-09-27, with the user; replaces the `auto` rule of D-085/D-086)
`web.search_provider: auto` walks `web.search_order` (default duckduckgo -> serpapi -> tavily -> azure):
providers without their key (or without Azure in the session) are skipped; an error, block, quota message or
empty result moves on to the next; the answer says which provider answered and why earlier ones failed.
Naming one provider uses only that one. The user chose DuckDuckGo first (free), SerpAPI next, Azure's paid
built-in search last.
Update (2026-09-27, user): Tavily moves last — its API is blocked on the office laptop's network. Default
order: duckduckgo -> serpapi -> azure -> tavily.

### D-089 — M10 wiring: hooks, custom commands, status bar · Decided (2026-09-27, M10)
Every session's tool list gains web_search, web_fetch, memory_read, memory_write and the browser/http tools;
the session passes its secrets, search order, Azure search hook and summariser to them and pins the memory
index. `hooks.post_edit` (config, default empty) runs each command after a successful write/edit/multi_edit
with {file} = the quoted repo-relative path, through the normal sandboxed shell; the output is appended to the
edit's result and the read tracker is updated (a formatter may have rewritten the file). Unknown `/name`
commands expand <forge_home>/commands/<name>.md into a message (shown as the user's message). The terminal
prompt has a bottom status bar: phase and task, working/idle, context %, cost, permission mode. The browser
is closed with the session.

### D-090 — Mode B: structure export and host profiles · Decided (2026-09-28, M10B)
`forge_structure_export.py` is a standalone stdlib script (Python 3.10+, shipped in forge.modeb, printed by
`forge profile export-script`) the user runs on the host. It emits tree, pinned versions, per-module imports,
class bases/decorators, function/method signatures (defaults as …, string literals in annotations as '…'),
blueprints (name, url_prefix, route paths, methods, schema names), SQLAlchemy columns (types, incl. FK targets
like 'policies.id' — schema, not data), SQL script names, LangGraph nodes/edges, env KEY names. Never bodies,
literals, values, comments, .env or data files; secret-looking files are only counted. --mask replaces terms
consistently (TERM1...). Profiles live in <forge_home>/profiles/<name>/ (profile.json with version and
sensitive_terms, PROFILE/CONVENTIONS/INTERFACES.md, exemplars/E00n.py+.md, structure_export.json,
structure_index.json, CHANGELOG.md). Deviation: the index is our BM25 over per-module documents in JSON, not
sqlite. Everything stored is redacted and has sensitive terms masked (<termN>); every change bumps the version.

### D-091 — Mode B workspaces · Decided (2026-09-28, M10B)
`forge new --standalone --profile P --workspace W`: project/ (Forge's "repo" in this mode; path_of maps
"_harness/..." to _harness/), _harness/ (host_stubs/, harness_conftest.py, run_app.py), output/, .forge/
(host_profile_ref.json), .venv (created empty; host versions are installed by `pip install` through the shell,
which always asks). WorkspaceInfo.mode "B", repo_path "". The write jail covers project/, _harness/, output/,
.forge/; the shell scope is strict (outside paths blocked, not asked); the sandbox also labels _harness/ and
.venv/. PYTHONPATH: project/ then _harness/host_stubs then _harness. Stub packages use pkgutil.extend_path so
project/ and stubs share the host package. Tests run with `pytest -p harness_conftest` (deviation: the spec
named _harness/conftest.py; a plugin keeps the project's own conftest untouched). No KB CHECK/EXPLORE; the
profile essentials take the KB slot; tools profile_search/profile_read/profile_update (approval)/
assumption_add/modeb_document. Web search refuses queries containing sensitive terms, the host's top-level
package names or table names.

### D-092 — Mode B deliverable and revisions · Decided (2026-09-28, M10B)
EXPORT (and /export) builds output/ from project/ only, plus INTEGRATION_GUIDE.md (the 7 sections of §6A.6),
INTERFACE_CONTRACT.md and INTEGRATION_NOTES content (written by the agent into .forge/modeb/), ASSUMPTIONS.md
(the register, also appended to the plan at approval), DB_CHANGES.sql, and REVISION_NOTES.md: each export is
revision N+1, the previous output/ is archived in .forge/revisions/rN/, and the notes list added / changed /
removed files by hash. Chat-driven diagnose: /diagnose explains that errors are pasted as messages; code fixes
are change requests (new revision). Commands: /profile [show|list|terms], /assumptions [confirm|wrong],
/contract, /revision, /forget-snippet; /kb and repo diagnose are disabled in Mode B.

### D-093 — Learning: library, lessons, metrics, retro · Decided (2026-09-28, M10C)
Scope keys: Mode A `repo:<kb folder name>` (one per repository app folder), Mode B `profile:<name>`; a
workspace sees its own scope plus `global` and `user`. Library: <forge_home>/library/REQ-nnnn.md + cards.json,
written after EXPORT (goal, plan, decisions, tasks, files, endpoints/tables detected, problems, status);
search = BM25 + folder overlap, same scope only; `library_read` reads a card or a file of that past workspace.
PLAN/change phases get the top related cards with an instruction to read and cite them. Lessons:
<forge_home>/learning/lessons.json (proposed/approved/rejected/archived; scope, keywords, evidence, confidence,
uses), redacted, near-duplicates merged (Jaccard >= 0.8), PLAYBOOK.md = approved global lessons; only approved
lessons are retrieved (BM25 over text+keywords, top-k 5, ~800 tokens) into the pinned `lessons` slot at every
task start. Metrics: learning/metrics.jsonl (task + run lines, Forge version); `/stats`. RETRO after EXPORT
(config learning.retro prompt|auto|off): the reviewer model writes learning/retros/REQ-n.md with
'- LESSON:' lines; prompt = one approval card for all proposed lessons (approve keeps, reject drops; /lessons
edits later). Tools: library_search, library_read, lesson_propose, improvement_propose.

### D-094 — Self-improvement proposals · Decided (2026-09-28, M10C)
<forge_home>/improvements/IP-n/ (PROPOSAL.md, meta.json, change.patch, override.md, tests/, VALIDATION.md).
Tier 1 = a proposed global lesson. Tier 2 = text appended to <forge_home>/prompt_overrides/<system|system_modeb|
phases>.md, which prompts load on top of the built-in files — only after the user types `/improve apply IP-n`;
config tweaks stay advice (Forge never writes config.yaml). Tier 3 = a patch: `/improve validate IP-n` copies
Forge's source checkout (src, tests, pyproject; not venvs) into IP-n/sandbox/, `git apply`s the patch, copies the
proposal's tests in, runs the suite and records PASSED/FAILED; the installed source is never touched (tested).
Validation needs a source checkout; from a wheel install it says so. Learning web tab: lessons (approve/reject/
make global), library cards, proposals (show/validate/apply/reject).

### D-095 — Claude Code parity (M10E) · Decided (2026-09-28)
FORGE.md: <forge_home>/FORGE.md -> <kb folder or host profile>/FORGE.md -> <workspace>/FORGE.md, rendered into a
new high-priority pinned slot `instructions` (capped ~1500 tokens, with the /style text); `/init` drafts the
repo-level one from KB essentials; a chat line starting with '#' asks (question card: workspace/repo/user/cancel)
and appends. @-mentions: @path, @path:10-80 (numbered lines), @image (copied to .forge/inputs/ and attached),
@DBR-n, @REQ-n, @L<n>/@lesson-n (same scope only); secret files are never inlined; messages > 8000 characters
are saved to .forge/inputs/paste-*.txt and replaced by a 1500-character preview + reference. `/effort
low|medium|high|default` sets AgentLoop.effort; a message starting 'think hard:' sets high for that turn.
`/style concise|explanatory|learning`. Skills: built-ins in forge/skills/*/SKILL.md (flask-smorest-endpoint,
langgraph-agent, sql-migration-raw, pytest-patterns, vision-document-pipeline, eval-harness), plus
<forge_home>/skills and <kb|profile>/skills; only descriptions pinned (`skills` slot); `load_skill`. Custom
subagents <forge_home>/agents/<name>.md (frontmatter tools/model(role)/effort/description); `spawn_subagent`
runs explore/reviewer/debugger or a custom agent with only its listed tools. Notebook tools (cell read /
replace / insert / delete, outputs kept unless clear_outputs; read-before-edit applies). Local history: git with
--git-dir=.forge/history.git --work-tree=repo/ (nothing git-related inside the copy or output), baseline at
session start, a commit per completed task, secret files excluded; `/log`, `/diff <task|hash>`. `/bg [kill]`,
`/rename`, `/export-chat` (.forge/exports/), `forge sessions list`. MCP client (optional, `mcp` 2.x MIT,
config mcp.enabled + servers {command,args,env_names,cwd}; stdio): tools named mcp__<server>__<tool> with the
server's input schema, joining every phase through SessionHost.extra_tools; the permission gate asks for them
(auto mode allows); `/mcp`. Toast notifications are not built (web notifications + the terminal status bar
cover "waiting for you").

### D-096 — Fixes found by the Mode B live run · Decided (2026-09-28)
(1) Orchestrated phases rebuilt the tool list from defaults, silently dropping Mode B tools: SessionHost now
keeps `extra_tools` (Mode B + MCP) that every phase includes. (2) pytest setup errors (missing fixture) have no
reason in the short summary: the parser now takes the first 'E ...' line of that test's section. (3) Mode B
openapi_check defaults to _harness/run_app.py create_app(). (4) Files the host already has (per its structure
export) are never delivered as whole files in Mode B: they go to output/_merge/<path>.proposed with a "merge
these lines" step in INTEGRATION_GUIDE. (5) Labelling Mode B's .venv for the sandbox went through the write jail
and failed every command: it is now checked to be inside the workspace and labelled directly.

### D-097 — Multimodal & eval-driven development (M10D) · Decided (2026-09-28)
Options for image/PDF handling: (a) Pillow + pypdfium2 (MIT-CMU; BSD/Apache, cp313 Windows wheels, offline),
(b) PyMuPDF (AGPL — rejected for an enterprise tool), (c) OpenCV (large wheel; left to the generated apps).
Chose (a). Tools: view_image (vision role; image sent as a data URL, logged by sha256 only), pdf_render,
image_info, image_ops (crop/rotate/deskew/grayscale/threshold/pad/resize), draw_boxes, compare_images,
run_eval, synth_samples. Sensitive paths (.forge internals, .env*) are refused. Eval sets live in
evals/<name>/ (eval.yaml command + targets + sensitive flag, samples/, labels/, optional questions.jsonl);
metrics: field exact / normalised match, region IoU ≥ 0.5 recall, "unreadable respected"; overlays and
eval-history.jsonl under .forge/reports/; after 3 consecutive misses of the targets the tool tells the agent to
stop and discuss (spec §13A). Synthetic generator labels exactly what it draws and marks samples
`synthetic: true` (never proof of real accuracy). Labelling helper: `forge label <dir>` (loopback + token + CSP,
like the web UI) and an Evals tab. LLM judge: rubric shipped (JUDGE_RUBRIC) for RAG answers; its live check is
optional. Finding from the live test: the vision model read handwriting perfectly but its signature bounding box
had IoU 0 with the truth — so the vision-document-pipeline skill now prescribes the hybrid of spec §13A.6
(classical-CV candidates, model classifies/chooses) and the live test only checks that localisation answers are
returned, not their accuracy.

### D-098 — Hardening & packaging (M11, part 1) · Decided (2026-09-28)
**Redaction** — new fixtures (tests/test_hardening.py) found real gaps; added patterns for well-known token
shapes (GitHub, OpenAI-style sk-, Slack, Google AIza, AWS AKIA), SAS `sig=`, `ConvertTo-SecureString '…'`, and
widened the key=value rule to JSON/YAML keys, headers (`api-key:`, `Ocp-Apim-Subscription-Key:`) and
connection-string keys (`Pwd=`, `AccountKey=`). Plain numbers are exempt so `max_tokens: 128000` stays readable.
**Shell** — reading a secret file through the shell (`Get-Content .env`, `*.pem`, `id_rsa`, `secrets/…`) now
always asks: read_file shows only key names, but the shell would print values that redaction can't know
(`.env.example/.sample/.template` stay safe). **Prompt injection** — options: (a) prompt rule only, (b) strip
suspicious text, (c) prompt rule + flag. Chose (c): tool results containing text addressed to an AI ("ignore
previous instructions", "AI assistants reading this", …) get a Forge note appended (content is never removed)
and a `notice` event (kind injection) tells the user; the permission gate stays the real protection (tested:
injected exfiltration/push/delete/install commands are denied or asked even in auto mode). Live check: the model
ignored an injected `Invoke-WebRequest … -InFile .env` and warned the user (it had not warned with the prompt
rule alone — twice). **Deleting Forge's own files** — delete_file stays always-ask for the user's files; for
files not in the baseline manifest (created by Forge in this workspace) it follows the normal rules (auto mode
allows). Found live: a headless Mode B run ended "blocked" because it couldn't remove a file it had created
itself. **Mode B prompt** — never recreate an existing host module in project/; stubs go to
_harness/host_stubs/, test helpers to tests/ or _harness/. **Mode B search tools** — list_dir/glob/grep on
_harness/ crashed (paths computed relative to project/); fixed. **Packaging** — options: (a) pip wheelhouse +
per-user venv, (b) PyInstaller exe (AV false positives, slow start, harder upgrades), (c) embeddable Python
zip (no venv/pip ergonomics). Chose (a): scripts/build_wheelhouse.ps1 (cp313 win_amd64 binary wheels only,
SHA256SUMS, optional Playwright Chromium, self-verifies with a --no-index install + `forge doctor --offline`;
66 wheels) and scripts/install_forge.ps1 (hash check, %LOCALAPPDATA%\Forge\venv, forge.cmd shim, .env template,
never overwrites .env/config) + docs/INSTALL.md. Extras `mcp` and `browser` added to pyproject. pytest keeps 25
tmp dirs (a parallel pytest session had deleted a running live test's workspace).

### D-099 — Fixture evals with hidden acceptance tests (M11) · Decided (2026-09-28)
Options: (a) score runs by Forge's own final verdict, (b) an LLM judge over the diff, (c) hidden acceptance
tests. Chose (c): six realistic tasks in evals/fixture_tasks/<id>/ (task.yaml requirement + hidden_test.py) —
a new aggregate endpoint, a business-rule limit, a search filter, a nested listing with 404, a new LangGraph
triage category, a validated sort option. Each hidden test fails on the unmodified fixture (checked) and is
copied into the workspace only after Forge finishes, so Forge can't tailor code to it.
scripts/run_fixture_evals.py runs `forge new` + `forge run --auto-approve` per task (own FORGE_HOME), then
the hidden test and the whole suite (old + Forge's + hidden) with the fixture venv, and writes
test-artifacts/evals-<ts>/REPORT.md. The embedded-Postgres fallback stays a deviation: pgserver has no
cp313 win_amd64 wheel.

### D-100 — Sandbox labelling failed silently outside the user profile · Decided (2026-09-28)
Found by the end-to-end run in C:\Work\Projects\ForgeE2E: `icacls /setintegritylevel … /C` printed "Access is
denied" for every folder (inherited *Modify* rights don't include WRITE_OWNER, needed to change a mandatory
label) yet exited 0, so Forge believed the sandbox was on while no folder was writable at low integrity —
every command that writes (pytest's temp files, __pycache__) failed and the agent blocked its tasks. All
tests ran under %TEMP% (Full control), which hid it; an enterprise laptop's workspace folder may well look
like C:\Work. Options: (a) fall back to no sandbox when labelling fails, (b) grant the current user Full
control on Forge's own workspace folders (the owner may always change the DACL), then label, (c) require
workspaces under the user profile. Chose (b) with (a) as the fallback: label_low grants the user
`(OI)(CI)F` on the folder, labels it, and verifies the label on the folder itself (raising → fallback with a
notice when it didn't stick); prepare_sandbox re-checks the label instead of trusting its marker file.
Regression test: a folder with only Modify rights gets labelled. Risk: the check reads icacls' English
output (R33).

### D-101 — Escalation step 3 and Diagnose app smoke (M11 carried-over items) · Decided (2026-09-28)
**Escalation step 3 (web search)** — options: (a) Forge builds and runs the query itself from the error text,
(b) a system note telling the agent to look the error up with its web tools. Chose (b): the agent knows which
part of the error is generic, and web_search's own guards (no code/internal names; Mode B's host-term filter)
still apply. The step is skipped when web_search isn't in the session's tools. **Diagnose app smoke** — options:
(a) start the app and hit its endpoints over HTTP, (b) build the app in-process from the fresh copy and list
its OpenAPI routes. Chose (b): it catches import errors and missing blueprint registrations (the most common
copy mistakes, seen live in Mode B) without opening a port or needing the app's runtime config; it runs in
the same sandbox as the fresh-copy tests and its result is in the report summary.

### D-102 — Mode B live run fixes, round 3 · Decided (2026-09-28)
(1) "no tests ran, 1 error" (collection errors) was reported as "pytest found NO tests — write tests", which
sent the agent writing more tests while the real problem was an import error; the ladder now says "could not
COLLECT the tests — fix these first" with the `E …` lines. (2) Forge now keeps Mode B's package plumbing
itself: before each Mode B test run, every stub package in _harness/host_stubs that project/ also has gets the
`pkgutil.extend_path` line (it was the agent's job and it lost two tasks to it). (3) New blueprints/routers in
delivered files that INTEGRATION_NOTES doesn't mention are listed as registration steps in the integration
guide (a delivered route nobody registers is a 404 in the host — seen live), and the Mode B prompt requires
INTEGRATION_NOTES. (4) The live test saves the host copy, output and pytest log when the host step fails.

### D-103 — "No tests ran" is not a pass · Decided (2026-09-28)
Seen in the end-to-end run: the agent wrote tests at the repository root while pytest runs in the app folder;
pytest printed "no tests ran" (exit 0 under some configurations), TestReport.passed was True, verify said
"[ok] full test suite", yet the evidence rule refused "done" — contradictory signals, four refused
task_updates, the task blocked and every dependent task skipped. TestReport.passed now requires at least one
passed test, the summary says "no tests ran", and the ladder's "found NO tests" message names the folder
pytest runs in and where tests must live.

### D-104 — A crashing tool must not end the session · Decided (2026-09-28)
Seen in the end-to-end run: the agent wrote `targets: {fields: [], regions: []}` in an eval.yaml; run_eval
raised TypeError, which escaped the loop (only ForgeError/OSError/ValueError were caught) and ended a 45-minute
headless run mid-task. (1) load_eval validates `targets` (metric name → number) with a message naming the
metrics; (2) AgentLoop._execute turns any other exception from a tool into ToolResult(ok=False) telling the
agent it's a Forge bug, and logs the traceback to .forge/logs/tool-error-*.log. The run resumes with
`forge run --workspace <ws>` (no requirement) where it stopped.

### D-105 — Findings from the end-to-end chatbot run: redaction vs code, stubs in production · Decided (2026-09-28)
(1) The key=value redaction rule masked Python code such as `image_token = extract(q)`; the reviewer then saw
`image_token = [REDACTED:assignment]` and raised a false blocking finding, and the agent copied masked values
into test files. Unquoted code-style values after a lower-case `name = ` (calls, attribute/subscript access,
None/True/False) are no longer masked; .env-style lines (`API_KEY=value`) and quoted literals still are.
write_file/edit_file refuse content that adds a `[REDACTED:` marker, telling the agent to use a placeholder.
(2) The run finished "done" with 30 passing tests, but the CLI's production clients were stubs (fake
embeddings, file-name descriptions, a constant signature score, a canned answer): tests only exercised fakes.
Options: (a) reviewer prompt only, (b) a deterministic check, (c) both. Chose (c): check_stubs flags
stub/placeholder markers ("not intended for production", "tests can monkeypatch", "stub implementation", …)
in added/changed non-test code as a blocking review finding, and the reviewer must trace each acceptance
criterion to the shipped code path. (3) Mode B: paths starting with `project/` are rejected (the model wrote
everything to project/project/…, which was delivered under output/project/). (4) Fixture evals: 6/6 hidden
acceptance tests pass, full suite green in all six (test-artifacts/evals-20260928-060742/REPORT.md).

### D-106 — End-to-end check results and the last redaction fix · Decided (2026-09-28)
The user's end-to-end task (Forge builds a FAISS multimodal RAG chatbot, then it extracts the signature from a
real prescription photo) took four Forge runs on one workspace: the build (8 tasks, 30 tests) and three change
requests a user would send after trying it. Round 1 found the production clients were stubs (led to D-105's
stub guard); round 2 wired real Azure calls; round 3 fixed the CLI still using a constant score and the CV
treating the dark table as ink — the crop then contained the signature but was too loose (IoU ≈ 0.19 against
a hand-estimated box); round 4 asks for printed-text removal and a tight crop. Redaction also masked
`api_key=api_key` (a parameter passed through), producing false "placeholder" review findings that consumed fix
rounds: a keyword whose value is its own name is now left alone. The scanner skips test-artifacts/ (captured
test output holds the fixture's fake JWT) and the wheelhouse script removes the build/ folder pip leaves.
Final result of round 4: 50 tests pass; the crop is tight around the doctor's scribble (406,907–600,1045,
model confidence 0.98) but still includes part of the printed caption and cuts off the handwritten number
(IoU ≈ 0.36 against a hand-estimated box). Round 4 also introduced a bug only a real run shows: a "vision
capability" probe sends `max_tokens`/`temperature=0` (rejected by the newer deployment) and reports the
error as "deployment doesn't support images"; RAG_VISION_VALIDATE=0 bypasses it.

### D-107 — Tables the code touches vs the scratch schema · Decided (2026-09-28)
Spec §9.5: "every table the code touches must exist in scratch before DB-backed runs; Forge checks this and
refuses the run otherwise", and schema-qualified writes must not reach the shared DB. Options: (a) refuse every
test run while a table is missing, (b) report missing tables before each run and refuse only the dangerous case,
(c) report only. Chose (b): Forge can't tell whether a test run actually uses the database (the fixture suite,
like many, uses SQLite), so (a) would block safe runs. db/table_check.py reads the tables the app's non-test
code uses (SQLAlchemy models + raw SQL, via the KB extractors, fresh from the workspace copy, cached by file
mtimes) and compares them with the scratch schema before every verify/run_tests pytest run; missing ones are
prepended to the result with how to create them. When non-test code WRITES to a schema-qualified table and the
scratch schema lives on a non-local database, the run is refused (R28 → mitigated). A DB error during the check
never blocks the tests.

### D-108 — Reviewer findings must carry evidence; at most 5 blocking · Decided (2026-09-28)
Seen in the end-to-end runs: blocking findings about code that wasn't there (stale diffs, masked text) and
wish-lists of extra hardening ("add retries", README wording) consumed both fix rounds while real problems
waited. Options: (a) prompt only, (b) a second LLM pass to judge findings, (c) prompt + deterministic evidence
check. Chose (c): a blocking finding must end with `evidence: \`…\`` quoting the offending code (or, for
something missing, the requirement's words); Forge checks the quote against the named file (raw and redacted
text) or the requirement and downgrades unverifiable findings to minor, with the reason in the report. At most
5 findings stay blocking. The prompt also tells the reviewer to read the current file (the diff may be older)
and that hardening the requirement didn't ask for is minor.

### D-109 — Mode B: tests that use host setup must request a host fixture · Decided (2026-09-28)
Every live Mode B run's first delivery failed in the host the same way: contract tests called
`session_scope()` (directly or via the new service) without a fixture; the stub worked, the host's engine only
exists inside the app fixture. modeb/fixture_check.py flags (blocking, in the review's test guard) any delivered
test that uses host infrastructure (`db`/`database`/`session`/`extensions` modules, `session_scope`-like names,
or new functions that use them) but requests none of the fixtures harness_conftest.py recreates (skipped when
the harness has an autouse fixture). Replayed on last night's evidence: it flags exactly the 6 tests that failed
in the host in revision 1 and none in the passing revision 2.
Live result (2026-09-28, after D-108/D-109): the Mode B live acceptance passed with the FIRST delivery passing
in the clean host copy (previous four runs all needed a pasted-failure revision); fixture evals 02 and 04 still
pass their hidden tests, and the evidence check downgraded two unfounded "blocking" findings.

### D-110 — Company networks: Windows certificate store and real connection causes · Decided (2026-09-28)
First run on the office laptop: `forge doctor` reported only "Could not reach the endpoint: Connection error."
for both models. On company networks the usual causes are HTTPS inspection (a company root certificate Windows
trusts but Python's bundled list doesn't), a required proxy, or DNS/VPN. Options for certificates: (a) ask
users to export the company CA and set SSL_CERT_FILE, (b) use the OS store via `truststore` (MIT, pure Python,
cp313 wheel, offline-installable), (c) disable verification (rejected: insecure). Chose (b), on by default,
FORGE_SYSTEM_CERTS=0 to opt out; injected at CLI start before any HTTPS client exists. Connection errors now
carry the innermost cause (e.g. SSLCertVerificationError, getaddrinfo, ConnectTimeout, 407) and a one-line
next step; `forge doctor` shows which certificate store is in use.

### D-111 — Standalone workflow for free-hand builds and pasted signatures · Decided (2026-09-28)
The user's main use is Mode B: build something new, often from signatures/snippets they paste. Three gaps:
(1) a profile could only be created in a terminal — the web UI's standalone form now also takes a new profile
name and sensitive terms and creates the (empty) profile with the workspace; (2) nothing told the agent to fill
an empty profile or how to treat pasted code — the Mode B prompt now says: ask only what this requirement needs
and save answers with profile_update; for a free-hand build choose conventional options and record them as
assumptions; pasted signatures are authoritative (exact names/params/types), go into INTERFACE_CONTRACT, are
stubbed in the harness, and may be kept as exemplars with approval; (3) the new workspace venv was empty, so
pytest was missing and a live headless run blocked every task (the live Mode B test had swapped in a ready venv
and hid this). Options: (a) keep asking to `pip install pytest` in the first task, (b) install pytest when the
workspace is created, (c) ship pytest inside Forge and point the workspace at it. Chose (b): creating the
workspace is the user's own action and pytest changes nothing on the host; the result is shown ("pytest:
installed" / why not), and if it failed the test tool tells the agent to ask for the install.

### D-112 — The interface contract always lists the host symbols the code imports · Decided (2026-09-28)
Live standalone run (pasted signature + existing host helper): the code and its 16 tests were right, but the
agent wrote no INTERFACE_CONTRACT and the export's default text claimed "no host symbols" while the code called
the host's `payments.audit.log_event`. modeb/contract_scan.py finds, from the delivered (non-test) code's imports,
every symbol from a package shared with the host that isn't new code in project/, with its signature from the
harness stub (or "no stub: signature unknown"). The export generates the contract from them when the agent wrote
none, and appends any the agent's contract doesn't mention. Live result after D-111 on a new empty profile:
exit 0, the pasted signature used exactly, log_event called with the digit count only, the host helper stubbed
in the harness and not delivered, 16 tests passing.

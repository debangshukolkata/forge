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

### D-113 — One "New project" form: project name + project folder (+ existing repo in Mode A) · Decided (2026-09-28)
The user's direction: both modes ask for a new project name and a new project folder; Mode A also asks for the
existing project/repository path; everything after that happens in the chat (Claude Code style). Options for
collecting them: (a) asked in the chat, (b) a small form, then chat — the user chose (b). The web start page now
has one form with a mode choice; POST /api/projects creates the workspace in the given folder and stores the
project name in workspace.json (`project`, shown in the sidebar). In Mode B the project name IS the host
profile (slugged, e.g. "Payments Masking" -> payments-masking): created on first use, reused when the name comes
back, so users never deal with "profiles"; existing projects are suggested as they type. Mode A's app sub-folder
is detected and only asked for when ambiguous. CLI: `forge new --project NAME` (Mode B: --profile optional).

### D-114 — React UI next to the classic UI · Decided (2026-09-28)
The user asked for a React UI on a different port, keeping the classic UI until the new one is tested; built
here with the built files committed (the office laptop needs only Python), React + Tailwind, "very
professional", designed with the ui-ux-pro-max skill. Stack: React 19 + TypeScript + Tailwind CSS 4 + Vite,
lucide icons (ISC), marked + DOMPurify + highlight.js + diff2html (as in the classic UI), fonts bundled via
@fontsource (OFL) — no CDN or Google Fonts. Source in ui-react/, build output in src/forge/web/react/ (package
data). `forge ui --react` serves it on 8766 with the same API, token, CSP and Host/Origin checks; the classic
`forge ui` on 8765 is unchanged. Security-relevant changes: (1) the session cookie is now per port
(`forge_token_<port>`) — browsers share cookies across ports of 127.0.0.1, so two UIs would overwrite each
other's token; (2) `forge ui --react --dev` accepts exactly one extra Origin, the Vite dev server
http://127.0.0.1:5173 (loopback, explicit flag, validated), and the token link then forwards to it. Design
system: Minimalism & Swiss Style, dark first + light theme, slate/green palette, IBM Plex Sans + JetBrains Mono
(ligatures off in code). Verified in headless Edge: home, New project flow, slash command, all eight tabs, theme
switch and a replayed conversation (tool cards, Markdown table, highlighted code, plan approval, question) with
zero console errors (so no CSP violations).

### D-115 — React UI functionality: attachments, @-files, mode cycling, history · Decided (2026-09-28)
The user: design later, functionality now. Found by comparing the engine with the UI: an `Upload` input was
declared but never handled, so no UI could attach a file. Added: POST /api/upload (raw body — no multipart
dependency; 25 MB cap; name sanitised; stored as .forge/inputs/<timestamp>-<name> inside the jail) and mentions
of `@.forge/inputs/<file>` (only files directly in that folder): images are attached for view_image, PDFs point
to pdf_render, text files are included, other formats are named with a note that Forge can't read them.
GET /api/files?q= lists matching project files for @-autocomplete (secret files never). React composer: attach
by paperclip, paste (Ctrl+V a screenshot) or drag-and-drop onto the chat, removable chips; one suggestion list
for "/" commands and "@" files; Shift+Tab cycles the permission mode (default → auto → plan) with an indicator;
Up/Down recalls earlier messages (per project, browser storage); slash commands are echoed in the chat; the
Evals tab refreshes on eval_report_ready; copy instructions get tick boxes. The classic UI is unchanged.
Cards carry data-card / data-pending / data-recommended for automation.

### D-116 — Live progress in the React UI · Decided (2026-09-28, discussed with the user)
Options discussed: (a) an activity line only (Claude Code style), (b) a progress header (phase stepper + task bar)
plus the activity line, (c) (b) plus an Activity tab with a timeline. The user chose (b), with plain-language
status and an animated indicator per kind of activity; no loader library (CSS animations + lucide icons: small,
offline, CSP-safe). Only real counts get progress bars — phases (six user-facing steps mapped from the engine's
phases) and tasks (one segment per task: done / in progress with a shimmer / blocked / pending); nothing
invents a percentage or an ETA. The activity line says what Forge is doing now from live events: the tool in
plain words with its target ("Running tests · tests/test_masking.py"), "Writing the reply" while streaming,
"Waiting for your approval/answer", or a phase-specific "thinking" text ("Planning the tasks", "Working on:
<task>"), each with its own indicator (ring, dots, scan, caret, test bars, globe, amber pulse) and an elapsed
timer; the header shows the elapsed time of the current run. task_list_updated now updates phase/tasks at once.

### D-117 — The React UI replaces the classic UI · Decided (2026-09-28, the user's call)
After testing, the user asked to remove the classic UI and keep the React one. `forge ui` now serves the React
build on the default port 8765 (the only UI); `forge ui --dev` accepts the Vite dev server; `--react` is kept as
a hidden, harmless alias. Deleted: src/forge/web/static (index.html, app.js, chat.js, panels.js, util.js,
app.css and the vendored marked/DOMPurify/highlight.js/diff2html files — the React build bundles its own
copies). create_app has no UI switch any more. Browser tests were ported to the React UI (mechanics: token
login, /help, Files/Diffs/Learning/Settings tabs, reload replay, output download; New project form in both
modes; the live Mode A run through the web UI). Projects are unaffected: all state lives in the project folder,
so a half-done project resumes in the React UI (auto-resume on open when it stopped mid-phase).

### D-118 — Tokens and cost per reply, task and phase; animated cost counter · Decided (2026-09-28, discussed)
The user asked for a cost indicator that moves as cost increases (chose: an animated counter only, USD) and for
tokens and cost per phase, per task and per reply with green / yellow / red (chose: all four places — task list,
phase stepper, each reply, a Usage tab; colours by fixed limits in config). Engine: every model call is filed
under the phase and task active when it was made (CostTracker.ledger + where; the reviewer, debugger and
summaries count where they ran) in a per-project UsageLedger, .forge/usage.json (input/output tokens, cost,
calls; totals add up across sessions and survive restarts). The router's per-call "usage" notice now carries the
updated summary (so numbers move per call, not per turn) and MESSAGE_DONE carries the reply's cost_usd.
Config: cost.colors.{reply,task,phase} = {usd: [green_below, yellow_below], tokens: [...]}; defaults reply
$0.01/$0.05 and 20k/100k tokens, task and phase $0.10/$0.50 and 150k/600k; the worse of the two colours wins;
exposed via /api/config. UI: the top-bar cost counts up (ease-out, 700 ms, jumps under reduced motion) with a
brief green highlight; badges on replies, task rows and stepper steps; the Context tab became Usage (context
window, this session, per-phase and per-task tables with totals). All figures are labelled estimates (tokens x
configured prices), not the Azure bill.

### D-119 — Run map: task graph + timeline of phases, tasks, agents and failures · Decided (2026-09-28, discussed)
The user asked for a graphical view of the plan, the tasks, blockers, spawned agents and failures (chose: task
graph + timeline, as a full-width "Run map" view next to Chat). Options considered: (a) React Flow + dagre for
the graph and a hand-drawn SVG timeline — chosen; (b) Mermaid rendered from text — static, no live state or
click-through, heavier bundle; (c) vis-timeline / a Gantt library — extra dependency for what is ~150 lines of
SVG, and harder to theme. New deps (UI only, bundled at build time, nothing at runtime on the laptop):
@xyflow/react 12 (MIT) and @dagrejs/dagre 3 (MIT). Engine: every event now carries `where` {phase, task} (the
bus stamps it when the session is orchestrated) and subagents emit `agent_started` {id, role, purpose} /
`agent_finished` {id, role, ok, tool_calls, failed_calls, duration_s}; the subagent's own events stay on its
private bus. UI: the map is derived only from the event list (live and replayed alike). Graph: Plan → tasks by
depends_on → Review → FIX tasks → Deliver; each card shows status, attempts, failed calls, stuck warnings,
helper agents, task cost badge and the blocked reason; the current task is ringed and its incoming edge
animated. Timeline: lanes for phases, each task and each agent role; red ✕ failed tool call, amber ▲ stuck,
amber ◆ waiting for the user; pauses longer than 45 s are squeezed (dashed break with the resume time) so hours
of waiting don't flatten the work. Clicking a card, bar or marker switches to Chat and flashes that event's row.
The Panels sidebar is hidden while the map is shown, to give it the full width.

### D-120 — Collapsible side panel · Decided (2026-09-28, small UI choice)
User asked to be able to collapse the right panel (Tasks, Files, …). A button at the right of the Chat | Run map
switch hides it to a 48 px rail of the tab icons (clicking one reopens the panel on that tab); the state is
remembered per browser (localStorage). Options: hide completely (loses the quick way back to a tab) or a rail —
chose the rail.

### D-121 — Animated current step in the progress header · Decided (2026-09-28, small UI choice)
User asked for animation on the active phase circle (e.g. Build) while it runs. The current step gets a spinning
accent arc and a soft expanding halo while Forge works (same signal as the live status line), and an amber
pulsing ring while it waits for the user; the step number stays readable inside. CSS only; stopped under
prefers-reduced-motion.

### D-122 — Failures drawer on the Run map · Decided (2026-09-28, discussed)
User asked to see what the "N failed calls" were (chose: a drawer sliding in from the right; summary plus
expandable output). Options considered: right drawer (chosen: room for error text, filterable, stays in the
Run map), popover at the click (cramped), a "Problems" tab in the side panel (hidden in the Run map view).
The drawer opens from the failed-calls chip (all), a task card's ✕ count (that task) or a ✕ timeline marker
(that failure highlighted); Esc/backdrop closes it. Each entry: plain-language kind (tests failed / edit didn't
apply / command failed / blocked or declined / tool error, from the tool name and output), outcome ("Fixed
later" = a later successful call of the same tool in the same task; "Task finished"; "Not fixed yet"), time,
what it tried, the last 6 lines of output (the error is usually last) with "Show more", and "Show in chat".
Engine: a failed call's event preview now keeps the first 400 and last 1,500 characters (was the first 1,500),
so the error at the end survives. Also fixed: React Flow disabled pointer events on non-draggable nodes, so task
cards weren't clickable; blocked cards now show their counts as well as the reason.

### D-123 — Run map: waiting-for-you bars, self-fitting graph, non-overlapping time labels · Decided (2026-09-28)
From the user's first real run: (1) waiting for approval wasn't visible on the map — a "Waiting for you" lane now
draws a bar from each request to the next event (Forge blocks until you answer, so the next event is the
answer), the open one growing until answered, and the summary strip gets an amber "Approval needed — open in
chat" button; (2) the graph was blank at the end of a live run — it fitted the view only once; it now refits when
its cards are measured and whenever the plan's shape or the area's size changes (not on every status update, so
a manual zoom/pan stays); (3) axis labels overlapped — labels that would collide are dropped (their dashed break
line stays), and dates appear when a run crosses days. Phase row redesign for multi-day runs: deferred by the
user ("we will redesign this phase"); options offered were scroll + zoom, a phase summary strip, group by day.

### D-124 — Progress stepper: cost and working time under each step · Decided (2026-09-28, user suggestion)
The per-step cost badges pushed "Deliver" out of the header. Each step now shows its name with cost and working
time underneath ("● $0.39 · 7m"); working time sums the gaps after each event of that phase, excluding waits for
the user. The stepper adapts to its own width (container queries): below 680 px only the current step shows cost
and time; below 600 px only the current step shows its name; everything is in the step's tooltip. Chosen over
tooltip-only (hides the numbers) and a separate row of numbers (loses the association with the step).
**Superseded by [D-127](#d-127).**

### D-125 — Light theme is the default · Decided (2026-09-28, user request)
The web UI opens in the light theme; the top-bar button still switches to dark. The choice is kept under a new
browser-storage key (`forge-theme-choice`), written only when the user toggles: the old `forge-theme` key was
saved on every load, so it recorded the old dark default rather than a real choice, and honouring it would have
kept existing browsers dark. Cost: anyone who had deliberately chosen dark sees light once and toggles again.

### D-126 — Styled scrollbars; chat never scrolls sideways · Decided (2026-09-28, user choice)
The UI used unstyled OS scrollbars, which showed as black Windows bars with arrow buttons inside the light theme.
Options shown to the user with previews: (A) slim neutral: a 10 px rounded thumb in `--border-strong`, no track or
arrows, darker on hover; (B) overlay shown only on hover; (C) green accent thumb. The user chose A. It applies to
every scroll area. Edge gets `::-webkit-scrollbar` rules, and Firefox gets `scrollbar-width: thin` plus
`scrollbar-color`, set only where the pseudo-elements are unsupported (Chromium ignores them on elements that have
the standard properties). Each theme now declares `color-scheme`, so native controls follow Forge's theme, not the
OS theme. Separate fix: a horizontal scrollbar appeared under the chat because a `<fieldset>`'s default min-width
is its widest content, so a long code line in an approval card widened the whole chat. The card's fieldset is now
`min-w-0`, and a browser test checks that the chat has no horizontal overflow.

### D-127 — Progress stepper: even spacing, always-visible labels, drop container queries · Decided (2026-09-28, user-reported bug)
Two bugs from D-124's layout: (1) uneven gaps between circles — each step's `<li>` was `flex-1` sized by its own
content, so a step with a longer cost/time subtitle (e.g. Build's "$0.39 · 7m") pushed its neighbours' connector
lines out of line with the rest; (2) at typical chat-column widths the container-query breakpoints (`@[600px]`,
`@[680px]`) hid step names and cost/time entirely, leaving bare numbered circles with no way to tell what phase
they represented. Options given to the user: (A) switch to a vertical stack below a width, with fixed-width
grid columns above it, no library — chosen; (B) horizontal always, only the active step ever labelled; (C)
horizontal always, inactive labels behind a hover tooltip only. The user picked A on all three sub-questions
(collapse to vertical, fix spacing with fixed columns, no new stepper library).

Implementation: the `<ol>` is a CSS grid, `grid-cols-6` (even columns) at ≥420 px measured width, `grid-cols-1`
(stacked rows) below it; the connector between steps is drawn as its own absolutely-positioned line (horizontal,
centred through the circles' row, or vertical, to the left of a stacked row) so its length never depends on label
width. Labels and the cost/time subtitle are always rendered, never hidden by breakpoint.

The breakpoint is driven by a `ResizeObserver` on the `<ol>` (a `useMinWidth` hook), not a CSS `@container` query
as D-124 used. While diagnosing screenshots that still showed the old bug after code changes, isolated test pages
confirmed `@container` conditions were never matching in our headless-Edge test harness (Chromium 154, both the
`msedge` channel and plain bundled Chromium) even for a trivial `width >= 420px` rule with plain `container-type:
inline-size` — while an equivalent `@media` query worked fine. Cause not fully root-caused (suspect a headless
rendering flag), but since it left the feature untestable in our own e2e suite and unverifiable on whatever Edge
build ships on the target enterprise laptop, `ResizeObserver` was used instead: broadly supported since 2020,
and it let the browser test in `test_web_e2e.py` actually exercise both layouts.

### D-128 — Drop the fixed phase pipeline; run a flat Claude-Code-style loop · Agreed (2026-09-28)
The user corrected the premise behind spec §7 (the SETUP→INTAKE→CLARIFY→KB CHECK→EXPLORE→PLAN→TASKS→
EXECUTE/VERIFY→REVIEW→EXPORT→RESTRUCTURE→HANDOFF→RETRO state machine, with mandatory approval gates at
REQUIREMENTS.md and PLAN.md): that design assumed Forge runs detached/unattended, but Forge runs live in
front of the user on their laptop, the same way Claude Code does. Options considered:
(a) keep the phase pipeline as-is; (b) keep phases but make each one's gate optional/configurable;
(c) drop the fixed pipeline entirely — a single agent loop (read request → act with tools → respond),
with inline judgment-based clarification and plan checks instead of mandatory named phases, exactly
mirroring how Claude Code itself behaves.
Chosen: **(c)**, replacing spec §7 (workflow/approvals) and the phase-filtered toolset in §8/§9.
Reasoning, resolved point by point:
- **Requirements confirmation**: no mandatory CLARIFY phase or signed-off REQUIREMENTS.md. Forge asks
  inline, only when the request is ambiguous or has a consequential fork — the same judgment call this
  assistant makes with the user, not a forced ≤5-question round every time.
- **Plan/design confirmation**: no mandatory PLAN phase or signed-off PLAN.md. Forge proceeds directly for
  small/clear changes; for a genuine design fork (architecture choice, hard-to-reverse decision, touches
  shared code) it still stops, lays out options with a recommendation, and waits — same trigger list as
  CLAUDE.md's existing "stop and discuss when" rules, just not gated behind a named phase.
- **Artifact trail / resumability**: no mandatory REQUIREMENTS.md/PLAN.md/tasks.json. Resumability instead
  comes from (1) the conversation/event transcript, (2) a lightweight in-session task list for visible
  progress on multi-step work (not an approval-gated artifact), and (3) the existing memory/lessons
  mechanism (§12), written as a deliberate action rather than a required phase output. The library
  requirement-card + retro can still be produced, but as an explicit end-of-work step the user or Forge
  triggers, not a phase-machine output.
- **Safety invariants**: nothing here weakens them. The write jail, DB scratch-schema guard, Mode B
  isolation and redaction (CLAUDE.md "Safety invariants") are already code-level checks independent of
  phase, not phase-enforced — they continue to run on every write/tool-call regardless of loop structure.
- **Sign-off cadence**: not fixed by which phase is active; expected to become a configurable mode (free
  hand vs. per-step approval vs. Claude-Code-default judgment) — to be recorded as its own decision once
  agreed with the user (this thread's point 3, not yet settled).
Rejected (a): too slow/heavy for live, in-front-of-the-user use (the user's own assessment). Rejected (b):
keeping the phase machine but making gates optional still carries the state-machine complexity and the
phase-filtered toolset for no remaining benefit once gates are judgment-based.
Consequence: spec §7 (Workflow & Approvals) and the phase list in §8 are being rewritten; `spawn_subagent`
types (explore, planner, reviewer, test_writer, debugger, §9.10) are no longer tied to specific phases —
Forge can call any of them at any point in the loop, same as this assistant's own Agent tool. Still to be
worked through point by point with the user: sign-off/approval modes (point 3) and Mode A/B execution
details (point 2).

### D-129 — Mode B: user-pinned interface contracts, learned over time · Agreed (2026-09-28)
User requirement: in Mode B, Forge has a free hand to design the solution, but the user may pin a specific
signature/contract upfront (e.g. the LLM call wrapper's signature, a file read/write helper's signature) so
generated code is easy to retrofit into the host repo by hand — and may change a contract mid-way, after
seeing generated code, with Forge accommodating the change from that point on.
Options considered for where the user provides this: (a) a dedicated Contracts panel/store in the
workspace (web UI side panel + a `CONTRACTS.md`-style file), always pinned into context like the Host
Profile, in addition to accepting it via chat at any time; (b) chat only, filed into pinned context/memory;
(c) folded into the existing Mode B Host Profile interview (§6A.2) only, asked once at setup.
Chosen: **(a)**, with chat also accepted as an entry point into the same store. Rejected (b): nothing keeps
track of which contracts are currently active across a long session, and no single place to review/edit
them. Rejected (c) alone: the profile interview is a setup-time flow; it doesn't cover changing a contract
mid-way after the user has seen generated code, which is a stated requirement.
Additional user requirement: Forge should **learn** contracts the user pins or repeatedly corrects, and
proactively recommend them on later, similar requirements — routed through the existing lessons mechanism
(§12: proposed, reviewed, approved, scoped same-repo/profile or promoted to global), not a new mechanism.
Consequence: spec §6A (Mode B) gets a new subsection for the Contracts store; §6A.5's plan step lists which
contract each new file's interface conforms to, alongside the existing profile-exemplar mirroring; the
Contracts store is added to §10.2's pinned context (alongside the Host Profile); lesson proposals (§12.2)
can originate from a corrected/repeated contract, not only from retro.
Confirms (no change from current spec, restated for this decision thread): §6A.7 (chat-driven diagnose)
already covers post-retrofit error handling — user pastes errors, Forge classifies and fixes, revises
output; A-11's fallback chain already covers dependency installs — Forge installs freely; if blocked by
something only the user can do (e.g. enterprise policy), Forge asks the user, and if the user can't either,
proposes a workaround or states plainly the requirement can't be met as specified so the user can descope.

### D-130 — Sign-off cadence is a live conversational instruction, not a config setting · Agreed (2026-09-28)
Closes the open point from [D-128] (sign-off cadence). Options considered: (a) global config default
(`config.yaml`/`/config`), overridable per workspace; (b) chosen once per workspace at SETUP, no global
default; (c) no config surface at all — cadence is an ordinary instruction the user gives Forge in
conversation, exactly the way this assistant is told "go ahead with the recommended option, don't ask me"
or "ask me before every step" mid-session, and Forge follows it from that point until told otherwise.
Chosen: **(c)**, per explicit user instruction ("should work exactly like Claude Code... do it how Claude
does it today"). Worked example given by the user: told "go ahead with the recommended option, I'm going
to sleep," Forge proceeds unattended overnight applying its own recommended choices; the next morning, told
"ask me before every step," it switches to asking before each action from then on. No workspace-setup
question, no config key, no per-workspace default — the instruction is just conversation state, same as it
is for this assistant.
Default absent any instruction: the same judgment-based behaviour already specified — CLAUDE.md's
"Stop and discuss when" list and spec §7's discussion points (design forks, shared/core code touched, new
dependency/DB/config, wrong assumption, escalation reached, neither party can act) — i.e. Forge starts in
"ask when it matters" mode, same as this assistant's own default, until the user grants a free hand or
asks for tighter/looser cadence.
**Critical-case override, never skippable regardless of any "go ahead" grant:** the existing safety
invariants (CLAUDE.md: write jail, Mode B isolation, secrets/redaction, DB scratch-schema-only writes,
Forge can't modify its own install/config) and A-9's always-ask list (headless `--auto-approve` never
covers always-ask actions) — generalised from headless mode to every mode. A free hand covers Forge's
*design and implementation* choices; it never covers an irreversible or destructive action, a request that
would touch the user's original repo or secrets, or anything already on the always-ask list. This mirrors
exactly how a blanket "go ahead" from the user does not authorise this assistant to skip its own hardcoded
safety checks (e.g. `git push --force`, deleting files outside its own session's work, secrets handling).
Consequence: no new config key or SETUP question is added. The orchestrator (already being reworked per
[D-128]) tracks the current cadence as session/conversation state (default: judgment-based) that the user
can change at any time by saying so, the same way slash-command-free instructions already work for this
assistant. Spec §7's "Discussion points" section gets a short note on this; §14 (Permissions) gets the
critical/always-ask list consolidated in one place so it's enforceable in code, not just prose.

### D-131 — Orchestrator state.json drops the Phase field entirely; Run map/stepper UI deferred · Agreed (2026-09-28)
Implementing [D-128] required deciding what replaces `Phase` (the enum currently driving
`agent/orchestrator.py`'s control-flow switch) in `OrchestratorState`/`state.json`. Options: (a) keep a
narrow, non-driving `activity` label purely for display (Run map/stepper, resume message), updated by the
model as a side effect but not read by control flow; (b) drop phase/activity entirely — `state.json` keeps
only `requirement`, `change_request`, `restructuring`, `tasks`, `current_task`; resume message becomes
generic ("resuming; N tasks pending, currently on T3") instead of phase-based.
Chosen: **(b)**, per the user ("drop phase/activity entirely — we will take up the Run map/stepper later").
Rejected (a): still carries a field the model must remember to keep current, and half-adapts the existing
Run map/stepper (D-118..D-127) to a vocabulary that's likely to change again once that UI is redesigned —
cleaner to cut it now and redesign the UI as its own later task than to carry a stopgap field.
Consequence: `status_changed`'s `phase` payload field is removed; the Run map/stepper UI (which reads it)
is explicitly out of scope for this pass and will show stale/fixed/missing phase state until redesigned —
tracked as a follow-up in TODO.md, not a regression to fix now.

### D-132 — Verification becomes judgment-based; sessions persist and resume like a reopened chat; cadence persists · Agreed (2026-09-28)
Three follow-on decisions, closing gaps found while re-checking "is this exactly like Claude Code" before
writing code.

**Verification (replaces §13's mandatory verify ladder + reviewer subagent + bounded fix rounds as a gate
before a task/requirement can close):** Options: (a) judgment-based, like this assistant — Forge runs
tests/checks when it judges them warranted (after a meaningful change, before claiming something works,
when something seems risky), no mandatory full-suite-plus-reviewer-subagent checkpoint; the verify ladder
and reviewer subagent tools still exist and Forge can invoke them anytime, just not as a forced gate;
(b) keep the full ladder mandatory by default, relaxed only under an explicit free-hand grant.
Chosen: **(a)**, per the user ("I want exactly as you do... rigorous tests every time makes development
very slow"). This is a further cut beyond [D-128]: D-128 only removed the CLARIFY/PLAN *approval* gates;
this removes the REVIEW phase's mandatory verification gate too. §13's ladder and §9.8's verification tools
are unchanged as *available* tools — only their mandatory, blocking use before EXPORT is removed.

**Persistence & resume:** the user corrected the premise that "live, one conversation" (point 1 of the
earlier Claude-Code-parity gap list) meant Forge has no persistence gap to close — it does, but the fix is
that Forge already needs to behave like *reopening a chat with this assistant*: laptop dies, network drops,
user returns after 7 days, or a token/context limit is hit — reopening the workspace continues where it
left off. Options for how: (a) auto-resume silently (task list, cadence, conversation context restored,
with a brief "here's what was in progress" note, no prompt) — the same experience as reopening a
conversation with this assistant; (b) always show a summary and ask the user to confirm resume vs. start
fresh, in case they've forgotten the workspace's purpose after a long gap.
Chosen: **(a)**. This confirms and generalizes what `Orchestrator.needs_resume`/`resume()` already do in
the current code (spec §7, §12.6) — state.json survives a kill and a workspace reopen continues at the
same task — extended to the flat-loop design being built for [D-128]: resumability is not phase-dependent
and must survive the phase field's removal ([D-131]).

**Cadence persistence:** does a "go ahead, don't ask me" or "ask me before every step" instruction
(§7, [D-130]) survive a killed/resumed session, or reset to default judgment-based on reopen? Options:
(a) persist it in state.json, consistent with (a) above and the overnight-build example in [D-130] (the
user shouldn't have to re-grant free hand after every restart); (b) reset to default on every resume as a
safety-conscious default.
Chosen: **(a)**. This corrects [D-130]'s original framing ("cadence is conversational state, not a config
setting") — it is still not a config *setting* (no config key, no SETUP question, changed only by the user
saying so in chat), but because Forge sessions can be killed and resumed days later (unlike a single
terminal invocation), the *current value* of that conversational state must be persisted in state.json
alongside the task list, or a "go ahead while I sleep" grant would silently evaporate on any interruption —
defeating the example [D-130] was written around. The always-ask/critical list is still never waived by a
persisted free hand, same as before.

Consequence for the orchestrator rewrite in progress: `OrchestratorState`/`state.json` (already losing the
`Phase` field per [D-131]) keeps or gains: the task list (unchanged), a persisted `cadence` field
(`default` / `free_hand` / `ask_every_step`), and enough of a resume summary to greet the user accurately
on reopen ("N tasks pending, currently on T3, cadence: free hand" style) — without reintroducing a
phase-driven control flow. The REVIEW step's mandatory gate logic in `orchestrator.py` (`_review`,
`MAX_REVIEW_FIX_ROUNDS`) is being removed as part of the same rewrite, not kept as dead code.

### D-133 — Run map/stepper redesign for the flat loop (closes the [D-131] follow-up) · Agreed (2026-09-29)
Closes the Run map/stepper redesign item left open by [D-131] (TODO.md): the old 6-step `ProgressHeader`
phase stepper reads a `phase` field that no longer drives control flow, and the two-pane Run map (task DAG
+ separate SVG timeline) was designed around the old fixed pipeline. Discussed with the user across several
rounds; final shape below replaces both.

**Activity/stepper screen:** delete `ProgressHeader` (the 6-step phase stepper) entirely — there is no phase
state left to represent honestly. Keep `ActivityLine` (already phase-independent: driven by `activity.kind`
and `state.current_task`, not by phase) as the one live indicator, and extend it with:
- a compact trailing badge on the current step showing running cost + elapsed time for the *current task*
  (from `cost.project.by_task[current_task]` and a task-start timestamp), in the existing `UsageBadge` style;
- a small persistent strip above the activity line for the *whole run's* total cost + elapsed time (using
  `runStartedAt`, which `ProgressHeader` used to surface and needs a new home for).

**Run map screen:** replace the fixed `planGraph()` skeleton (`@plan → tasks → @review → @deliver`, laid out
from a `phaseOrder` array) with a single live-growing DAG, React Flow + dagre as today, built incrementally
from the event stream rather than pre-drawn:
- nodes appear only when their start event fires: `start` once, a `task` node on that task id's first
  appearance in `task_list_updated` (so `update_plan` adding tasks later visibly extends the graph, not just
  the initial plan), an `agent` node on `agent_started` (explorer/debugger/reviewer) attached by a `spawned`
  edge to the task that triggered it (or to `start` if none), and a `deliver` node on export;
- `depends_on` edges between tasks as today; failure/stuck markers (currently timeline-only) move onto the
  DAG nodes themselves as small badges/icons, so no signal is lost;
- each task/agent node carries its own cost + time badge, matching the activity-line treatment, using
  existing data (`by_task`, `agent_finished`'s `duration_s`); per-agent *cost* (not just duration) needs a
  small backend addition (`agent_finished` payload gaining `cost_usd`, summed in `subagent.py`'s
  `_tracked_run` the way `MESSAGE_DONE` already does) — treated as a fast-follow, not a blocker, so the UI
  ships first against what already exists;
- layout: full dagre relayout on every structural change (node/edge count changes, not every event), with
  animated position transitions rather than a hand-rolled incremental/position-preserving layout — decided
  against the incremental approach as the riskier build (dagre isn't designed for it; edge crossings/overlap
  regressions are likely the first time a late dependency or a subagent attaches to an old task). A full
  relayout with an animated transition also more honestly reflects that the plan itself is being revised,
  not just extended.

**Dropped from the design:** the separate SVG timeline pane (chronological view, idle-gap compression) is
removed, not kept alongside the DAG — one primary view, not two competing ones; its only distinct value
(failure/stuck markers, "when did this happen") is preserved by moving those markers onto DAG nodes. Also
dropped: auto-fit fighting the user — `fitView` (already used for the DAG's initial/grown layout) keeps
re-fitting automatically only until the user manually zooms or pans; after that, React Flow's built-in +/−
`Controls` (already free) take over, with a recenter affordance to return to live auto-fit.

Options considered and rejected: keeping both DAG and timeline (two first-class views judged unnecessary —
the DAG-with-live-growth plus per-node time/cost subsumes most of the timeline's value); position-preserving
incremental dagre layout (rejected as the highest-risk, hand-rolled part of the original proposal); bundling
the `agent_finished` cost-field backend change into the same milestone as the UI rewrite (deferred to a
fast-follow so the visible UI work isn't gated on an invisible backend change).

Build order: (1) `runmap.ts` — incremental DAG builder off first-seen events, replacing `planGraph()`;
(2) `RunMap.tsx` — full-relayout-on-structural-change + animated transitions, node cost/time badges, markers
moved onto nodes, auto-fit-until-user-touches-it + recenter; (3) `Activity.tsx` — delete `ProgressHeader`,
add the run-total strip, extend `ActivityLine` with the per-task badge; (4) remove now-dead phase plumbing
(`STEPS`/`STEP_OF_PHASE` in `activity.ts`, `PHASE_LABEL`/`phaseWorkMs` in `runmap.ts`, `stepOf`) once nothing
reads it; (5) fast-follow: per-agent `cost_usd` in `agent_finished`. Re-enables the two `test_web_e2e.py`
Run-map/stepper tests skipped under [D-131] once the new design is in place, and folds in the pre-existing
D-123 multi-day-runs redesign (was going to touch the same stepper/timeline code — the growing DAG with a
recenter control addresses it: old runs simply load with their full graph already laid out, no separate
"group by day" mechanism needed).

### D-133a — `task_list_updated` gains an `exported` field for the Run map's Deliver node · Agreed (2026-09-29)
Implementing milestone 1 of [D-133] (`runmap.ts`'s incremental DAG builder) needed a live, replay-safe signal
for "the run has actually exported" to gate the `deliver` node — D-133 flagged this as open ("no explicit
`exported` bool right now in RunModel") and left the exact source to be found during the build. The frontend
already carries a stale, free-text `phase` string from `/api/state` (`resume_summary()`, D-128/D-131) that
must not be used; there is no `session_ended` event type in `engine/events.py` (the old `runmap.ts` switch
case for it was dead code, never firing). `OrchestratorState.exported` (`agent/state.py`) is the real signal,
already flipped to `True` at the end of `Orchestrator._export()` right before `_save()` calls `_publish_tasks()`.

Options considered: (a) add `exported` to the existing `task_list_updated` payload in `_publish_tasks()` —
one field on an event the frontend already consumes and that fires immediately after `_export()` sets the
flag, so it's visible live and on replay with no new event type; (b) a new `EventType.SESSION_ENDED` event —
more explicit but a new wire type for one boolean, and every existing consumer (console UI, replay) would need
to learn it; (c) surface it only via `/api/state`'s polled snapshot — breaks replay (events are the source of
truth for a reopened project per D-119) and adds a state field alongside the already-flagged-stale `phase`.
Chose (a): smallest change, reuses an event both live and replayed sessions already see, no new wire type.

Change: `Orchestrator._publish_tasks()` (`agent/orchestrator.py`) adds `"exported": self.state.exported` to
the `task_list_updated` payload. `runmap.ts`'s `buildRunModel` sets `RunModel.exported = true` once it sees
that field true on any `task_list_updated` event; `buildGraph` adds the `@deliver` node only once `exported`
is true. No new event type, no change to `/api/state`.

### D-134 — Chat: a failed tool call the model immediately self-corrected renders de-emphasised, not red · Agreed (2026-09-29)
User feedback from testing the new empty-project flow: the model wrote `write_file` with a `project/`-prefixed
path (paths are already relative to the workspace's `project/` root), got a correct, specific rejection, and
retried with the fixed path seconds later — but the chat showed the corrected first attempt as a full alarming
red-X failure row, indistinguishable from a failure that never got fixed. Confirmed via
`.forge/transcripts/events.jsonl` that Forge's behaviour itself was correct (the write jail's error message did
its job; the retried write succeeded) — this was a display-only problem, not a functional bug.

Options considered: (a) auto-collapse/de-emphasise a failed call once a later same-tool call succeeds — muted
styling, an "retried" badge, no red, while a failure with no successful retry keeps full red; (b) group a
failed attempt and its retry into a single collapsible row; (c) just recolor failed-then-retried rows amber
without any other change. Chosen: **(a)**, per the user, as it fixes the actual annoyance (red alarm fatigue
for normal model self-correction) without changing the transcript's one-event-one-row model or hiding any
information — every row a user could want is still there, just visually right-sized to whether it turned out
to matter. Matches the spirit of the existing `Failure.outcome === "fixed"` classification already used by the
Run map's failure drawer ([D-133]), extended to the chat view; not literally reused since chat's `ChatItem`
model and `runmap.ts`'s `RunModel` are built by separate reducers over the same event stream.

Implementation: `ChatItem`'s `tool` variant (`types.ts`) gains an optional `retried?: boolean`. `useForge.ts`'s
`tool_call_finished` reducer case: on a successful call, walks backward through the timeline for the nearest
earlier call of the *same tool name* — if that call is a `fail` not already marked `retried`, marks it so and
stops (an earlier `ok` of that tool means any failure before it was already resolved by a prior success, so
the walk stops there too). Matches on tool name only, not exact arguments/path — exact matching is unreliable
by construction in the triggering case itself (the retried call's path differs from the failed one). This is a
heuristic: a failure genuinely unrelated to a same-tool success that happens to follow it shortly after would
also be marked "retried" even though the two aren't actually connected. Judged acceptable — false positives
only ever soften a failure's visual weight, never hide it (the row and its full error preview stay, expandable,
just less alarming), and the common real case (mis-call → clear error → immediate correct retry) is exactly
what this is for.

`Chat.tsx`'s `ToolCard`: a `retried` failure shows a muted border/opacity, a neutral "retried" badge, and a
neutral `AlertOctagon` icon instead of the red `XCircle` — an unresolved failure (no later same-tool success)
is untouched. `npm run build` clean.

### D-135 — Bug fix: `propose_plan`/`update_plan` must end the turn so the orchestrator can start the first task · Agreed (2026-09-29)
Found while testing the `new-demo` project (the empty-folder todo-CLI run from earlier today): all 5 tasks sat
at `pending` forever, every `task_update` call was rejected with "The current task is None, not T1" (and later
T5), and the model eventually gave up, reported itself blocked in a chat message, and went idle — which from
the UI looked indistinguishable from the app being stuck (no waiting-card, just "Idle" with 0/5 done).

Root cause, traced via `.forge/transcripts/events.jsonl`: `Orchestrator._run_agent()`'s `while` loop only calls
`_start_task(task)` between calls to `agent.run()` — it can't see a task appear *during* one. `propose_plan`
populates `self.state.tasks` as a tool call from inside an in-progress `agent.run()`, but nothing in it signals
the loop to stop and re-check `next_task()`; only a successful `task_update` (or the escalator) currently sets
`context.end_turn = True` to force that. So when the model calls `propose_plan` and then, in the same
uninterrupted turn, goes on to do all the actual work (write files, run tests) without a natural stopping
point, `_start_task` never runs for any task, `current_task` stays `None` all session, and every later
`task_update` is rejected — reproduced exactly in the captured transcript (three `task_update` calls, T1, T1
again, then T5, all "current task is None").

This is a real control-flow bug (D-128's flat loop still depends on `_start_task`/`current_task` bookkeeping
being correct for `task_update`/handoff notes/per-task context resets to work at all), not a display issue —
though it manifested to the user as a UI problem (idle-looking-stuck), which is why it surfaced during Run map
testing. Fixed in `agent/orchestrator.py`: `propose_plan` now sets `context.end_turn = True` after saving the
task list, exactly mirroring how `task_update` already ends a turn — `AgentLoop.run()`'s existing
`if self.context.end_turn: return` (loop.py) safely stops after the current tool-call batch finishes (so
`propose_plan`'s own result is still correctly paired before the turn ends), handing control back to
`_run_agent`'s `while`, which then calls `_start_task` on the first pending task before the model's next reply.
`update_plan` gets the same fix, since it can equally reshuffle/rename tasks out from under an in-progress
`current_task` mid-turn — additionally, it now clears `current_task` if the updated task list no longer
contains that id, rather than leaving a stale reference that could later mismatch or misattach.

No options considered beyond this — the fix directly restores the invariant `task_update`'s check already
assumes (`current_task` reflects a real, currently-started task) using the same mechanism the codebase already
established for it. Verified: targeted tests (`-k "orchestrator or propose_plan or update_plan or task_update"`,
15 passed), full `test_orchestrator.py` + `test_m10_wiring.py` (20 passed), ruff/ruff format/mypy clean on
`orchestrator.py`. Separately, the idle-looks-stuck *display* problem this bug exposed is still open — noted
in TODO.md as its own item, since even a correctly-running requirement can legitimately go idle after a final
reply with no further action, and the UI currently gives no visual cue distinguishing that from being stuck.

### D-136 — Project-creation setup shows real phases instead of one static label · Agreed (2026-09-29)
User feedback: the "Setting up the project and its Python environment…" text on the start form (Mode B) never
changes for however long setup takes — no visibility into what's actually happening (folder/harness creation,
venv creation, `pip install pytest`), which reads as possibly-stuck for a slow install. Same problem in Mode A
("Copying the repository…", though that one at least had an unused `on_progress` callback already wired
through `copy_app_folder` — just never surfaced past the backend).

Root cause: `create_standalone_workspace`/`create_workspace` both run as one blocking call via
`asyncio.to_thread`, called directly from an HTTP POST handler (`/api/projects`) *before* the project's own
session/WebSocket exists — so there is no event bus yet to publish progress into, unlike everything else in
the running app (spec's event-sourced UI, D-119). Options considered: (a) a small polling GET endpoint
(`/api/setup-progress`) backed by a plain string on `WebSessionManager`, updated by a progress callback thread
ed through the setup calls, polled by the start form every 400ms while busy; (b) open the session/WebSocket
before setup finishes so progress could ride the existing event-bus machinery; (c) Server-Sent Events for this
one endpoint. Chosen: **(a)** — matches the requested granularity (a few coarse phase labels, not per-command
streaming or just an elapsed timer — the other two options offered and declined), smallest change, no new
transport, reuses the exact `ProgressCallback` pattern `copy_repo.py` already established for Mode A. Rejected
(b): opening a session before the workspace it's for actually exists is a bigger structural change than this
feature warrants. Rejected (c): a new transport mechanism for one short-lived, low-frequency status value.

Implementation: `modeb/workspace.py`'s `create_standalone_workspace` gains an `on_progress: SetupProgressCallback
| None` param, called at its three real phase boundaries ("Creating workspace folders…", "Creating the Python
environment…", "Installing the test runner (pytest)…"). `WebSessionManager` (`web/manager.py`) gains a plain
`setup_progress: str | None` field, set by a callback passed into both `new_workspace` (reusing the existing
`copy_repo.py` `on_progress(count, path)` callback, formatted as "Copying the repository… (N files: path)")
and `new_standalone`, and cleared in a `finally` once setup finishes either way. New `GET /api/setup-progress`
(`web/server.py`) returns `{"phase": manager.setup_progress}` — covered by the existing security middleware
like every other route, no separate auth wiring needed. `Home.tsx`: the static label is replaced by a `setupPhase`
state string, updated on submit and by a 400ms `setInterval` poll of the new endpoint while `busy`, cleared
when the request settles either way.

Verified: ruff/ruff format/mypy clean on the three touched backend files; `npm run build` clean; targeted
tests (`test_contracts.py`, `test_modeb.py`, `test_learning.py`, `test_live_modeb.py`'s non-live cases) — all
existing `create_standalone_workspace(...)` call sites pass at most 3 positional args, so the new `on_progress`
param (a plain optional positional-or-keyword param appended last, defaulting to `None`) doesn't break any of
them.

### D-137 — Frontend support (React/Angular/CSS) scoped down to a React + Mode A proving slice first · Agreed (2026-09-29)
User asked for Forge to build a full 3-tier app on its own — frontend designed from scratch (not just
extending an existing repo), verified the way this assistant verifies its own UI work (build/lint/test plus
headless-browser checks), and broad tech coverage (React, Angular, CSS) via one tech-agnostic layer designed
up front, matching Claude Code's generality.

Assessed against the current codebase: Forge is Python-specific at multiple layers, not just "the tools happen
to default to Python" — `workspace/pyenv.py`/`modeb/workspace.py` (venv creation, `pip install`, interpreter
discovery), `verify/ladder.py` (py_compile, ruff/flake8/mypy config detection, pytest output parsing, a Python
import-graph walk for targeted test selection — see `_affected_modules`/`targeted_tests`), and Mode B's whole
host-profile/contract model (`modeb/profile.py`; D-129's Contracts panel) which is built around stubbing the
host's Python import paths and symbols, a concept with no direct analogue for a frontend being designed from
nothing (there's no "host" to stub against). None of this transfers to JS/TS/Angular even as a shared base
class beyond the outermost `StepResult`/`LadderReport` shapes.

Options considered for how to proceed: (a) design the full tech-agnostic abstraction (a "verify rung," an
"environment," a "host contract" concept general enough for Python + React + Angular + CSS) before writing any
frontend-specific code, as its own spec-writing pass; (b) scope down to a single proving slice — React support
in Mode A only (extending an existing repo, not designing from scratch) — get a real, working, tested ladder
and tool set for it, and only then design the general abstraction from two real data points (the existing
Python ladder and the new React one) instead of from speculation about ecosystems Forge hasn't touched yet;
(c) build React and Angular support in parallel from day one.

Chosen: **(b)**, per the user ("For now lets make the way you suggest") after being shown the honest scale of
the full request — a genuinely stack-agnostic layer answering "what is a verify rung/environment/contract
across ecosystems with fundamentally different shapes" up front would be a multi-month design program built
on guesses, since TypeScript has no separate compile step the way Python does, Angular's CLI bundles
build+test+lint in ways that don't decompose like `ruff`/`mypy`/`pytest`, and Node's install/lockfile model
differs from a venv in ways that would bias any abstraction designed before real evidence exists. This mirrors
how Forge's own architecture was actually built: D-128's flat-loop rewrite was itself a correction made after
live use showed the original phased-pipeline design was wrong — abstracting from real, working code beats
abstracting from speculation. Rejected (a): high risk of locking in wrong abstractions with no working code to
validate them against. Rejected (c): doubles the unproven design surface before either stack has a single
working milestone.

**What phase 1 (React + Mode A) covers, explicitly**: extending an *existing* React app already in the user's
repo — Forge reads its existing `package.json`/build tooling/test setup the way it already reads a Python
repo's `pyproject.toml`/`ruff`/`mypy` config in `VerifyLadder._configured`, rather than inventing a frontend
architecture from nothing. Browser-verification (headless, Playwright — the same tool Forge's own
`tests/test_web_e2e.py` already uses to test Forge's UI) is in scope for phase 1, per the user's answer to the
frontend-verify design question, not deferred.

**Explicitly deferred to a later, separately-designed phase 2** (not decided now, not scoped): Angular support;
any other framework; Mode B (designing a frontend from scratch with no existing repo/host to read conventions
from) for the frontend side; the general tech-agnostic verify-rung/environment/contract abstraction itself.
Each of those still needs its own options-and-recommendation discussion before being built, per this file's
standing rule for hard-to-reverse choices (new tool interfaces, folder layout, prompt structure) — this entry
records only the decision to scope down and start with React + Mode A, not a design for that slice itself,
which is the next thing to work through.

### D-138 — React + Mode A design: node environment, verify ladder shape, smoke-check cadence · Agreed (2026-09-29)
First concrete design pass for [D-137] phase 1. Grounded in what already exists rather than assumed: Mode A's
`WorkspaceInfo.python_env`/`workspace/pyenv.py` (venv detection, never copies the venv itself),
`verify/ladder.py` (Python-only rungs: compile/lint/typecheck/targeted-tests/full-suite, first failure stops
the climb, config-detected via `_configured` reading the repo's own `pyproject.toml`/dedicated files — Forge
never introduces a tool the repo doesn't already use), and `find_app_folder_candidates` (already excludes
`node_modules` when scanning for the Python app folder — pre-existing awareness of adjacent JS folders, never
acted on). Also found: `tools/browser.py` already has a working, generic Playwright-backed browser tool
(headless Edge/Chrome/Chromium, console/network capture, accessibility snapshots, localhost-only guard) built
for checking Forge's own Swagger UI — nothing in it is backend-specific, so it needed no new infrastructure to
reuse for verifying a React app renders, only a new call site in the React verify ladder.

**Node environment**: `WorkspaceInfo` gains a sibling `node_env: NodeEnvironment | None` field (new
`workspace/nodeenv.py`, mirroring `pyenv.py`'s shape: detect `package.json`, the package manager via lockfile
presence — npm/yarn/pnpm — and the node binary) rather than folding it into `python_env`, since the two are
independent environments with different env-var shapes (`PythonEnvironment.command_env()` sets
`PYTHONPATH`/`VIRTUAL_ENV`; Node needs none of that) and a workspace may have either, both, or neither.

**`node_modules` handling**: excluded from Mode A's repo copy (`copy_app_folder`'s ignore rules extended the
same way `.venv`/`.git` already are), with `npm install` run fresh in the workspace copy through the normal
approval gate — chosen over copying an existing `node_modules`, per the user, matching how Python already
works (the venv itself is never copied; Mode B installs pytest fresh) and avoiding copying a huge, fragile
tree with native bindings/symlinks that may not survive relocation.

**Verify ladder shape for React/TS** (`verify/react_ladder.py`, new — not a subclass of `VerifyLadder`, since
the rungs don't decompose the same way; see below): typecheck (`tsc --noEmit`) → lint (ESLint) → unit tests
(Jest or Vitest, whichever the repo already has) → build (`npm run build`/`vite build`) → browser smoke check
(new rung, checkpoint-only — see below). Two structural differences from the Python ladder, noted so they
aren't mistaken for oversights later: (1) TS has no separate "compile" step the way Python's `py_compile` is —
`tsc` covers parse+typecheck in one rung; (2) a build rung has no Python equivalent (Python code doesn't need
bundling to "work"), but is a real distinct failure mode for React (e.g. a broken asset import that no
typecheck/lint/test rung would catch).

**Smoke-check cadence**: runs only at task/export checkpoints, not on every `verify` call — chosen per the
user, mirroring how Python's own slow rung (the full test suite, `full=True`) is likewise reserved for
checkpoints rather than run on every targeted-verify call, keeping fast iteration fast while still catching
real rendering failures before a task is marked done.

**Vite**: explicitly in scope as a supported build tool (alongside CRA/webpack-based setups) for the React
ladder's build rung — `nodeenv.py`'s environment detection must read the actual `scripts.build`/`scripts.test`
commands from the repo's own `package.json` (Vite projects typically run `vite build`, CRA `react-scripts
build`) rather than assuming one bundler's command names, the same "read the repo's own config, never impose
a convention" principle the Python ladder's `_configured` already follows for ruff/mypy.

**Demo UX (client-side dummy data, in-memory backend data)**: raised by the user as a follow-up — fast-to-demo
apps that store dummy data in the browser (localStorage/sessionStorage/React state) before a real backend
exists, and a Python-side in-memory data layer that can later be swapped for a real DB-backed one. Split into
two decisions:
- **Frontend client-side demo data**: no new Forge tooling or scaffold. This is ordinary application code the
  model already knows how to write with its own judgment (localStorage, in-memory React state, whatever fits
  the requirement) — per the user ("Just as claude-code would do"), the same way this assistant writes such
  code today with no dedicated pattern imposed. Nothing to build.
- **Python-side in-memory data layer**: per the user ("Both options should be available as per Forge decision
  or user requirements"), Forge is not locked into one mandated shape. Two available approaches, chosen by
  judgment based on the requirement (mirroring how verification cadence and plan-writing are already
  judgment-based per D-128/D-132, not forced gates): (a) a repository-pattern interface (a Python
  Protocol/ABC with get/list/create/update/delete) with an in-memory implementation for demos and a real
  DB-backed one built the same way Forge already builds DB code — appropriate when the work is likely to
  graduate to a real backend later, since swapping is one line of wiring, not a rewrite; (b) a simpler
  flag/in-memory-dict approach for a genuine one-off demo with no stated intention of becoming real. Forge
  picks between them the way it already picks a written-plan-or-not (D-128): judgment, or the user says which
  they want. No new tool or scaffold needed for either — both are within what the model can already write;
  this is guidance for the model's judgment (to be added to a relevant prompt/instructions file), not new
  product surface.

**Targeted-test detection**: Python's `targeted_tests`/`_affected_modules` does real import-graph analysis.
For React, proposed starting point is simpler — colocated test files (`Button.tsx` → `Button.test.tsx` in the
same folder) plus direct relative-import matching — deferring import-graph depth until evidence (from real use)
shows it's needed, consistent with [D-137]'s "build from evidence, not speculation" reasoning. Not yet
implemented; flagged here as the chosen starting approach, to be built alongside the rest of this ladder.

Not yet decided/built in this pass (tracked as the next steps under this same phase): the actual
`workspace/nodeenv.py` module, `verify/react_ladder.py`'s rungs, the `copy_app_folder` ignore-rule addition,
and how `VerifyLadder`'s caller (`orchestrator.py`'s `_run_tests`, the `verify`/`run_tests` tools) picks which
ladder(s) to run for a workspace that may have a Python backend, a React frontend, or both.

**Resolved while starting implementation**: the `verify`/`run_tests` tools (`tools/verify.py`) call
`VerifyLadder(context)` generically — the model just says "verify," with no notion of which stack it touched.
`VerifyLadder.run()` becomes a small dispatcher: it looks at which changed files exist (reusing
`workspace/output.py`'s already-stack-agnostic `compute_changes`, the same way `changed_python_files` already
filters that list to `.py`) — `.py` files route to the existing Python ladder, `.ts`/`.tsx`/`.jsx`/`.css` files
route to the new React ladder — and runs whichever stack(s) were actually touched, combining their reports
into one `LadderReport`. A workspace with only a Python backend touched behaves exactly as today (no React
ladder invoked); a task touching both a new backend endpoint and its frontend wiring runs both ladders and
reports both — matching the earlier "one unified workspace, one task board" choice rather than needing the
model to know or declare which stack it's verifying.

### D-139 — D-137/D-138 phase 1 built: nodeenv, react_ladder, VerifyLadder dispatcher · Decided (2026-09-29)
Implements the design D-138 already agreed. `workspace/nodeenv.py` (new): `NodeEnvironment` (pydantic v2,
mirrors `PythonEnvironment`'s shape) with `node`, `package_manager` (npm/yarn/pnpm, from lockfile presence,
npm default), `app_dir`, and `install_command`/`build_command`/`test_command`/`lint_command`/
`typecheck_command` read from the app's own `package.json` "scripts" section (never assumed literally —
`typecheck_command` accepts either `typecheck` or `type-check` as the script name, since both are common).
`detect_node_environment(app_dir)` returns `None` when there's no `package.json` or no `node` on PATH
(`shutil.which`), the same "nothing to run against" contract as `setup_python_environment`.
`find_node_app_candidates` mirrors `find_app_folder_candidates`, ranking folders with a `build`/`start` script
first. `WorkspaceInfo.node_env: NodeEnvironment | None` added next to `python_env`; `create_workspace` detects
it in the same `app_subfolder` the user already gave (monorepo auto-discovery of a separate frontend folder is
explicitly deferred, per the task scope). `node_modules/` was already in `ignore.py`'s `DEFAULT_EXCLUDES`
(pre-existing, per D-138's own finding) — no change needed there.

`verify/react_ladder.py` (new, not a `VerifyLadder` subclass, per D-138): `ReactVerifyLadder` runs typecheck
(`npx tsc --noEmit`, skipped without a `tsconfig.json`) → lint (the repo's own lint script, else `npx eslint .`,
skipped without any of `.eslintrc*`/`eslint.config.*`/an `eslintConfig` key) → unit tests (Jest or Vitest,
detected from `package.json` `dependencies`/`devDependencies`; skipped if neither is present; a regex on the
Jest "Tests: N passed, M total" / Vitest "Test Files N passed (M)" summary line, deliberately simple per D-138)
→ build (the repo's own build script; skipped if none). Reuses `StepResult`/`LadderReport` from `ladder.py`
rather than redefining them, so both ladders combine into one report. The browser smoke-check rung is
deliberately NOT here — left as a comment pointing at `Orchestrator._export`/task completion as its future
call site, using the existing `tools/browser.py` (D-083) — not built in this pass.

`verify/ladder.py`: `VerifyLadder.run()` is now a small dispatcher. The former body became `_run_python`
(unchanged logic). `run()` always runs `_run_python` first (unchanged call, unchanged return on failure — the
"first failing rung stops the climb" behaviour is preserved exactly); only when `workspace.info.node_env is
not None` AND `changed_frontend_files` (new helper, mirrors `changed_python_files`, filtering
`compute_changes` to `.ts`/`.tsx`/`.js`/`.jsx`/`.css`) is non-empty does it additionally instantiate
`ReactVerifyLadder` and append its steps. A Python-only workspace (no `node_env`) never even imports
`react_ladder.py` (the import is local to that branch) and produces byte-identical `LadderReport`s to before —
verified by a dedicated regression test that monkeypatches `ReactVerifyLadder` to raise if instantiated and
confirms the ordinary Python-only run never touches it.

Verified: `ruff check`/`ruff format --check` clean on all five touched/new source files; `mypy src/forge`
clean (153 files, no new errors); new `tests/test_nodeenv.py` (9 tests: detection, lockfile-driven package
manager selection, missing package.json/node binary, script-name discovery, candidate ranking) and
`tests/test_react_ladder.py` (9 tests: each rung's skip condition, a lint/build/test rung actually running via
a monkeypatched `execute`, and three dispatcher tests — Python-only never instantiates the React ladder,
node_env-present-but-nothing-changed also skips it, and a real frontend change runs and combines it) all pass.
Full non-live suite (`pytest -q -k "not live and not pg" tests/ --ignore=tests/test_web_e2e.py`): 455 passed,
46 deselected, no regressions. `scripts/check_secrets.py`: 0 findings.

Left open for phase 2 (explicitly out of scope here, per D-137): the browser smoke-check rung's actual
call site and cadence wiring; `npm install`/yarn/pnpm-install automation (the agent runs it itself via the
existing `run_command` tool, through the normal approval gate — consistent with how Mode B already leaves
`pip install pytest` to an approved shell command); Angular; Mode B frontend support; monorepo auto-discovery
of a frontend folder separate from the Python `app_subfolder`; real import-graph-based targeted-test selection
for React (the colocated-test/relative-import starting point from D-138 is likewise not yet built — the
current React ladder always runs its unit-test rung against the whole test command, not a targeted selector,
matching how `run()`'s dispatcher only decides WHICH ladders run, not per-ladder targeting depth).

**Follow-up**: D-138's "Python-side in-memory data layer" judgment guidance (repository-interface vs. plain
in-memory dict, chosen by judgment or the user's stated intent) is added verbatim to both `agent/prompts/
system.md` (Mode A) and `agent/prompts/system_modeb.md` (Mode B) — a short bullet next to the existing
database-handoff rule in each, since it's the same kind of judgment call ("hand off what you can't run") as
what's already there. No code change; prompt-only, per D-138's own framing ("guidance for the model's
judgment... not new product surface"). Verified both templates still `.format()` correctly (no stray braces
introduced) and `scripts/check_secrets.py` stays clean.

### D-140 — Browser smoke-check rung built: call site, mechanism, pass/fail/skip · Decided (2026-09-29)
Builds the piece D-138 designed and D-139 deliberately left as a comment: the checkpoint-only browser
smoke check for a React frontend, wired into `Orchestrator._export()` (agent/orchestrator.py).

**New module, not inlined into orchestrator.py**: `agent/frontend_smoke.py` (`run_frontend_smoke_check`,
`render_smoke_check_section`), following the existing pattern of `orchestrator.py` delegating related
concerns to sibling modules (`learning_hooks.py`, `reports.py`) rather than growing the already-large
`_export()` method in place.

**Where it hooks in**: `_export()` runs it only when `workspace.info.node_env is not None` — a Python-only
workspace never imports or calls into `frontend_smoke.py` at all (regression-tested, same discipline as
D-139's Python-only VerifyLadder guard). It is informational only, per D-132: the result is appended as a
`## Frontend smoke check` markdown section to the export report, exactly mirroring the existing
`## Restructure check` block's style (URL checked, PASSED/FAILED/SKIPPED, a short error excerpt on
failure) — it never raises, blocks, or fails `_export()` itself.

**Starting the app**: `NodeEnvironment` gains a `dev_command` field (`workspace/nodeenv.py`), read from the
repo's own `package.json` scripts in order `dev` → `start` → `preview` (never a literal `npm run dev`
assumed, the same rule D-139 already applied to build/test/lint/typecheck). `frontend_smoke.py` starts it as
a background process directly via `tools/powershell.py`'s `build_script`/`start_process` — the same
mechanics `tools/background.py`'s `StartBackground.run()` uses — rather than going through the `Tool`
wrapper or `BackgroundManager`, since this is a system-triggered check with no model tool call and no
approval to ask for. A free port comes from `tools/background.py`'s existing `free_port()`; readiness is
polled with the same module's `port_open()` (a `{port}`-style timeout loop, 45s default) rather than
`StartBackground`'s own ready-wait helper, since there is no `BackgroundProcess` registered in the session's
`BackgroundManager` for this one-off check to reuse that helper against.

**Checking the app**: once the port is open, `tools/browser.py`'s existing `BrowserSession` (D-083) loads
the URL directly (`page.goto`), reusing its already-wired `console` capture for `[pageerror]` entries — no
new browser infrastructure, exactly as D-138 anticipated.

**Pass/fail/skip, decided for v1**: PASS = an HTTP response under 400, zero `[pageerror]` console entries,
and the page body has at least 40 characters of visible text (`page.inner_text("body")`) — a minimal
"isn't blank" bar, not a DOM-structure heuristic, per the task brief's "don't over-engineer this" guidance.
FAIL = a 4xx/5xx response, any `[pageerror]` entry, or a near-empty body — these are real problems worth
surfacing but must never stop export. SKIP = everything that must never count as a frontend defect: no
dev/start/preview script in the repo, the process failing to start, the port never opening within the
timeout, or no browser available at all (Edge/Chrome/bundled Chromium all failing to launch, the same
fallback chain `BrowserSession.ensure()` already tries) — each produces a `SmokeCheckResult(skipped=True)`
with a one-line reason, mirroring `verify/ladder.py`'s `StepResult.skipped` concept and wording style even
though this isn't a `StepResult`.

**Cleanup**: the dev server started for this one check is always stopped right after (`kill_tree` in a
`finally`), regardless of outcome — it is never registered in the session's long-lived `BackgroundManager`,
so it needs no wait for `SessionHost`'s end-of-session `stop_all()` and nothing is left running once
`_export()` returns.

**Left out of scope for this pass** (not a regression, a deliberate v1 boundary): a smarter "is this page
meaningfully rendered" heuristic beyond the body-text-length check; retrying a flaky dev-server start;
running the smoke check at task-completion checkpoints in addition to export (D-138 named both task and
export checkpoints — this pass wires export only, the more clearly-bounded of the two; task-checkpoint wiring
is left for evidence from real use, consistent with D-137's "build from evidence" principle); and surfacing
the smoke-check result anywhere in the UI beyond the export report text (no new event type, no Run map node).

Verified: `ruff check`/`ruff format --check` clean on all touched/new files (`agent/frontend_smoke.py`,
`agent/orchestrator.py`, `workspace/nodeenv.py`, `verify/react_ladder.py`'s updated comment,
`tests/test_frontend_smoke.py`); `mypy src/forge` clean (154 files, no new errors). New
`tests/test_frontend_smoke.py` (13 tests): `_export()` regression guard for a Python-only workspace (the
check function is never called), `_export()` wiring for pass/fail/skip sections with a mocked check
function, and `run_frontend_smoke_check` itself exercised in isolation with mocked `start_process`/
`_wait_for_port`/`BrowserSession` (no real Node/Chromium needed). Targeted run (`-k "orchestrator or export
or react_ladder or nodeenv"`, excluding `test_web_e2e.py`): 42 passed. Full non-live, non-pg suite: run at
milestone end alongside `scripts/check_secrets.py` (0 findings).

### D-141 — Phase 2 design: Mode B frontend from scratch (no host to conform to) · Agreed (2026-09-29)
User chose Mode B frontend-from-scratch as phase 2's first direction (over Angular support or small phase-1
gap fixes). Clarified first: Mode B's existing model (`modeb/profile.py`'s `HostProfile`, the interview,
CONVENTIONS/INTERFACES documents, exemplar snippets) exists to make Forge's *output* integrate into a real
host codebase it never sees — there is a host to conform to, just not a visible one. A "frontend from scratch"
request is structurally different: per the user, this is a brand-new standalone frontend (like the existing
todo-CLI standalone demo, but a web UI) with **no host at all** to integrate with or interview about. This
rules out reusing the host-profile/interview/contract machinery for the frontend side — that system solves a
different problem than the one being asked for here.

**Node/React setup is lazy, not eager.** `modeb/workspace.py`'s `create_standalone_workspace` unconditionally
sets up a Python venv today because every Mode B project needs the harness; a React frontend is not similarly
guaranteed needed by every standalone project, so workspace creation stays Python-only. Node environment setup
happens later, on demand, the first time the model decides a requirement needs a frontend — via a new tool
(name TBD at implementation, e.g. `setup_frontend`) that scaffolds a `project/frontend/`-style subfolder,
installs dependencies, and populates `WorkspaceInfo.node_env` (reusing phase 1's `NodeEnvironment` model from
`workspace/nodeenv.py` unchanged — it was built detection-based, not Mode-A-specific, so it transfers as-is
once populated by scaffolding instead of detected from an existing repo).

**Stack choice is per-project judgment, not one fixed default.** Options considered: (a) one fixed default
(Vite + React + TypeScript + plain CSS/CSS Modules) every time, for predictability and a verify ladder that
always knows what it's dealing with; (b) Forge decides per-project based on what the requirement actually
needs (a simple demo gets a plain setup; something that calls for a component library gets one). Chosen:
**(b)**, per the user, consistent with how plan-writing and verification cadence are already judgment-based
rather than forced (D-128/D-132) — this is the same kind of call. Consequence: the verify ladder must stay
stack-*detection*-based (already true of phase 1's `react_ladder.py`/`nodeenv.py` — they read the actual
`package.json`, never assume one toolchain), not stack-*assumption*-based, so this choice adds no new
constraint on what phase 1 already built; it only means the scaffolding tool can't hardcode one fixed
`package.json` template and call it done — it needs to generate (or invoke a scaffolder for) whatever stack
the model decides fits, and phase 1's ladder picks it up from the result either way.

**Not yet decided in this pass** (next implementation step): the exact scaffolding mechanism (run `npm create
vite@latest` live, which needs network access and behaves like any other install the user must approve, vs.
Forge hand-writing a minimal scaffold itself to avoid a network dependency — each has real trade-offs: the
former matches real-world convention and gets Vite's own templates for free but fails offline or behind a
restrictive proxy; the latter works offline but means Forge maintaining its own scaffold templates); the exact
new tool's name/interface; how `HostProfile`/`sensitive_terms` still apply (Mode B's redaction/sensitive-term
rules are about the user's own business domain, not about a host codebase, so they likely still apply
unchanged to a from-scratch frontend — needs confirming during implementation, not assumed).

**Resolved**: scaffolding runs the real `npm create vite@latest` (or the equivalent for whatever stack the
model decides on, per the per-project-judgment choice above), through the normal shell-command approval gate
like any other install — chosen over Forge maintaining its own offline scaffold template, per the user.
Accepted trade-off: this fails if the machine is offline or behind a restrictive proxy at scaffold time, the
same risk class Forge already accepts for every other `npm install`/`pip install` it depends on (Mode B's own
`pip install pytest`, D-111, already carries this same risk and is accepted); no special-casing needed for
frontend scaffolding specifically, it's ordinary install-time risk. Forge takes on no template-maintenance
burden as a result.

### D-142 — D-141 phase 2 piece built: `setup_frontend` tool, Mode B frontend-from-scratch scaffolding · Decided (2026-09-29)
Implements D-141's design. New `tools/frontend_setup.py` (`SetupFrontend`, tool name `setup_frontend`,
~150 lines, well under the module-size guideline).

**Args, chosen interface**: `folder: str` (default `"frontend"`), `framework: Literal["react", "vue",
"svelte", "preact", "vanilla", "other"]` (default `"react"`), `typescript: bool` (default `True`), and
`create_command: str | None` — a free-form escape hatch. The common case (`framework` != `"other"`) is
translated into `npm create vite@latest . -- --template <name>[-ts]`, matching Vite's own real template
names, so the model never has to spell out the scaffold invocation for the case D-141 said to make easy.
`framework: "other"` requires `create_command` (a pydantic `model_validator`, so a missing command is
rejected before any shell call, not discovered after) — this is the path to Angular's own CLI or any
scaffolder Vite doesn't template, without Forge hand-listing every ecosystem's invocation. Chosen over pure
free-text-only (would make the common React+TS case more typing for every call) and over structured-only
with no escape hatch (would block Angular/anything else entirely, contradicting D-141's "no one fixed
default stack" — every alternative considered was rejected for narrowing the very flexibility D-141 asked
for).

**Mode-B-only gating**: matches the existing pattern exactly, not a new one. `tools/registry.py`'s
`default_tools()` has no Mode-B conditional today (confirmed by reading it) — Mode-B-only tools instead live
in `tools/modeb.py` and are added via `modeb_tools()`, which `engine/session_host.py`'s `_build_agent` only
includes `if workspace.mode_b`. `SetupFrontend` is registered by adding it to `modeb_tools()`'s return list
in `tools/modeb.py` — in Mode A it is never constructed, let alone offered to the model. As defense in depth
(the same style `ProfileSearch`/`ProfileRead` already use, checking `_profile(context) is None` even though
they're only ever registered in Mode B), `run()` also checks `context.workspace.mode_b` itself and returns
`ToolResult(ok=False, ...)` if it's ever called in Mode A by some future wiring path.

**Scaffold mechanism and node_env wiring**: `run()` creates the empty target folder, builds the scaffold
command, and calls the existing `tools/shell.py` `execute()` — the identical function `run_command`/
`python_run` use — with `cwd` set to `args.folder` (host-relative; `Workspace.path_of` resolves it under
`project/` in Mode B, the same convention `run_command`'s own `cwd` argument already follows). This goes
through the ordinary shell/approval flow, per D-141, not a bypass. On a non-`ok` result, the tool returns
`ok=False` with the scaffold's own error output and touches `WorkspaceInfo` not at all. On success, it calls
`detect_node_environment()` (phase 1's, unmodified) against the new folder; if that returns `None` (the
scaffolder exited 0 but left no real `package.json`/node found — a command that lied about succeeding), the
tool still returns `ok=False` rather than claiming success with nothing to show for it. Only when detection
succeeds does it set `workspace.info.node_env` and call `workspace.save_info()` — the same persistence path
every other `WorkspaceInfo` mutation in the codebase already uses (`create_standalone_workspace` itself
calls it the same way), so a reopened workspace sees the same `node_env` (verified by a dedicated test that
reopens the workspace after a successful scaffold).

**Idempotency, chosen**: reject a second call outright rather than silently overwriting — checked two ways:
`workspace.info.node_env is not None` (a frontend was already wired up, regardless of folder name) and the
target folder already existing and non-empty (covers a folder created outside `setup_frontend`, e.g. by hand
or a different tool). Both return `ok=False` with a message telling the model to work in the existing folder
or ask the user before replacing it. Chosen over silent overwrite (would risk destroying a working
scaffold/dependencies over one bad tool call) or a `force: bool` flag (adds an untested destructive path for
a case the task brief didn't ask for; the model can already just ask the user, which is the documented
answer for anything Forge can't decide alone, D-011).

**Sensitive-terms/redaction, confirmed not assumed**: read `agent/loop.py`'s `_run_one` — `flag()`
(`safety/redact.py`) runs on every tool's `content` after every call, unconditionally, keyed off nothing
tool-specific. `ToolContext.sensitive_terms` and the profile-based redaction Mode B tools use
(`default_redactor`/`profile.clean`) are likewise applied at the loop/profile level, not opted into per
tool. `setup_frontend`'s own output (shell text from `npm create`, package names, folder paths) therefore
needed zero special handling to be covered — confirmed by inspection, not guessed; no code change was
needed or made for this.

**Prompt guidance**: one bullet added to `agent/prompts/system_modeb.md`, next to the existing in-memory-
data-layer judgment bullet (D-139's follow-up), in the same terse style: use `setup_frontend` instead of
hand-writing `package.json`/build config when a requirement needs a UI and none exists yet.

**Left open, not built in this pass** (see TODO.md's D-141/D-142 entry for the full list): no UI-component-
library auto-setup beyond whatever the chosen scaffolder's own template provides; Angular's own CLI is only
exercised through the `create_command` escape hatch in a unit test with a mocked shell call, never against
the real Angular CLI; real npm/network was never exercised (per the task brief, tests mock the shell call);
no monorepo-layout question actually arose — a scaffolded frontend just lands at `project/<folder>/` beside
the Python code, which the Mode B harness already treats as ordinary project content.

Verified: `ruff check`/`ruff format --check` clean on `tools/frontend_setup.py`, `tools/modeb.py`,
`tests/test_frontend_setup.py`; `mypy src/forge` clean (155 source files, no new errors). New
`tests/test_frontend_setup.py` (7 tests, `npm create` mocked throughout): unusable outside Mode B, a
successful scaffold populates and persists `node_env` (with the real translated Vite command asserted), a
free-form `create_command` is passed through verbatim, `framework: "other"` without `create_command` is
rejected by the pydantic validator before any shell call, an already-set-up workspace rejects a second call
without touching the shell, a failing scaffold command returns `ok=False` and leaves `node_env` untouched and
reopenable cleanly, and a scaffolder that exits 0 but leaves no detectable node app is not treated as success.
Targeted run (`pytest -q -k "modeb or frontend_setup or nodeenv" --ignore=tests/test_web_e2e.py`): 36 passed,
480 deselected, no regressions to existing Mode B/nodeenv tests. `scripts/check_secrets.py`: 0 findings.

### D-143 — Dedicated Angular support in the verify ladder (structured, not fully agnostic) · Agreed (2026-09-29)
User asked whether Forge should become fully technology-agnostic like this assistant (no structured verify
ladder — the model just runs whatever command it decides and reads raw output). Two different things were
disentangled: (1) adding dedicated, tested support for more stacks within Forge's existing structured-ladder
system; (2) dropping the ladder concept for frontend work entirely. Chosen: **(1)**, per the user — Forge's
ladder (parsed pass/fail, `task_update`'s "no passing test since last edit" gate) is a deliberate property for
a less-supervised agent, not incidental scaffolding; giving it up for arbitrary-stack generality was judged a
real regression risk, not a neutral simplification, since Forge runs with materially less live supervision than
an interactive session of this assistant and leans on structured signals to know when to trust its own claims.

**What's actually needed for Angular, found by reading `workspace/nodeenv.py` and `verify/react_ladder.py`
in full before designing**: `NodeEnvironment`/`nodeenv.py` need **no changes** — detection already reads the
repo's own `package.json` scripts generically (build/test/lint/typecheck/dev, whatever names the repo uses),
and a standard Angular-CLI project exposes exactly these as npm scripts (`ng build`/`ng test`/`ng lint` wrapped
by `package.json`), so it already works for Angular's shape today. The real gap is `react_ladder.py`, which has
three React/TS-specific assumptions:
1. **Typecheck** hardcodes bare `npx tsc --noEmit`. An Angular project typically has multiple
   `tsconfig.*.json` files (app/spec/e2e) and template type-checking (Angular's compiler, `strictTemplates`)
   that plain `tsc` doesn't exercise — an Angular-aware typecheck rung should prefer the Angular CLI's own
   build/typecheck path when `angular.json` is present, not bare `tsc`.
2. **Test-framework detection** only recognises Jest/Vitest (`_test_framework`). Angular's default is
   Karma+Jasmine (`ng test`), though newer Angular versions increasingly support Jest — both need detecting.
3. **The dangerous one, found while designing this, not yet a bug in production**: `ng test`'s default
   behaviour is watch mode against a REAL browser, not a one-shot CI run. Naively running `node_env.test_command`
   (which resolves to the repo's plain `npm run test` → `ng test`) risks hanging indefinitely waiting for a
   watcher/browser rather than exiting — the ladder rung must append Angular's own CI-mode flags
   (`--watch=false --browsers=ChromeHeadless`, or read the repo's own CI test script if it defines one
   separately, the same "prefer the repo's own convention" rule already used everywhere else) rather than
   invoking the bare test script and assuming it behaves like Jest's default one-shot run.

Lint and build are expected to work unchanged (Angular's lint is still an ordinary npm script; `ng build` needs
no special handling), but this needs confirming during implementation, not assumed, the same discipline
D-138/D-141 already applied to their own open questions.

Not yet decided in this pass (implementation's job): whether Angular gets a fourth ladder module
(`angular_ladder.py`, parallel to `react_ladder.py`) or `react_ladder.py` grows Angular-aware branches
internally — given `react_ladder.py`'s own docstring already explains why it isn't a `VerifyLadder` subclass
("these rungs don't decompose the same way"), a similar "Angular's rungs don't decompose the same way as
React's" argument likely favours a separate module again, but this is left for whoever implements it to judge
once the exact shared-vs-different rung logic is worked out in code, not speculated here.

### D-144 — D-143 implemented: dedicated Angular verify ladder, new module, dispatcher routes by angular.json · Decided (2026-09-29)
Implements D-143's design. New `verify/angular_ladder.py` (`AngularVerifyLadder`, `is_angular_project`), not
Angular-aware branches inside `react_ladder.py`.

**Structural choice**: separate module, per the analogy D-143 itself named — `react_ladder.py`'s own docstring
explains it isn't a `VerifyLadder` subclass because React's rungs don't decompose the same way Python's do;
the same argument applies one level down: Angular's typecheck and test rungs don't decompose the same way
React's do (Angular typecheck goes through the CLI's build/compiler, not bare `tsc`; Angular's default test
runner needs CI-mode flags appended or it hangs, with no React/Jest/Vitest equivalent). Branching every rung
five ways inside `react_ladder.py` would have reintroduced exactly the shape-mismatch problem D-138 used to
justify a dedicated module in the first place. Lint and build ARE thin, framework-agnostic wrappers (confirmed
below) with no Angular-specific logic to justify their own functions, so `AngularVerifyLadder` still has its
own `_lint`/`_build` methods (mirroring `ReactVerifyLadder`'s shape) but their bodies are functionally
identical — duplicated rather than shared via inheritance, since a shared base class for two near-identical
methods out of four would add more indirection than the few lines saved. `_read_package_json` and
`_parse_js_test_summary` ARE reused directly from `react_ladder.py` (plain function imports) rather than
duplicated, since those two are pure, framework-agnostic helpers (JSON reading, regex summary parsing) with
no React-specific assumptions baked in.

**Typecheck, chosen invocation**: `ng build` (via `node_env.build_command`, falling back to `npx ng build` if
the repo has no `build` script), with `--configuration=development` appended when `angular.json` declares
that configuration name (read generically from every project's `architect.build.configurations`, not assuming
the default CLI project name). Reasoning: the Angular CLI has no dedicated typecheck-only command (checked —
`ng build`/`test`/`lint`/`e2e`/`serve` are the CLI's build-related commands; no separate `ng typecheck`);
`ng build` runs the full Angular compiler (ngc) against the app's real tsconfig, which does template
type-checking (`strictTemplates`) that bare `tsc --noEmit` skips entirely — this was the actual defect D-143
found in `react_ladder.py`'s hardcoded `npx tsc --noEmit`. `--configuration=development` is preferred over the
(slower, minifying) production default when available, purely to keep the rung fast; it still only checks for
errors, since the separate `_build` rung below performs the real (typically production) build. Trade-off
accepted: this rung is slower than a real `tsc --noEmit` pass would be (a full build vs. a type-check-only
pass) — no faster CLI-native alternative exists today; noted as a possible future gap if Angular ever ships a
lighter typecheck-only command.

**Test-framework detection**: Karma is detected via `karma`/`jasmine-core` in dependencies OR a
`karma.conf.js` file present (covers a repo declaring Karma only as a transitive/global dependency); Jest is
detected via `jest` in dependencies (Angular's newer versions support swapping in Jest, checked and confirmed
this is a real, documented Angular CLI builder option, not speculative).

**THE critical rung — Karma CI-mode flags, always appended, never optional**: for a Karma-detected project,
the test rung is `{node_env.test_command or "npx ng test"} --watch=false --browsers={launcher}`, NEVER the
bare `test_command` — confirmed via Angular's own documented `ng test` default (watch mode, real-browser Karma
launcher, does not exit on its own), a genuine hang risk if the ladder ran it unmodified, exactly as D-143
flagged. Launcher name: prefers a custom launcher name found in the repo's own `karma.conf.js`
(`customLaunchers: { <Name>: { base: 'ChromeHeadless', ... } }`, read via a regex on the raw file text rather
than executing the JS config, since Forge does not run arbitrary repo JS to introspect config — commonly
`ChromeHeadlessCI`, which repos define to add `--no-sandbox` for CI containers) — falls back to Forge's own
generic `ChromeHeadless` when no `karma.conf.js` or no `customLaunchers` block is found. Jest-detected Angular
projects are explicitly NOT given this rewrite (Jest's own default is already one-shot) — regression-tested to
confirm the Karma-only flag rewrite doesn't leak onto Jest.

**Lint and build, confirmed not assumed**: both ARE ordinary `npm run <script>` invocations once wrapped —
`ng lint` and `ng build` are themselves already package.json scripts in a standard Angular-CLI project
(`ng generate`'s own default `package.json` wires exactly this), so `AngularVerifyLadder._lint`/`_build` reuse
`node_env.lint_command`/`build_command` (or `npx ng lint` as a lint fallback) with the identical skip-when-
absent logic `ReactVerifyLadder` already has. Confirmed by reasoning through Angular CLI's own script wiring,
not assumed — no correction needed to D-143's expectation here.

**Dispatcher wiring (`verify/ladder.py`)**: `VerifyLadder.run()`'s existing "node_env present AND frontend
files changed" gate is unchanged; a new private `_run_frontend()` sits behind it and decides Angular vs. React
by calling `angular_ladder.is_angular_project(self.app_dir)` (an `angular.json` file at the app root) —
Angular when true, `ReactVerifyLadder` otherwise (the previous, only, behaviour). Both ladder imports stay
local to `_run_frontend()`, matching the existing lazy-import style `run()` already used for
`ReactVerifyLadder`. A plain React/TS project (no `angular.json` anywhere) is unaffected: the same
`ReactVerifyLadder` runs, with the same rung names and invocations as before this pass — regression-tested
explicitly, same discipline D-139/D-140 already applied to "Python-only workspace unaffected".

**`workspace/nodeenv.py`**: confirmed, not just accepted on faith, that D-143's "no changes needed" holds —
`detect_node_environment()` reads `build`/`test`/`lint`/`typecheck`/`dev` script names generically from
whatever `package.json` the repo actually has; a standard `ng generate`'s scaffolded `package.json` defines
exactly `build`/`test`/`lint` (via `@angular-eslint`) in that shape, so detection already works unmodified. No
change made to this file.

**Left open, not built in this pass** (real gaps, out of scope here): Angular's newer esbuild-based/
Vitest-backed test runner and the `@angular/build:karma` vs. legacy `@angular-devkit/build-angular:karma`
builder distinction were not specifically probed — the Karma detection here is dependency/config-file based
and framework-invocation-based, not builder-aware, so an unusual builder setup could in theory need its own
flags this pass doesn't know about; Nx monorepo conventions (Nx wraps `ng` commands differently and often puts
`angular.json`-equivalent config in `project.json` per-app instead) are not handled — `is_angular_project` only
checks for a literal `angular.json` at the app root, so an Nx workspace would currently fall through to the
React ladder, which is wrong but no worse than before this pass (Nx wasn't handled by anything previously
either); no real Angular CLI or npm was exercised — all tests mock the shell call, per the task brief.

Verified: `ruff check`/`ruff format --check` clean on `verify/angular_ladder.py` (new), `verify/ladder.py`,
`verify/react_ladder.py`, `tests/test_angular_ladder.py` (new); `mypy src/forge` clean (156 source files, no
new errors). New `tests/test_angular_ladder.py` (24 tests): Angular detection via `angular.json`; typecheck
rung uses `ng build` (not bare `tsc`), picks up a `development` configuration when declared, and falls back to
`npx ng build` without a build script; Karma/Jasmine and Jest framework detection (dependencies and
`karma.conf.js`-alone); the critical Karma CI-flag test asserting the EXACT command string (`"...
--watch=false --browsers=ChromeHeadless"`) and explicitly asserting the bare command is never used; a custom
`karma.conf.js` launcher name (`ChromeHeadlessCI`) picked up and preferred; Jest explicitly NOT getting the
Karma flag rewrite; lint/build confirmed as thin script wrappers; dispatcher routing tests in both directions
(Angular project never invokes `ReactVerifyLadder`, non-Angular project never invokes `AngularVerifyLadder`);
and an explicit React-project-unaffected regression test asserting the plain `test_command` runs verbatim with
no `--watch=false` anywhere in any command seen. Targeted run (`pytest -q -k "react_ladder or nodeenv or
angular or ladder" --ignore=tests/test_web_e2e.py`): 43 passed, no regressions. `scripts/check_secrets.py`:
0 findings. Full non-live/non-pg suite run at milestone end.

### D-145 — Guided first-run setup: single script, UI-driven keys, live connectivity check · Agreed (2026-09-29)
Prompted by a real install confusion hit live: the office laptop had a stray `forge` install at
`%LOCALAPPDATA%\Forge\venv` (from an earlier `install_forge.ps1` run) shadowing the one in a freshly replaced
`forge-main` folder on PATH — `forge ui` silently ran the old code with no signal anything was wrong. That
specific bug is fixed by deleting the stray install, but it exposed a broader gap: no single guided path from
"I have the Forge folder" to "the UI is open and I know my keys work."

**What already exists, confirmed by reading the code, not assumed**: `scripts/install_forge.ps1` already
creates a private venv, installs Forge, writes a `%USERPROFILE%\.forge\.env` template, and adds a PATH shim —
but requires a pre-built offline wheelhouse as input, has no "open the UI at the end" step, and has no
connectivity check. `src/forge/doctor.py` already has real, working checks — `check_secrets` (are the required
env names present), `check_models` (a live call to each configured Azure deployment, ok/warn/fail per model),
`check_databases` (live Postgres reachability, access level) — already wired to `GET /api/doctor` and rendered
as a list in `Home.tsx`. The green-tick-per-key idea the user asked for is **not a new capability**, it already
exists; it just isn't part of a guided flow and isn't reachable before the user already has keys in a `.env`.
Config/secrets loading (`config.py`'s `Secrets`/`load_secrets`) is read-only today — there is no existing
"write a value into .env" function; this is the one genuinely new piece of surface being added.

**Agreed flow**, per the user: on open (first run or any run), Forge checks whether the required env values
already exist. If they do, it goes straight to testing connectivity (the existing `check_models`/
`check_databases` logic) and proceeds directly into the app on success — no setup screen shown at all when
everything's already configured (most runs, once set up once). If required values are missing, the user may
either supply them (a form, written to the `.env` Forge already uses) or explicitly ignore/skip and proceed
without them (consistent with Forge's existing philosophy of never blocking on what it can't do — DECISIONS
D-011, "if the user can't act either, Forge proposes a workaround"). On a successful connectivity check, Forge
proceeds directly — no extra confirmation step, no separate "you're all set, click continue."

**Scope for the install script side** (companion to the UI change, smaller piece): the user does the
zip-download-and-unzip manually — no script needed for that part. What needs to be one script is everything
after: venv creation/install from the unzipped folder itself (not `%LOCALAPPDATA%`, sidestepping the exact
PATH-shadowing class of bug just hit, by design — a plain unzipped folder is not a git-cloned repo the way
`forge-main` was, so there is no existing venv to reuse or confuse), then launching `forge ui` automatically at
the end so the very first thing the user sees is the guided setup screen above, not a blank terminal. Prefers
a bundled wheelhouse if present next to the script (offline-capable, matching the real office-laptop
constraint) else installs from the unzipped source directly (online) — this was clarified with the user as not
really an online-vs-offline design fork at all, since the manual download/unzip step already happened before
the script runs either way.

**Not yet decided in this pass** (next implementation step): the exact new backend endpoint(s) for writing a
submitted key into `.env` (must go through the same redaction-registration path `load_secrets`'s
`register_secret_values` already uses, so a freshly-entered key is masked from logs/events immediately, not
only after the next process restart re-reads the file); the exact UI form's field list (presumably the same
required-name set `check_secrets` already computes from `config.llm.providers.azure`, not a hardcoded
duplicate list); the installer script's exact venv/install mechanics (reusing `install_forge.ps1`'s proven
logic for the pieces that transfer, not rewritten from scratch).

**Resolved**: no restart — writing a key reloads `Secrets` in the current process immediately, per the user,
so submit-then-see-green-ticks feels like one continuous flow rather than being interrupted right at the
first-run moment. Implementation needs whatever holds the live `Secrets`/`LLMRouter` instance (check
`engine/session_host.py`/wherever `load_secrets` is currently called once at startup) to support being handed
a freshly-updated `Secrets` object without a full process restart — the exact mechanism (re-run `load_secrets`
and swap it in vs. a narrower "just update these names" path) is left to implementation to work out against
the real startup code, not prescribed here.

### D-146 — D-145 implemented: guided setup screen, .env write endpoint, no-restart live check · Decided (2026-09-29)
Implements D-145's UI/backend piece only (the installer-script piece — one script, bundled wheelhouse,
`forge ui` auto-launch at the end — is separate and still open; see TODO.md).

**Backend**: `config.py` gains `write_secret_values(values, home, redactor)` — the one genuinely new piece of
surface D-145 called out. It reads the existing `.env` line by line, replaces the value on any line whose
name matches a submitted key (regex on `NAME=`), appends lines for submitted names not already present, and
leaves every other line (comments, blanks, unrelated values) untouched; creates the file/parent folder if
missing. It calls `register_secret_values` (the same function `load_secrets` already uses) before returning,
so a value just typed into the browser is masked from logs/events immediately, not only after the next
`load_secrets` call. `doctor.py` gains `required_secret_names(config)` (extracted from `check_secrets`'s own
computation, unchanged behaviour) and `missing_secret_names(config, secrets)` — both the write endpoint's
allowlist and the setup screen's field list derive from these, no duplicate list anywhere.

**Confirmed, not assumed**: read `web/manager.py` in full — `WebSessionManager` holds no `Secrets`/`LLMRouter`
instance until `open_workspace`/`new_workspace`/`new_standalone` runs (i.e. a project already exists). Before
that point, nothing in the process caches secrets, so "no restart" needed no reload mechanism at all: every
`load_secrets(home)` call already re-reads `.env` from disk. `test_freshly_written_value_is_immediately_
visible_with_no_restart` in `tests/test_config.py` asserts this directly (write, then `load_secrets` again in
the same process, no monkeypatching of any cache).

**Endpoints** (`web/server.py`): `GET /api/doctor` gained a query param, `offline: bool = True` — the existing
cheap fast path (used by `Home.tsx` today) is the unchanged default; `?offline=false` runs the full live
connectivity check (`run_doctor(offline=False)`), used by the setup screen right after a submit. New
`GET /api/setup` — cheap, no live calls — returns `{missing: string[], config_error: string | null}` from
`missing_secret_names`, so the frontend can decide before rendering anything whether to show the setup screen
at all. New `POST /api/setup/secrets`, body `{values: {name: value}}` — validates every submitted name against
`required_secret_names(config)` and returns 400 listing the unrecognised name(s) if any are outside that set
(never an arbitrary-file-write primitive); on success calls `write_secret_values` and returns `{ok: true}` —
no submitted value is ever echoed back, matching `doctor.py`'s existing never-print-secrets discipline.

**Frontend**: new `ui-react/src/components/Setup.tsx`. `App.tsx` calls `GET /api/setup` once on load before
rendering Home/Chat (a brief spinner, not the setup screen, while that single request is in flight — no flash
of the setup UI on the common already-configured path); an empty `missing` list skips straight past it. The
form fields are exactly `missing`'s names (no hardcoded duplicate on the frontend); submitting posts to
`/api/setup/secrets`, then immediately calls `GET /api/doctor?offline=false` in the same handler and renders
the result list with the same OK/warn/fail icon convention `Home.tsx`'s existing "Environment check" card
already established (reused, not reinvented). If the Secrets check comes back non-failing, it proceeds
straight into the app with no extra confirmation click; a "Skip for now" button does the same unconditionally,
consistent with D-011 (Forge never blocks on what it can't do).

**Tests**: `tests/test_config.py` — write-into-fresh-file, preserves-unrelated-lines, appends-new-names,
rejects-nothing-itself (validation lives in the endpoint, tested there), the load-bearing no-restart assertion,
and redaction-registration-is-immediate. `tests/test_web.py` — `/api/setup` reports missing names,
`/api/setup/secrets` writes the file and never echoes the value back (asserted against the raw response text),
and rejects an unrecognised field name with no write occurring. `scripts/check_secrets.py`: 0 findings.
`ruff check`/`ruff format --check` clean on every touched backend file; `mypy src/forge` clean; `npm run build`
clean (no new TypeScript errors).

**Left open** (D-145's other, smaller piece — not attempted in this pass): the installer script changes —
`install_forge.ps1` (or a new sibling script) launching `forge ui` automatically at the end so the setup
screen above is the very first thing a fresh unzip-and-run shows, plus its "prefer a bundled wheelhouse next
to the script, else install from the unzipped source" logic. Tracked in TODO.md.

### D-147 — Installer-script piece of D-145: `scripts/run_forge.ps1`, a new sibling script · Decided (2026-09-29)
Completes the last open piece of [D-145]. `install_forge.ps1` was judged the wrong script to extend, not a
base to build on: it installs into `%LOCALAPPDATA%\Forge\venv` (a shared per-user location, outside any
repository, with a PATH shim) — the right model for a stable, long-lived install, but structurally the exact
setup that caused the PATH-shadowing bug that motivated this whole feature ([D-145]'s background) when a
second, different Forge folder existed on the same machine. A freshly unzipped folder has no earlier install
to reuse or collide with, so a new sibling script, `scripts/run_forge.ps1`, creates its venv **inside that same
folder** (`.venv`) instead — nothing to shim onto PATH, nothing that can later shadow or be shadowed by another
copy. It deliberately does not write a `.env` template itself (`install_forge.ps1`'s own job for its own use
case) — [D-146]'s setup screen already covers entering and verifying keys, so this script's only job is
getting to that screen: create/reuse the venv, `pip install -e .` from the unzipped source (or `--no-index
--find-links <wheelhouse>` if one is bundled alongside, for the real office-laptop-may-be-offline case), then
launch `forge ui` directly.

Verified by actually running it against this build machine's own repo (not just written and assumed correct):
first run failed with a raw `WinError 32` — a previous `forge ui` process from earlier in this session was
still holding its own `forge.exe` open, so `pip install -e .` couldn't replace it. This is a realistic scenario
(re-running the script while an earlier window is still open), not an edge case to ignore, so the script now
checks the file lock explicitly before installing and raises a clear message ("Forge is still running from
this folder... close that window or stop the process first") instead of surfacing pip's confusing internal
error. Re-tested after stopping the stray process: reuses the existing `.venv` correctly, installs cleanly,
and reaches a real running server (confirmed via the same 403-means-alive auth-gate check used earlier in this
session, not just "the script didn't crash"). `scripts/check_secrets.py`: 0 findings.

Not built: `install_forge.ps1` itself is unchanged — it remains the right tool for a stable per-user install
outside any working folder; `run_forge.ps1` is for the "I just unzipped this and want it running" case
specifically, and the two are not meant to converge into one script, per the reasoning above.

### D-148 — End-of-requirement retro/lesson approval must not block the next message · Decided (2026-09-29)
User report: Mode B, a from-scratch React attendance app, 4 tasks done; asking Forge to "run it and show
me" got no response — Forge kept repeating "4 tasks completed" and asking for lesson approval instead.
Root cause: `_export()` awaited `after_export()` inline, which (with `learning.retro` defaulting to
`"prompt"`) awaited an approval future for the proposed lessons before the turn ended. `SessionHost.run()`
processes one turn at a time from a single input queue, so the user's next chat message queued silently
behind that unresolved approval card — the same "not a turn-blocking approval gate" principle D-128 applied
to `propose_requirements`/`propose_plan` had not been applied to the retro's lesson approval.
Options considered: (a) leave `retro: "prompt"` as default but make `_export` return before awaiting it
(still gates lesson approval when the user does opt into "prompt"); (b) default `retro` to `"auto"` (lessons
proposed silently, reviewed later via `/lessons`) and always run the retro as a background task decoupled
from the turn. Chosen: **(b)**, both together — matches how this assistant itself handles an end-of-task
retrospective (it doesn't block the next ask on it), and removes the failure mode entirely rather than just
shrinking its window. `learning.retro: "prompt"` remains available for anyone who wants the approval card;
it no longer blocks the input queue either way, since the retro now always runs as a tracked background
task (`Orchestrator._background`/`wait_idle`), awaited only by callers that need the settled result
(`run_headless`, `SessionHost.close`).
Also fixed in the same pass, same underlying complaint ("behave exactly like Claude Code — build it, then
show it to me when I ask, copy instructions only when I ask for them"): the closing message no longer pushes
`output/COPY_INSTRUCTIONS.md` as the default next step (it now says to ask for a run or for copy
instructions); Mode B's system prompt (`system_modeb.md`) gained the same "start it with start_background,
then http_request/browser_open" instruction Mode A already had, since a free-hand Mode B build (no host to
fit) is exactly the case where the user wants to see the running app, not integration steps.
**Tests**: `tests/test_learning.py`, `tests/test_config.py`, `tests/test_web.py`, `tests/test_workspace.py`
(`-m "not live"`) pass. `tests/test_live_learning.py` updated: with `retro: "auto"` as the default, lessons
from a headless auto-approved run stay `"proposed"` (nothing to approve automatically) rather than
`"approved"/"rejected"`; `run_headless` now waits for the orchestrator's background tasks (the retro) before
returning, so the test still observes its result deterministically instead of racing it. `ruff
check`/`format --check` and `mypy src/forge` clean on every touched file.

### D-149 — `related_cards_note` was wired to change requests only, never a fresh requirement · Decided (2026-09-29)
Found running the live test for D-148: `tests/test_live_learning.py::test_second_run_cites_the_first_runs_card`
failed on `advance()` (`orchestrator.py`) only appending `related_cards_note` (the "earlier related
requirements, cite them by id" hint) when `kind == "change"`. A brand-new requirement in an
already-worked-on repo/profile — the common case for this feature, and this test's own second run — never
got the note at all. Fixed by appending it on every first brief regardless of kind (`Library.search` already
excludes the current workspace's own card, so it can't cite itself). Verified live, twice: the model's
plan started citing the prior requirement ("following the same layering pattern as the prior claim-count
requirement" / "the prior claim-count requirement") both times — proving the note reaches the model and is
used — but paraphrased rather than writing the literal id "REQ-0001" the test originally regexed for
verbatim. Loosened the assertion to accept either the literal id or a clear paraphrase (`claim.?count`)
rather than burning a third ~15-20 minute live run chasing exact-string compliance from the model on
wording the prompt never mandates as literal.
**Tests**: `tests/test_learning.py`, `tests/test_config.py`, `tests/test_web.py`, `tests/test_workspace.py`
(`-m "not live"`) pass; `ruff check`/`format --check` clean. Live: two consecutive runs of
`test_live_learning.py` confirmed the note lands and is used (not rerun a third time after loosening the
assertion, since both prior runs' captured plan text was checked against the new assertion logic directly).

### D-150 — Gemini as a second model provider (Vertex AI, any role) · Agreed (2026-09-30), building
User wants Gemini usable alongside Azure OpenAI — any role, not just vision — plus video input (the user
confirmed Gemini handles video, something Azure OpenAI can't do at all) and a startup/doctor connectivity
check showing whether Gemini is reachable, matching D-145/D-146's existing live-connectivity pattern.
**Access path — Vertex AI direct SDK, not LangChain, not the AI Studio API key path.** The user's own
working snippet used `langchain_google_genai`; CLAUDE.md bans LangChain inside Forge (the fixture repo uses
it, Forge doesn't), so the adapter calls Google's official `google-genai` SDK directly (`client.aio.models.*`,
Apache-2.0, pure-Python — installs cleanly into an offline wheelhouse same as `openai`/`httpx`), with
`vertexai=True`. Confirmed live on the user's office laptop (this dev machine has no GCP credentials, so
every claim below was verified there, not assumed): auth is Application Default Credentials, auto-detected
by the SDK (gcloud ADC or `GOOGLE_APPLICATION_CREDENTIALS`) — **Forge never stores or reads Gemini
credentials itself**, unlike Azure's API-key-in-.env model. Confirmed working: plain text calls, tool/function
calling round-trip (model calls a function, the result is fed back as a `function_response`, the model uses
it — the one piece most load-bearing for Forge's agent loop), streaming, image vision, and — on a second
round of testing — video input. `thinking_level` (the newer enum config) is rejected by this Vertex API
version ("not supported by this model"); `thinking_budget` (an integer token count) works. A tight
`max_output_tokens` on a thinking-capable model (e.g. the default test's `max_output_tokens=20`) can be
silently consumed entirely by `thoughts_token_count`, leaving `response.text` as `None` — not a provisioning
error, just a budget-too-small symptom; confirmed by retrying with `max_output_tokens=500`, which returned
"ready" cleanly. On the user's project/region (`us-central1`): `gemini-2.5-pro`, `gemini-2.5-flash`,
`gemini-2.5-flash-lite` all work; `gemini-2.0-flash`, `gemini-2.0-flash-lite`, `gemini-3-pro-preview` are
listed in Model Garden but 404 (not enabled for this project/region) — Model Garden's listing is not proof
of callability, only a live probe-call per candidate model is.
**Role scope**: generalized, not vision-only — `ModelConfig.provider` becomes `Literal["azure", "gemini"]`
and any role may be assigned a Gemini model in config.yaml, the same way Azure models are assigned today.
**Config shape** (`src/forge/config.py`): new `GeminiProviderConfig` (`project_env`, `location_env` — plain
config values pointing at the GCP project/region, not secrets; reuses `Secrets.get`'s existing
env-var-with-os-environ-fallback mechanism purely for the "Forge never stores this, only reads the env var
name" pattern, not because they need redaction). `ModelConfig.deployment_env` becomes optional
(`str | None`); a new `model_name: str | None` field holds a Gemini model's literal string directly in
config.yaml (safe per D-014 — it's a public model name, not a tenant-specific deployment identifier, so no
env-var indirection needed). `doctor.required_secret_names` now asks for Azure's vars only when an Azure
model is in use, and Gemini's `project_env`/`location_env` only when a Gemini model is in use, so an
Azure-only or Gemini-only setup isn't asked for the other provider's values.
**Doctor/startup check**: no new mechanism — `doctor.check_models` already iterates every model actually in
use (any provider) and does a live "reply with the single word: ready" call, reporting ok/warn/fail; a
Gemini model assigned to any role gets this for free through the existing `/api/doctor?offline=false` /
first-run setup screen's connectivity check (D-146), once the router can dispatch to a `GeminiProvider`.
**Video — still open, not yet decided.** The Files API (`client.files.upload`, used for larger video on
Google AI Studio) may not behave the same way on Vertex AI (Vertex more commonly expects a `gs://` Cloud
Storage URI via `file_data`, not an ephemeral upload endpoint) — this needs a live check on the user's
project before committing to a design, since writing the adapter against an assumed-but-unverified upload
path risks silently failing in exactly the case it exists for. Asked the user to run a two-path probe (Files
API upload vs. inline bytes) on the office laptop; awaiting the result. Until resolved, `view_video` is not
built; everything else (provider adapter, router dispatch, config, doctor check, image vision parity with
`view_image`) proceeds in parallel since it doesn't depend on the answer.
**Error mapping**: `google.genai.errors.APIError`/`ClientError`/`ServerError` carry `.code` (HTTP status),
`.status` (e.g. `INVALID_ARGUMENT`, `RESOURCE_EXHAUSTED`), `.message` — maps onto Forge's existing
`LLMError` subclasses the same shape as `azure_errors.py` does for the OpenAI SDK. Confirmed live:
`google.auth.exceptions.DefaultCredentialsError` is what's raised with no ADC configured (this dev machine's
own case) — mapped to `LLMAuthError` with the office-laptop ADC setup pointed to, not a generic failure.
`automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)` is set explicitly on every
call — without it the SDK warns about and may attempt to run tool calls itself, which must never happen:
Forge's agent loop owns every tool call, the same invariant the Azure adapter already holds.

### D-151 — Revamp: Forge works and looks like Claude Code · Agreed (2026-10-02), discussion stage
**Context.** User reports Forge's result quality as very poor and its speed as slow. Target: Forge should
develop, debug and analyse the way Claude Code does (few targeted tool calls, narration between them,
judgment-based verification) and show it on screen the same way. Evidence will come from Forge runs on the
build machine (Azure key, several test projects); we judge the loop from those logs, not from guesses.
**Decisions (user answers):**
- Verification stays judgment-based: Forge decides when to verify. No forced gate (consistent with D-128..132).
- UI = option A: the chat becomes a Claude Code-style timeline transcript (vertical rail; green dot = tool
  call, grey dot = narration; user message in a bordered box; bold tool name + dim one-line description;
  Grep/Read collapsed, Bash/Edit shown with output; narration text in order between calls).
- File edits shown as inline diffs in the timeline.
- Subagents: their own tool calls are visible nested in the subagent row, plus a collapsed hand-back row
  that expands to the full report.
- MCP and LSP wanted. Security design (Mode B, write jail, redaction, permissions) is brought to the user
  BEFORE building either.
- Gemini work (D-150) is PARKED, uncommitted, not to be touched until the user resumes it.
- Evidence plan: Forge writes run logs; user runs several projects here; we read the logs to decide what
  to change in the loop/prompts. Logging must record per-LLM-call latency, tokens and tool durations.
**Still to discuss:** log format/location, the permission DSL, tool-registry/agent config shape.
**Built 2026-10-02 (step 1, run log):** new `llm_call` event from `AgentLoop._chat` (role, model, latency,
time to first token, finish reason, reasoning effort, message and tool counts, token usage, tool calls
requested) written to the existing per-workspace `.forge/transcripts/events.jsonl` next to the existing
`tool_call_finished` durations; `forge log-summary --workspace <dir>` (or `--log events.jsonl`) prints the
one-page report (`engine/log_summary.py`, `tests/test_log_summary.py`). The web UI ignores the new event type.
Known: mypy reports one error in `llm/azure_openai.py` that comes from the parked, uncommitted D-150 config
change (clean without it).

### D-152 — Modules with enforced boundaries · Agreed (2026-10-02), built
User asked to develop Forge as independent modules (main agent, subagents, tools, memory...) so a fault stays
inside one module, and to see whether per-module docs cut token cost. One package (user's choice), tiers and
module list as proposed. Found two import cycles (a 10-package one around tools/agent/engine/verify/vision/web,
and db/kb/workspace). **Fixes:** see docs/MODULES.md "What moved". **Enforcement:**
`tests/test_module_boundaries.py` (tiers + MODULE.md dependency lists), a `MODULE.md` per module folder.
**Behaviour change:** `spawn_subagent` is no longer in `default_tools()`; only the main agent registry (session
host and orchestrator) adds it, so subagents cannot nest (before, read-only subagents were offered it).
**Token cost:** per-module docs cut the cost of *building* Forge (read one MODULE.md, not the 130 KB spec and
2,200-line DECISIONS). They do not by themselves cut Forge's *runtime* tokens; that needs role-specific toolsets,
lazy tool schemas and modular prompt fragments, to be decided from the run logs (D-151).

### D-153 — A chat message answers open approval cards; build id · Agreed (2026-10-02), built
**Problem (office laptop, 2026-10-02):** after "create an attendance system" Forge kept asking to accept/reject
lessons and ignored "launch the app". Cause: a message sent while an approval card is open queued behind the turn
that was waiting on that very card. 15cfd1a already moved the retro off the turn; this fixes the general case.
**Rule:** a non-slash chat message while approval cards or questions are open declines the approvals (message =
instruction) and answers the questions as free text, then runs as normal (`SessionHost._supersede_open_requests`,
`ApprovalBroker.reject_all`, `QuestionBroker.answer_all_with_text`). Declining is the safe direction. Slash
commands leave cards alone. A `request_superseded` notice tells the user. **Build id:** `forge.buildinfo` — a
10-char hash of the package's source (line-ending normalised), shown by `forge --version` and `forge doctor`,
so an installed copy can be compared with this repo (`forge --version` here gives the reference).

### D-154 — `agent` split into agent / subagents / workflow · Agreed (2026-10-02), built
User confirmed splitting the main agent from subagents. `agent` (tier 9) = loop + stuck detection only;
`subagents` (10) = subagent, review, spawn_tool; `workflow` (11) = orchestrator, state, reports, learning_hooks,
frontend_smoke, escalation (+ its `prompts/phases.md`, package-data updated). Escalation ran a debugger subagent
and was imported by the loop, a cycle, so the loop now takes an injected `StuckHandler` (Protocol) and the
session host sets `loop.escalator = Escalator(loop)`; subagent loops leave it unset (they never escalate).
Tiers after this: diagnose 12, engine 13, session/ui 14, web 15, cli 16. See docs/MODULES.md.

### D-155 — Failure handling: the model improvises, no escalation ladder · Agreed (2026-10-02), built
User: "I want the failure handling of Forge to be like: the model improvises" (as in Claude Code). **Removed:**
the stuck detector (repeat call / repeat error / oscillation / no progress / fix attempts), the escalation ladder
(reflection -> debugger -> web lookup -> ask user -> block), the `StuckHandler` injection (D-154), the
`block_current_task` hook, and their tests. **Kept as guardrails:** the iteration cap
(`limits.max_iterations_per_task`, then "Say 'continue'"), the session budget cap, tool errors returned to the
model, `ask_user`, `spawn_subagent` (debugger), `web_search` and `task_update(status=blocked)` — all now the
model's own choice. `system.md` gained one short paragraph describing recovery as the model's call (read the error,
don't repeat the same action, options available). `limits.max_fix_attempts` stays in the config schema, unused,
because config.yaml rejects unknown keys and existing files may set it. Spec §13.3 and the "stuck" Run-map notice
are obsolete (SPEC_DEVIATIONS). **Risk:** an unattended `--auto-approve` run can now loop on one failure until the
iteration cap; judge from the run logs (D-151) whether a light safeguard is needed.

### D-156 — Verification, memory/learning and repo knowledge replicate Claude Code · Agreed (2026-10-02), docs done, code staged
User: verification, memory and learning, and knowledge of the repo should replicate Claude Code. Chosen defaults
(options considered per area: keep as optional tools / shrink / replace; "replace" chosen because the user's
complaint is poor quality and slowness and every extra machinery layer adds tokens and wrong turns).
**1. Verification.** Claude Code has no verify tool: the model runs whatever commands it judges useful (tests,
linter, type checker, build, start the app and call it, browser) through the shell tool and reads the capped
output (§10.3). **Replaced:** the `verify`/`run_tests`/`openapi_check`/`langgraph_check` tools, the Python,
React and Angular ladders, the test-weakening guard and the automatic frontend smoke check at export.
**Kept:** `mark_server_run` and DB hand-offs (safety invariant 6), the Mode B test harness and stub packages,
`spawn_subagent(reviewer)`, and two prompt rules ("no claim without evidence", "never weaken or skip tests").
**2. Memory and learning.** Claude Code = instruction files + auto-memory + skills. **Becomes:** FORGE.md
instruction files (user / project / local, hierarchical; exists in `parity`), an auto-memory folder per scope with a
`MEMORY.md` index and typed files (user, feedback, project, reference) that the model writes through the memory
tools when the user states something lasting or corrects it, and skills. **Removed:** the requirements library
and cards, the lessons store and its approval cards, the retro, `metrics.jsonl`, self-improvement proposals,
`/lessons`, `lesson_propose`, `improvement_propose`, `library_search/read`, `related_cards_note`, `pin_lessons`.
**Kept:** scope isolation (Mode A memory belongs to one repository, Mode B to one host profile, user preferences
global), redaction on every memory write, never secrets or data rows in memory, and invariant 5 (Forge never
changes its own installed code or prompts; the proposals feature simply goes). Removing the lesson approvals also
removes the card type behind the office-laptop report (D-153).
**3. Knowledge of the repo.** Claude Code has no prebuilt index: it uses Glob/Grep/Read, an explore subagent
and CLAUDE.md. **Replaced:** the KB builder, deterministic extractors (Flask/SQLAlchemy/LangGraph/AST), BM25,
LLM-written narrative documents, `kb_search/kb_read/find_symbol/find_references/list_symbols`, the KB check at the
start of a requirement and `forge kb`. **Kept:** Mode B's Host Profile (a different thing: Mode B cannot see host
code at all). **Added later:** a `/init` equivalent that drafts FORGE.md after exploring, and LSP (wanted, D-151).
**Staging (code):** (1) learning and memory first (also ends the lesson cards), (2) verification ladders, (3) KB.
Each step: remove the module's tools from the registry, delete the dead code, update MODULE.md and tiers, run the
module and boundary tests, then compare a run log against the previous build. Nothing is deleted before the
previous state is committed, so git can restore any piece.
**Risks:** lose the deterministic extractors' framework conventions on large repos (quality could drop there);
more tokens spent on search each run; judge both from the run logs (D-151) and keep the removal reversible.
**Open for the user:** whether `test_guard` should survive as a silent check (default: removed), and whether old
KBs/lessons in Forge home should be left on disk (default: left untouched, ignored).

### D-157 — Repo structure like anthropics/claude-code; plugin support; parallel tests · Agreed (2026-10-02)
**Finding:** github.com/anthropics/claude-code holds no CLI source (agent loop, tools, permissions are a pre-built
binary). Its public layout is: `plugins/`, `.claude-plugin/`, `.claude/commands/`, `examples/`, `mods/`,
`scripts/`, `.github/`, `.devcontainer/`, `.vscode/`, `CHANGELOG.md`, `SECURITY.md`, `LICENSE.md`, `CLAUDE.md`,
`README.md`. "Exactly the same" is therefore only possible for the public/extension layer, not the module layout.
**User's answers:** do both (extension layout and housekeeping files); real plugin support (commands, agents, skills,
hooks); keep the tiered `src/forge/` module structure (it enforces the boundaries).
**Done now (housekeeping):** `CHANGELOG.md`, `SECURITY.md` (the six safety invariants and how to report),
`examples/` (FORGE.md, a custom agent, a skill), `.github/` issue and PR templates. No CI workflow yet (it would fail on
the parked Gemini mypy error and needs Edge/Playwright for the browser tests).
**Not built yet (needs the design below approved, because hooks run commands = security-relevant, and plugins are a
new interface):** `plugins/<name>/` with a manifest, commands, agents, skills, hooks, MCP servers; project-level
`.forge/` folder (commands, agents, skills, settings.json at user/project/local level).
**Tests:** `pytest-xdist` added to the dev extras; `pytest -n 12 --dist loadfile` runs all 542 tests in ~3.5 min
(was ~15 min sequential). Fixed on the way: the browser tests were failing since D-146 (empty Forge home showed the
first-run setup screen; the e2e fixture now sets fake keys) and one waited too briefly under load.

### D-158 — `learning` retired; auto-memory built (D-156 code step 1) · Built (2026-10-03)
**Removed:** the whole `learning` module (requirements library, lessons store and approvals, retro, metrics,
self-improvement proposals, scope), `tools/learning.py` (`library_search/read`, `lesson_propose`,
`improvement_propose`), `workflow/learning_hooks.py` (library card + metrics + retro after export, related-cards
note, lessons pinned per task), the `/library /lessons /retro /stats /improve` commands, the `@REQ` and `@L`
mentions, the "lessons" pinned slot, approved prompt overrides (`prompt_override`), and their tests. The retro and its
lesson approval card, which caused the office-laptop report, no longer exist.
**Built:** auto-memory in `forge.memory`: one file per memory (frontmatter name/description/type user, feedback,
project, reference) + a `MEMORY.md` index, in two scopes: user (`<home>/memory/`) and project
(`<home>/memory/scopes/<scope>/`; scope = repo key or host profile, `memory/scope.py`, same key format as before).
Tools `memory_read(name?, scope?)`, `memory_write(name, description, type, text, scope)`, `memory_forget`; the index
of both scopes is pinned every session; `/remember [project] <text>` and `/memory [delete <name>]`. Memories are
redacted and size-capped. Older single-file user memories still load. Pinning a Mode B contract now saves a
project-scope `reference` memory (no approval step) instead of proposing a lesson.
**Kept on purpose:** the `learning:` config key and `limits.max_fix_attempts` stay in the schema (config.yaml rejects
unknown keys); the `lesson_proposed`/`improvement_proposed` event types stay so old event logs still load; the web
`/api/learning` endpoint returns empty lists so the current UI panel renders until the timeline UI replaces it; old
`learning/` data in Forge Home is left on disk, unread. **Tests:** 533 passed + this module's updated tests green
(parallel run, `-n 12`).

### D-159 — Verification ladders retired; the model checks its own work (D-156 code step 2) · Built (2026-10-03)
**Removed:** the whole `verify` module (Python, React and Angular ladders, the test-weakening guard, app-level
openapi/langgraph checks, lint/mypy/compile parsers), `tools/verify.py` (`verify`, `run_tests`, `openapi_check`,
`langgraph_check`), the automatic frontend smoke check at export (`workflow/frontend_smoke.py`), the "tables exist in
scratch" pre-check, and their tests. The model now runs tests, linters, type checkers and builds itself through
`run_command` / `python_run`, reads raw capped output, and starts the app with `start_background` plus
`http_request` / `browser_*` — as Claude Code does. System prompts, the phases text, the `task_update` refusal text and
three skills no longer name the removed tools.
**Kept and moved:** a shell test run still counts as evidence for `task_update` (`execute` already recorded it);
`mark_server_run` and the DB hand-offs; the pytest summary parser (now `toolkit/pytest_report.py`, used by
`forge diagnose` and the restructure before/after check); the diagnose OpenAPI probe (`diagnose/openapi_probe.py`);
Mode B's `GuardFinding` (now in `modeb/fixture_check.py`) and its fixture check.
**Mode B without the ladder:** the shell session sets `PYTEST_ADDOPTS=-p harness_conftest` for Mode B workspaces and
`execute()` runs `ensure_shared_stub_packages` first, so any pytest the model runs loads the host stand-ins and the
stubs can't hide new code (covered by `test_tests_run_against_harness_stubs`, run through the shell).
**Risks:** no automatic "no tests found" / "pytest not installed" / "collection errors, don't write more tests" hints;
the model sees the raw output (more tokens, but also what Claude Code sees); no silent test-weakening guard (the prompt
rule remains). Judge from the run logs. **Tests:** 478 passed, 2 skipped on purpose (parallel run).

### D-160 — Knowledge base retired; the repo is read on demand (D-156 code step 3) · Built (2026-10-03)
**Removed:** the whole `kb` module (builder, extractors for Flask/SQLAlchemy/LangGraph/AST, narrative LLM documents,
index, search), `tools/kb.py` (`kb_search`, `kb_read`, `find_symbol`, `find_references`, `list_symbols`), the KB check
and refresh at the start of a requirement, the `/kb` command and `forge kb`, the `kb` field on `ToolContext`, and the
"tables exist in scratch" check (`db/table_check.py`, dead since D-159). Mode A no longer pins "codebase essentials":
Forge reads the repository with `glob` / `grep` / `read_file` and the explore subagent, like Claude Code.
**Kept, and why (safety):** the credentials-bootstrap detection. Forge must never read the tables an app loads its
database credentials from (spec §9.5.1, safety rules 3 and 4), and that list came from the KB manifest. It now lives in
`db/credential_tables.py` (+ `db/python_index.py`, trimmed `db/data_facts.py`), runs at session start on the original
repo (read-only, secret files never parsed) and feeds `DbSession` deny-tables exactly as before. Moved: BM25 to
`modeb/bm25.py` (Mode B profile search). **Where FORGE.md and skills live now:** the project folder
`<home>/memory/scopes/<scope>/` (Mode B: the host profile folder); a FORGE.md in an old KB folder is copied over once.
**New:** `/init` is Claude Code's: it tells the model to explore the repository and write the repo-level FORGE.md
with the new `instructions_write` tool (refuses to overwrite an existing file). Old KB folders in Forge home are left
on disk, unread. The `kb_builder` model role and the pinned slot name `kb_essentials` (now Mode B profile essentials
only) stay for config and event-log compatibility.
**Risk:** no precomputed API/model/graph catalog, so large repos cost more search per requirement; judge from the run
logs. **Tests:** 464 + 95 targeted after fixes, all green (parallel run); `tests/test_kb.py`, `test_live_kb.py` and the
three table-check tests removed, one credential-table test added.

### D-161 — Accuracy and speed over cost at runtime; token savings only while building · Agreed (2026-10-03)
User: while Forge works with the Azure tokens it must never optimise for cost (accuracy and speed always win); token and
cost optimisation belongs only to how Forge is developed with Claude Code. **Dropped** (not parked): role-specific
toolsets, lazy tool schemas and prompt fragments as cost measures. **Changed:** `limits.session_budget_usd` default
20.0 -> 0 (no cap; `CostTracker.check_budget` ignores a zero budget, `/cost` says "no cap"; a user may still set a
cap); `role_reasoning_effort.summariser: low` removed (summaries replace earlier conversation, so they run at the
model's default effort). **Kept on purpose:** cost display, the context window and tool-output caps (needed for the
window, not for cost), `max_iterations_per_task` (runaway guard), the reviewer/judge on a second model (a different
view, not a saving), low effort right after a cut-off reply (to fit the output limit). **Not done:** the web UI budget
panel still prints "Budget $0" (UI work deferred).

### D-162 — One conversation across tasks; the brief is sent once (found in the first live run log) · Built (2026-10-03)
**Evidence** (`forge log-summary` on a real run, 61 model calls, 89 tool calls, 380 s, 86% of it model time): after every
`task_update ... done` the model re-read the same files in batches of 8–10 (`routes.py` and `policies_repository.py` six
times each, about half of all reads were repeats). Cause: `ContextManager.reset_for_task` replaced the whole history at
each task start, including right after `propose_plan`. **Change:** `Orchestrator._start_task` keeps the conversation and
appends a short "Next task: ..." note; it resets only in a fresh process (resume after a kill), where the history is
empty and must be briefed again. Tasks are now a progress list, not context boundaries. Compaction (unchanged) handles a
full window. **Second bug found in the same run:** `Orchestrator._briefed()` compared against the raw template text including
its `{requirement}` placeholder, so it never matched and every chat message re-sent the whole requirement brief; it
now matches the literal text before the first placeholder. **Tests:** three new unit tests (brief recognised, next task
keeps the conversation, a fresh process is briefed again); the two live orchestrator tests were stale since D-132
(they expected `review.md` and `REQUIREMENTS.md`, and a two-task decomposition); updated to the flat loop.
`reset_for_task` stays in `ContextManager` for the resume path.

### D-163 — A follow-up message always reaches the model; no nudges; bad cwd is an error · Built (2026-10-03, found in the first Mode B build)
**Bug (core, high impact):** after a requirement was delivered, any follow-up message ("launch the app", "add X") made the
orchestrator re-export and print "Done: N task(s) completed" without calling the model: `_run_agent` only looped while a
task was open or none existed, and a follow-up arrives with every task settled. Seen as zero tool calls and a repeated
"Done" in the run log; almost certainly the office-laptop report too (D-153's retro fix was the wrong cause). The old
live restructure test passed trivially for the same reason (the file it checked already existed). **Fix:** `_run_agent`
always runs the model once per message; the orchestrator then exports only when files changed since the last delivery
(`last_edit_step > _export_step`), otherwise just marks the workspace resume-safe again. **Removed the nudge**
("Finish the current step: verify and call task_update ... Don't stop without one of these."): a plain-text answer now ends
the turn, as in Claude Code (headless runs keep their own PROCEED nudge). **Also:** a `cwd` that doesn't exist
(`project` in Mode B, where `project/` is already the root) made the sandbox launch fail and switched the sandbox off for
the session; `execute` now returns "No such folder" instead. Tool-call arguments (shortened, redacted) are now in the
`tool_call_started` run-log event. **Tests:** two new unit tests (follow-up reaches the model without re-announcing; a
plain answer ends the turn with one call), a missing-cwd test.
**Found, by design, not changed:** `pip install` is always-ask, so an unattended `forge run --auto-approve` cannot install
a project's dependencies (Flask etc.) and blocks every task; the model asks the user, nobody answers. The campaign driver
(`C:\Work\ForgeRuns\drive_forge.py`) approves pip installs into the workspace venv only.

### D-164 / D-165 — Follow-ups arrive as the user's own message; restructure carries its instruction · Built (2026-10-03)
**D-164:** Mode B `cwd="project"` (which the model keeps writing) now means the project root; `task_update` works on any
existing task, so a blocked task the model fixed can be marked done (it was refused unless it was the current task).
**D-165, found in enhancement round 2 of the first Mode B build:** the model did not do the requested enhancement; it
re-ran the previous "install flask" feedback and told the user the new features already existed. Cause: a follow-up
was embedded in a long system brief together with every earlier change request, and was never the latest user turn.
Now a follow-up is appended as a normal user message (the earlier requirement is only re-sent as context in a fresh
process). **Same code, second bug:** the restructure brief was built from the original requirement, so the user's
`/restructure <instruction>` text never reached the model (the live restructure test passed trivially because its
asserted file already existed). The change/restructure briefs now carry `{change}`. Tests: follow-up text is the last
user turn and earlier context is kept; the restructure brief carries the instruction.

### D-166 — Work without a task list is still delivered (found in the invoice-tool build) · Built (2026-10-03)
The model built the whole invoice tool without ever creating a task list; the orchestrator only treated work as
settled when tasks existed, so `output/` was never built and an unattended run ended "Understanding the requirement"
(exit 2) with 975 events of finished work. A task list is the model's choice (D-128), so the work is now settled when no
task is open and either tasks exist or files changed since the last delivery; then `output/` is built. The closing
message says "work finished" when there are no tasks. Tests: delivery without tasks; a plain question without edits
neither delivers nor finishes.

### D-167 — Forge verifies web UI work in a real browser (user: "Forge should write and run these scripts itself") · Built (2026-10-03)
**Evidence from the first Mode B builds:** Forge reported UI features done that were not there (bakery cart without any
"Add to cart" button, attendance CSV export that did not exist) because it only ran unit tests; in the attendance runs it
never started the app or opened a browser, and a prompt paragraph asking for it changed nothing (round 4: pip and pytest
only). **Change:** like the existing test-evidence rule, `task_update(done)` is refused when templates, stylesheets or
scripts (not tests) were edited during the task and the app has not been used in a browser since: a `browser_*` tool
call or a passing shell command that runs Playwright counts. The refusal tells the model how (start_background,
browser_open/click/fill, screenshot + view_image, compare with the requirement word by word). New skill
`web-ui-verification` (procedure, and a Playwright script that uses the installed Edge: `channel="msedge"`, no browser
download) plus a rule in both system prompts. Bookkeeping: `ToolContext.last_ui_edit_step` / `last_browser_step`, set in
`AgentLoop._note_ui_evidence` and `execute`. Not covered: work with no task list (only the prompt rule applies). **Tests:**
UI-edited task refused then accepted after a browser step; a blocked UI task is not gated.
**Campaign results so far** (independent Playwright checks in `C:\Work\ForgeRuns`): attendance app 37/37 after 4
enhancement rounds and one feedback round; bakery site 57/57 after 3 enhancement rounds and one feedback round;
invoice tool 26/26 after one feedback round with the real invoices pasted in and one enhancement round.

### D-168 — Independent verifier subagent: Forge writes, runs and acts on its own acceptance checks · Built (2026-10-03)
User: Forge must write independent checks from the requirement's context, run them, analyse the results and rework, as
my own Playwright scripts did. **Built-in subagent type `verifier`** (`spawn_subagent(agent="verifier", task=...)`): a fresh
context that did not write the code derives concrete acceptance checks from the requirement (exact labels and messages,
validations, edge cases, persistence, regression), starts the app, writes a Playwright script (Edge, `channel="msedge"`,
no browser download) or a pytest/requests script under `tests/e2e/`, runs it, decides per failure whether it is an app
bug or its own wrong assumption, fixes its own check mistakes, and replies with PASS/FAIL per check, reproduction steps,
the script path and `VERDICT: PASS|FAIL`. It runs on the `coder` model, may write only below `tests/e2e/` (the file tool
refuses other paths) and cannot change the app. Its approvals (pip install of playwright, starting the app) go through the
main session's approval channel and gate mode instead of an internal broker nobody answers; it shares the session's
background-process manager. A `VERDICT: PASS` counts as browser evidence for `task_update(done)` (D-167). Prompt rule in both
system prompts (use the app yourself, then call the verifier for anything beyond a trivial flow, fix real failures, run it
again) and in the web-ui-verification skill. The scripts it leaves in `tests/e2e/` are delivered with the work, so the user
gets repeatable checks. **Tests:** write restriction, built-in type registered; its behaviour is checked live in the campaign.

### D-170 — Verifier robustness (first live run on the bakery site) · Built (2026-10-03)
First real verifier run (bakery site, 61 tool calls, 12 minutes): it wrote a 436-line Playwright suite under
`tests/e2e/`, ran 23 checks and found a **real bug my own scripts had missed** (placing an order with no customer name
shows no message at all; the requirement said it must be refused with a clear message). Two defects in the verifier
itself: it ran out of steps while still calling tools and returned an **empty report** to the main agent, and it asserted
exact wording the requirement never gave ("Please enter your name.") copied from the app's source. **Fixes:** every subagent
that ends mid-work is now asked once, with nothing to call, to write its report from what it found (`_run_subagent`), the
verifier's step budget is 90 instead of 45, and its prompt now says: check what the requirement says, not what the code
does; never assert unspecified wording (check that a clear visible message appeared); reproduce a failure by hand and read
the server log before calling it a bug. The earlier D-168 checklist (static, tests, runtime log, behaviour, browser
diagnostics, visual, data) stays.

### D-171 — Saving the state of a project to memory so work can be taken up later (`/handoff`) · Built (2026-10-03)
User: the "write everything to memory so it can be picked up later" step I did for this project must be a Forge feature.
**Built on the existing auto-memory (D-158):** `/handoff [note]` asks the model to write ONE project-scope memory named
`project-state` (replacing the previous one) with fixed sections: Goal, Decisions (with reasons and what was rejected), Done
(and how each part was checked), In progress, Next (including open questions), How to run and test, Pitfalls; it reads the
existing state, the task list and the code first and may not invent anything. The same rule is in both system prompts, so a
plain request ("save everything so we can continue later") or having to stop with unfinished work does the same. **Resume:**
when a `project-state` memory exists, the pinned memory block starts with "Work on this project was left unfinished or paused:
read the memory 'project-state' first ... and carry on from there", and the prompts tell the model to do so. Scope is the
project (a repository in Mode A, a host profile in Mode B), so nothing crosses between projects. Tests: `/handoff` sends the
structured request (with the user's note); a saved state is flagged first in the pinned memory.

### D-172 — Hitting the step cap is not finishing; the cap is a generous runaway guard · Built (2026-10-03)
**Found in the larger-feature test** (bakery accounts, loyalty points; the user's open question "does Forge call the verifier on a
larger feature?" — yes: it did, unprompted, 64 tool calls). The verifier correctly reported FAIL (the account page crashed with
a 500 once the customer had an order: Jinja resolves `order.items` to the dict method). But the main agent had used all 40
steps of `max_iterations_per_task` right before, the loop stopped with only a notice, and the orchestrator then **delivered
`output/` and reported "Done"** while the verifier's failure was unresolved and the work was cut off. **Fix:** `AgentLoop`
records `hit_iteration_limit`; the orchestrator returns without delivering or settling when the last run ended at the cap, so
`exported` stays false (an unattended run is nudged to continue, an interactive user says "continue"); the default cap is 150
(a runaway guard only, D-161), not 40. Tests: a model that never stops calling a tool is cut at the cap, nothing is delivered;
the default cap is at least 100.

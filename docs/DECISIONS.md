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

### D-173 — Throwaway checks and clean-up (user: Claude Code "writes a throwaway spec ... cleans up after itself and deletes the file") · Built (2026-10-03)
Forge could already write and run a script against the running app (the main agent via `write_file` + `python_run`, the verifier
under `tests/e2e/`) and delete files it created (`delete_file`; only the user's own files always ask). Missing: the verifier could
not delete anything and was told to leave its script behind, and nothing told it to clean up the data its checks created (the
bakery run left three scratch databases in `tests/e2e/`). **Now:** the verifier has `delete_file` restricted to `tests/e2e/`
(`write_only_under` also guards deletes); its prompt and the web-ui-verification skill say: keep the script by default (a repeatable
check delivered with the project), or call it throwaway/temporary when the main agent says so (`tests/e2e/tmp_*.py`, deleted with
the screenshots and scratch databases when done); either way the checks leave the app and its data as found (a scratch database
file or delete the records, users, orders and files they created; never touch data they did not create). The main agent's prompt
says it may ask for a throwaway check. For Node/React apps the skill names an `@playwright/test` spec. Tests: the verifier may
delete only below `tests/e2e/`.

### D-174 — Visible progress while the model thinks (user: "little visible progress between steps") · Built (2026-10-03)
Measured (28 runs): 74% of the time is waiting on the model, 15 s per call on average and 100-200 s for calls that write whole
files, so the screen was silent for long stretches. **Two changes:** (1) the Responses request now asks for reasoning summaries
(`reasoning.summary: "auto"`, verified live on this deployment) and each finished summary part streams as a `thinking_delta`
event (`ChatRequest.on_thinking`, a local callback that is never sent; `SessionHost.stream_thinking`); the terminal client
prints it dim and italic; a deployment that rejects `summary` is retried without it. (2) both system prompts ask for one short
sentence before a batch of tool calls ("Reading the routes to see how errors are shaped"). Not done: the web UI does not show
`thinking_delta` yet (UI work is deferred), and tools do not start while the model is still streaming its remaining calls.
Tests: summaries reach the callback with `summary: auto` in the request, a refusing deployment is retried without it, the host
publishes the event.

### D-175..D-180 — Items from the Codex-comparison list (docs/SPEC_CODEX_GAPS.md, G1 G2 G6 G7 G4) + subagent progress · Built (2026-10-03)
Built in a separate git worktree while the speed benchmark ran, so the benchmark was not disturbed.
- **D-175 / G1 parallel subagents.** Measured first: the loop already ran consecutive read-only calls in parallel and
  `spawn_subagent` is marked read-only, so two subagents overlapped, including two verifiers (which write `tests/e2e/` and
  start the app) and two debuggers (which run commands). Now only `explore` and `reviewer` overlap (`PARALLEL_SUBAGENT_TYPES`);
  the rest run one after another; at most 4 at once (`MAX_PARALLEL_SUBAGENTS`). Timing test: two reads/explorers about 0.3 s,
  two verifiers 0.6 s, six explorers 0.6 s (4 then 2). Subagents still cannot nest.
- **D-176 / G2 compaction hooks.** `hooks.pre_compact` / `hooks.post_compact` command lists; run through the session's shell like
  `post_edit`; pre-compact output (capped at 1500 chars each, redacted) is handed to the summariser as facts to keep; a failing or
  crashing hook is reported (`hook_failed` notice) and skipped, never blocks compaction. `ContextManager.run_hook` is set by the host.
- **D-177 / G6 `todo_write`.** The model's own lightweight list (whole list each time; pending/in_progress/completed; at most one
  in_progress), no approval, read-only. Pinned (slot `todos`) so it survives compaction, emitted as `todo_updated`, rebuilt from
  the last event when a project is reopened; the terminal shows it. Prompts: use it on work with three or more steps. The web UI does
  not show it yet (UI deferred).
- **D-178 / G7 `monitor`.** Wait on a background process in one call: returns when a regex appears, the process exits (with the exit
  code) or the timeout (default 60 s, max 300 s) passes, with the new output; replaces `read_background` poll loops. Same sandbox, no
  new rights.
- **D-179 subagent progress** (found by the speed benchmark: a verifier runs 10-15 minutes and the screen showed nothing). A running
  subagent's tool starts/finishes and reasoning summaries are relayed to the session as `subagent_step` events (agent id and role
  included); the terminal shows them nested. The web UI shows them once the timeline UI is built.
- **D-180 / G4 per-agent settings.** Custom agent files may set `max_steps` (1-200) and `write_only_under` (a folder; `..` refused);
  an agent that lists unknown tools is rejected with the list of known ones instead of silently ignoring them.
Not built: G3 (compaction robustness; only if real runs need it), G5 (no change under D-155).
- **D-181 subagent display (user decision 2026-10-03).** In the web UI a subagent's own tool calls are shown nested inside its row,
  collapsed by default and expandable (not just the hand-back). Options were nested vs hand-back only; nested chosen because
  verifier runs last 10-15 minutes. Built with the timeline UI (deferred); the engine already relays the steps (D-179).
- **D-182 speed settings unchanged (user decision 2026-10-03).** The A/B/C benchmark (attendance build + 2 enhancements): gpt-5.1
  baseline 2953 s (accuracy not measured: port 5061 is blocked by Edge, ERR_UNSAFE_PORT; avoid 5060/5061 in checks), gpt-5.1 with
  lower effort after read-only steps 2447 s (9/11, 15/17, 19/21), gpt-4.1 coder 742 s (all checks passed, verifier never called).
  One run per setting on one app, verifier use differs, so no setting change; the model and effort stay as configured (D-161).
- **D-183 settings permission rules (user decision 2026-10-03, first step of docs/DESIGN_PLUGINS_MCP_LSP.md).** `<home>/settings.json`
  (`%USERPROFILE%\.forge\settings.json`) may hold `{"permissions": {"allow": [...], "deny": [...]}}`; a rule is `tool` or
  `tool(pattern)` (fnmatch; the pattern is matched against the shell command, wildcards allowed, tool names may use `*`, e.g.
  `run_command(python -m pytest*)`, `mcp__demo__add`, `mcp__demo__wipe*`). **Deny always wins**, in every mode, and also matches a
  segment of a chained command (`cd x && git push` hits `run_command(git push*)`). **Allow only turns "ask" into "allow"**: it can
  never lift a classifier block, the always-ask list (pip install, deleting the user's files, network, outside the workspace) or plan
  mode, and it never covers a command containing `; & | < > \`` or a newline or `$(` (so `pytest && curl ...` is not `pytest`).
  Options considered: user file only (chosen) vs also a project file in the workspace. A project file is deferred: the model can write
  inside the workspace, so a project-level settings file there would let it grant itself permissions. A broken file raises
  `ConfigError` instead of being ignored (a dropped deny rule would be worse than refusing to start). Applies to the main agent and to
  subagents. Option "always allow" prefixes in `.forge/permissions.json` are unchanged. Tests: `tests/test_permissions.py`.

### D-184..D-186 — UI redesign: login, landing flow, Apple-style design (user decisions 2026-10-03) · Built (login, hub, list, theme)
- **D-184 login and landing flow.** The web UI opens on a login page; after signing in the user chooses New project (the existing
  Standalone / From an existing repository form) or Open an existing project (a list, newest first, with the last request and time;
  opening replays the project's events and memory). Login options considered: A local account with a salted scrypt hash (chosen),
  B trust the Windows user (no password), C company SSO (needs admin and app registration, parked). One account per machine in
  `<home>/account.json`; first run creates it; "forgot password" = delete the file (projects are untouched). Wrong passwords: the same
  message for a wrong ID or password, a 30 s pause after 5 in a row. Session = random token in an HttpOnly SameSite=Strict cookie
  (one per port), kept in memory, so a server restart signs everyone out. Everything except the page shell and `/api/auth/*` returns
  401 without it, and the WebSocket closes with 4401. This sits on top of the per-run server token and the 127.0.0.1 bind (unchanged).
  It keeps other people on a shared laptop or browser out; it is not protection from a local administrator. `create_app(accounts=None)`
  means no login and exists only so the older tests need none; `forge ui` always passes an account store. Code:
  `web/accounts.py`, `web/auth_routes.py`, `web/project_list.py`; `/api/projects` (GET) lists projects; the recent list now keeps 50.
  Tests: `tests/test_web_accounts.py`, `tests/test_web_login_e2e.py` (screenshots in test-artifacts/react-ui/).
- **D-185 design language.** The user's design.md (Apple style) is adopted as the theme for the whole app, adapted for a developer
  tool (docs/DESIGN.md): one blue accent (#0066cc, #2997ff in dark) for everything clickable; white cards on parchment (#f5f5f7), near-
  black tiles (#272729 / #1d1d1f) as the alternating bands on the landing screens; hairline borders, no shadows, pill buttons with a
  0.95 press scale, 18 px cards, a frosted top bar. Fonts: Inter bundled via `@fontsource/inter` (OFL licence, build-time npm
  package, offline on the laptop) replaces IBM Plex Sans; the font-weight ladder is 400/600 (`font-medium` maps to 600); JetBrains Mono
  stays for code. Success is a separate green token (`ok`) so blue only means "clickable"; done/added/targets-met/green dots moved to
  it. Large type and 17 px body only on the landing screens; chat, run map and panels keep their dense sizes. Dark theme is derived
  by us from the tile colours (the design.md has none). Photography tiles and the product shadow are not used (no product images).
- **D-186 setup and model plan (agreed global per machine; built 2026-10-03 after the user said "proceed").** The setup shows as
  a **drawer on the right** (user decision 2026-10-03, replacing the first full-screen version): it opens by itself on the New project
  screen, beside the form, and from "Environment" in the top bar; "Create and open" goes straight to the chat and the old
  Environment-check card on the form is gone. Contents: five rows (This computer, Azure OpenAI, PostgreSQL, Gemini, Tesseract OCR) that each run
  live and flip from "checking" to ok / warning / failed with a one-line fix and a Retry button, then a model table (one row per
  role) proposed from what answered. The user can change a row and presses "Save models". Saved in `<home>/environment.json` (check results with times, the confirmed
  role -> model keys; never a secret value, texts are redacted); next time the saved results show at once while the checks re-run,
  and the saved plan is the default. Applied to the live session on confirm and to every new session in `build_session`
  (`apply_saved_plan`; an unknown model key is skipped). Rules: the plan only moves a role off a model that did not answer (to one
  that did, and for `vision` only a model that can read images); Azure with no answering model blocks "Confirm"; one answering model
  is a warning. Options considered for the plan's home: write it into config.yaml (rejected: Forge must not modify config.yaml,
  invariant 5) vs its own file merged at session start (chosen). Honest limits: Tesseract and Gemini are only *detected* (binary on
  PATH, Google credentials + project in .env); this version of Forge does not use either yet, and the screen says so. Gemini's row
  reads "not part of this version" unless the parked provider (D-150) is in the config. Postgres: one reachable database is ok.
  Code: new module `environment/` (checks, plan, store; tier 7), `web/environment_routes.py`, `ui-react/.../Environment.tsx`.
  Tests: `tests/test_environment.py`, `tests/test_web_login_e2e.py::test_environment_screen_in_edge` (the model call is stubbed
  there; screenshots `environment-light.png` / `environment-dark.png`). Also fixed: `__main__.py` had no tier in the boundary test.

### D-187 — Can the agent read Forge's own .env? Verified 2026-10-03; two shell gaps closed (user asked to verify)
- **Checked with real probes** (not only by reading code): `read_file` refuses anything outside the workspace (jail: absolute path and
  `..` both raise). Shell reads of the Forge `.env` by literal path are always-asked in Mode A and blocked in Mode B (outside the
  workspace). A leaked `.env` is masked by redaction: key/secret/token/password values and URL passwords registered from the file
  show as `[REDACTED:NAME]`. Forge never copies `.env` values into `os.environ`, so child commands do not inherit them.
- **Gaps found and fixed:** (1) `Get-Content $env:FORGE_ENV_FILE` (and `$HOME`, `$env:USERPROFILE`, `%APPDATA%`, ...) was classified
  *safe*: a path built from a variable is invisible to the per-argument check. (2) `python -c "open(r'...\.env')"` only asked,
  and could be remembered as "always allow python". Now both are *always-ask* (never remembered, never silent): any command text
  that names `.env` (not .env.example/.sample/.template) after a separator or quote, or uses those variables or `FORGE_ENV_FILE` /
  `FORGE_HOME`. Tests: `tests/test_shell_secret_paths.py`.
- **Closed by D-202 (2026-10-03):** the shell's child processes inherit the user's own environment variables, so a key the user
  exported themselves (not from Forge's .env) would show in `Get-ChildItem Env:` unmasked. Removing Forge's variable names
  (the .env names and the provider env names) from the child environment would close it, but would also hide e.g. LOCAL_PG_URL
  from a built app that reads it from the environment. Redaction does not catch re-encoded values (base64, reversed) if the model
  runs code to transform a secret; that needs an approved command first.

### D-188 — The chat's opening screen (2026-10-03, "proceed to the next screen" = the chat step of the flow)
- A new or empty project's chat opens with a welcome in the new design: a large question ("What are we building?" for Standalone, "What
  should we change?" for a repository copy), one line of guidance, chips for the project name, the mode, the coder model chosen on the
  Environment drawer and a link back to it ("Review environment" until the models were confirmed), and three starter prompts per mode.
  A starter fills the message box (the user reads, edits and sends it; nothing is sent automatically). The rest of the chat (messages,
  tool cards, side panels) only picked up the new theme; the Claude Code style tool-call cards and the subagent view stay in TODO.
  Test: `tests/test_web_login_e2e.py` (screenshot `chat-welcome-light.png`).

### D-189 — Chat look: "Conversation" (user decision 2026-10-03, option A of A/B/C) + Claude Code tool-call layout
- Options shown: A conversation (your message a soft blue pill on the right, Forge's reply as plain text, tool calls quiet lines),
  B transcript (role labels, boxed cards, terminal-like), C turn tiles (alternating light/dark band per exchange). A chosen; C
  rejected for wasting vertical space in runs with dozens of tool calls.
- Built: a centred 760 px column; user message pill (`accent-soft`, 20 px radius, right); Forge reply as prose with no avatar or box;
  a floating pill composer with a round send button (Stop keeps its text label); notices and command output use the full column.
  This also delivers the earlier TODO "Claude Code layout for tool calls" (user choice A, 2026-10-03): a call is one quiet line
  (tool name, summary, status, time); opening it shows an IN block (the command, else the arguments one per line; from the
  `arguments` the engine already sends, falling back to the summary for old logs) and an OUT block folded to 15 lines with
  "Show N more lines". Approval / question / action cards keep their look. Test: `test_react_chat_cards_render`
  (`cards-light.png`). Not done: the subagent nesting (D-181) and the todo list display (D-177) still wait for their UI.

### D-190 — Nested subagent view in the web chat (built 2026-10-03; design decided in D-181)
- A `spawn_subagent` row carries the agent's own steps. Collapsed: a role badge (Explorer / Reviewer / Debugger / Verifier), the purpose,
  the call count ("2 calls, 1 failed") and, while it runs, its newest step ("grep: def authenticate") with a spinner. Opened: the
  steps in order (reasoning notes in italics, each tool call with status and time; up to 400 kept) and then the usual IN (the task) and
  OUT (the hand-back, folded to 15 lines) blocks. The events were already there (`agent_started`, `subagent_step`,
  `agent_finished`, D-179); only the web timeline was missing. Pairing: an `agent_started` joins the oldest running `spawn_subagent`
  row that has no agent yet, so parallel explorers are matched in the order they started (a different order would swap their
  labels: noted as a known limit). An agent started by something other than that tool (the review step) gets a row of its own.
  Code: `ui-react/src/agentTimeline.ts`, `components/AgentSteps.tsx`; test `test_react_subagent_steps_are_nested`
  (`subagent-nested-light.png`).

### D-191 — Todo list in the web UI (built 2026-10-03; engine side is D-177)
- Forge's own list (`todo_write`, whole list per `todo_updated` event) shows (1) as a strip above the message box, open by default:
  "Todo 1/3", then each item with a done check, a spinner for the one in progress and an empty circle for the rest; collapsed it
  shows the progress and the item being worked on; (2) in the side panel's Tasks tab with a progress bar, while the older
  plan/task list (from the phased orchestrator) is empty. Options considered for placement: strip only, panel only, both (chosen: the
  strip is where the eye is during a run, the panel keeps it after the strip is collapsed). State is rebuilt from the last
  `todo_updated` event, so a reopened project shows the same list. The `todo_write` tool row stays in the chat as a normal call.
  Test: `test_react_todo_list` (`todo-strip-light.png`).

### D-192 — Timeline rows in the web chat: narration, folded read/search runs, inline diffs, failures open (built 2026-10-03; agreed in D-151)
- **Narration:** the model's reasoning summaries (`thinking_delta`) show in order between calls as dim italic text; consecutive ones
  merge into one block. **Read/search runs:** two or more `read_file` / `grep` / `glob` / `list_dir` calls in a row fold into one line
  ("Read 2 files, Searched 3 times") with a spinner while running and a red mark if one failed; opening it lists the calls.
  **Edits as diffs:** the `file_changed` event already carries a unified diff; the web now attaches it to the edit's call row, which
  opens by itself with added lines green, removed red, and `+N −M` on the row (the IN block is replaced by the diff, the OUT block
  stays). **Failures open:** a failed call (not one the model retried successfully) expands by itself once, and can be closed.
  Code moved out of Chat.tsx into `components/ToolRows.tsx`. Test: `test_react_timeline_rows` (`timeline-rows-light.png`).
- **Not built, on purpose:** the vertical rail with green/grey dots from D-151: the user's later choice of the "Conversation" look
  (D-189) replaced it. **Still open:** the Run map still reads the old phase field (D-131; two skipped browser tests), and the open
  question of sending the full tool result to the UI instead of the capped preview (the preview is up to the engine's cap;
  redaction would apply either way).

### D-193 — Run map closed out (2026-10-03; the D-133 redesign was already built, this finishes its open items)
- **Tests:** the two browser tests skipped since D-131 are replaced by `tests/test_web_runmap_e2e.py` against the D-133 design: the
  map grows from live events (start, task, helper-agent and deliver nodes appear only when their event fires; markers for failed
  calls, stuck warnings and helper agents sit on the task nodes; the summary strip; Forge waiting on you; the failures drawer with
  its "fixed later" outcome; a task opens its place in the chat) and the activity line with the per-task badge and the run-total strip.
  Screenshots: `run-map-light.png`, `run-map-dark.png`, `run-map-failures-light.png`, `activity-light.png`.
- **Per-agent cost (the D-133 fast-follow):** `agent_finished` now carries `cost_usd`, the cost of that subagent's own model calls
  (summed from its `llm_call` events with the session's price table; a model no longer configured counts as zero; the session total
  already included it). Shown on helper-agent nodes in the Run map and in the nested subagent row of the chat.
  Test: `tests/test_agent_loop.py`.
- **Look:** the task and agent nodes lost their small shadow (the design has none). Behaviour of the Run map itself is unchanged.
- **A trap found while testing:** the page re-reads `/api/state` on every `task_list_updated`, so a test that fakes "working" with a
  `status_changed` event must publish it after the task list, or the server's real "not busy" overrides it.
- **A real bug the loaded test runs exposed (D-193):** a node added to the map later (Deliver, a helper agent) could stay invisible for
  good: the Run map gave React Flow no node sizes, so it hid each new node until it had measured it, and under load that
  measurement was sometimes missed (about one run in three while the whole suite ran in parallel). The nodes now carry their known
  width and height (the same numbers dagre lays them out with), so they show at once. Also a fix for `subagent.py`: a loop
  stand-in without a router (as in `test_events.py`) gets cost 0 instead of failing.

### D-194 — Contracts panel in the web UI (built 2026-10-03; the second half of D-129)
- A **Contracts** tab in the side panel, offered only on Standalone (Mode B) projects (Mode A reads the repository itself, there are no
  seams to pin). A form (seam, signature, optional note) pins a contract; each pinned contract is a card with its signature, note,
  where it came from ("Pinned by you" / "From your corrections"), when it was pinned and revised, and Revise / Forget buttons
  (Revise locks the seam and saves a revision; Forget asks first). The list also refreshes when the chat pins one with `contract_pin`
  or `/contracts pin`. Endpoints: `GET/POST /api/contracts`, `DELETE /api/contracts/{seam|id}` (`web/contracts_routes.py`). Pinning
  runs the same `contract_pin` tool the chat uses, so a contract entered on the panel is also saved as project memory, then the pinned
  context is refreshed so the next model call sees it. Options considered: a modal editor (rejected: the panel is narrow but always
  open and the form needs three fields), editing the signature in place on the card (rejected: easy to change by accident; Revise
  is explicit). Forgetting removes the contract from the register (as `/contracts forget` does); a memory note saved when it was
  pinned is not removed. Tests: `tests/test_web_contracts.py`, `tests/test_web_contracts_e2e.py` (`contracts-light.png`).

### D-195 — The full result of a tool call in the web UI (built 2026-10-03; the open question from the tool-call layout, D-189)
- **Problem:** the `tool_call_finished` event carries only a preview (1,500 characters; a failure keeps its head and tail), so a long
  test run or file read could not be seen in full. Options: (a) raise the preview cap, (b) save the whole text and fetch it on
  request (chosen), (c) put the whole result in the event. Rejected (a): any cap still cuts something. Rejected (c): the event log
  is replayed in full on every reopen and sent to the browser, so a few large outputs would make reopening a project slow.
- **Built:** when a result is longer than its preview, the engine saves the whole text to
  `<workspace>/.forge/tool-output/<32-hex id>.txt` (through the write jail, redacted with the event bus's own redactor, cut at
  2,000,000 characters with a note) and the event gains `output_id` and `output_chars`. `GET /api/tool-output/<id>` serves it
  (the id must be exactly 32 hex characters, so no path can be passed; behind the login and the session token like every other call).
  In the chat the OUT block shows "Show full output (N characters)"; it replaces the preview with the whole text (scrolling box,
  copy button, "Show less"); a deleted file says "The full output is no longer available". Subagent calls save nothing (their
  calls show only as steps). Short results save nothing. Code: `agent/tool_output.py`, `web/tool_output_routes.py`,
  `EventBus.redact_text`. Tests: `tests/test_tool_output.py`, `tests/test_web_tool_output.py`, `test_react_full_tool_output`.
- **Security:** the same redaction as the events (invariant 3: secrets never reach the browser); the files sit in the workspace's own
  `.forge` folder, which is not part of the delivered output. **Limits:** the files stay until the workspace is deleted (no
  clean-up yet); a result cut by the tool itself (the shell's own cap, the context cap applied later) is saved as the tool returned it.

### D-196 — What Forge remembers, shown on each project in the project list (built 2026-10-03; part of D-184)
- Each project card now shows, under the last request: **where the work stands** (the first line of the Goal and of the Next section of
  the `project-state` memory a `/handoff` leaves; if the handoff has no such sections, its first line), chips for the number of
  remembered notes, FORGE.md present, and when the handoff was saved. The search box also looks in the handoff. Read from the Forge
  folder without opening the project (`web/project_memory.py`): Mode A projects by their repository's memory scope, Standalone
  projects by their host profile (FORGE.md lives in the profile folder there). Nothing is shown when nothing is remembered, and a
  project whose profile reference is missing shows no memory instead of an error. Options considered: a "Resume" preview panel
  (rejected for now: the card already carries the two lines that answer "where was I"), and listing every note name on the card
  (rejected: too long; the count is enough, the notes are in the project). Tests: `tests/test_project_memory.py`,
  `test_react_project_list_shows_what_forge_remembers` (`projects-memory-light.png`).
- **Found on the way:** FORGE.md sits in the same folder as the project's memory notes, so `MemoryStore.all()` lists it as a note
  named "FORGE" (and it probably appears in the pinned memory index). The count here skips it; the store itself is unchanged.

### D-197 — Change password screen (built 2026-10-03; extends D-184)
- Your name in the top bar opens **Your account**: who is signed in and a Change password form (current, new, repeat). The server
  asks for the current password again (a borrowed open window must not be able to lock the owner out), enforces the same 8-character
  minimum and refuses the same password; wrong guesses of the current password count toward the same 5-tries / 30-second pause as
  sign-in. On success every other session is signed out and this browser gets a fresh one (`POST /api/auth/password`; the route
  checks the session itself because `/api/auth/*` is reachable without one). The user ID cannot be changed here (deleting
  `account.json` still resets everything, and the login screen still says so). Options considered: also changing the user ID
  (rejected for now: it adds nothing to protecting the machine), a modal over the current page (rejected: the other landing screens are
  pages). Code: `AccountStore.change_password`, `web/auth_routes.py`, `components/Account.tsx`. Tests: `tests/test_web_accounts.py`,
  `test_account_screen_in_edge` (`account-light.png`).

### D-198 — The Learning tab is gone, and the message box suggests only real commands (2026-10-03; closes the D-158 leftover)
- The side panel's **Learning** tab (lessons, requirements library, improvement proposals) showed three empty lists since the learning
  module was retired (D-156/D-158). The tab, its component, the `/api/learning` endpoint (kept empty only so that panel kept rendering)
  and the web's handling of `lesson_proposed` / `improvement_proposed` events are removed; the event names stay in the protocol so
  old logs still load. A tab remembered as "learning" in the browser falls back to Tasks.
- **Found on the way:** the message box's "/" suggestions still offered seven commands the engine no longer has (`/improve`, `/kb`,
  `/lessons`, `/library`, `/restructure`, `/retro`, `/stats`) and lacked `/contracts` and `/handoff`. Fixed, and
  `tests/test_slash_suggestions.py` now fails when the suggestion list and the engine's command table differ (only `/exit` is left
  out on purpose). Memory (FORGE.md, notes, handoff) is the replacement for lessons and is shown in the project list (D-196).

### D-199 — Cleanups (2026-10-03)
- **Saved tool outputs (D-195) are capped:** at most 200 MB per workspace; after each save, if the folder is over the cap the oldest
  files are deleted down to 80% of it (the file just written is never deleted). A deleted output shows "no longer available" in the
  chat. Options considered: delete by age (rejected: reopening an old project would lose all of its outputs at once) and clean up at
  session start only (rejected: a long single session could grow without bound). Tests in `tests/test_tool_output.py`.
- **FORGE.md is no longer a memory note:** it shares the project's memory folder, so `MemoryStore.all()` listed it as "FORGE (user)",
  and the pinned index and `MEMORY.md` repeated the repository rules the model already gets as instructions (and `memory_read`
  could open it as a note). The store now skips it (`INSTRUCTIONS_FILE`); the file is untouched. The workaround in the project list
  count (D-196) is gone. Test: `tests/test_memory_store.py`.
- **Phase leftovers hidden:** the top bar's status badge ("direct") and the Tasks tab's "Phase direct" line showed the engine's coarse
  status string, which means nothing to a user since the phase pipeline went (D-131). Removed; the engine still sends the field.

### D-200 — Azure keys on the Environment drawer (2026-10-03; REPLACED by D-204: keys are no longer typed into the app)
- The **Azure OpenAI** row of the drawer now lets you fix what it reports: when required values are missing it lists them (names
  only) in a form (the key field is masked), and "Save and test" writes them and re-runs the check at once; when everything is set a
  quiet **Update keys** button opens the same form with every required name, empty, where a blank field keeps the saved value. Until
  now a missing value could only be entered on the first-run screen (or by editing the file); if that screen was skipped there was
  no way back to it. **No new way to write secrets:** it uses the existing `POST /api/setup/secrets` (only the names Forge itself
  requires are accepted, nothing is sent back, the new values are registered for redaction at once). The check result and
  `GET /api/setup` carry names only (`missing`, `required`).
- **Hardened while there:** a value with a line break is refused (a pasted second line would have added a second variable to the .env
  file) and whitespace around a value is trimmed. Options considered for the form's home: a separate Settings page (rejected: the
  drawer is where the failure is seen) and prefilled masked values (rejected: the browser must never receive a saved value, invariant
  3). The values live in the .env file in the Forge folder as before (see the risk discussion of 2026-10-03: plaintext on disk, same
  as editing the file by hand). Tests: `tests/test_web.py`, `tests/test_environment.py`, `tests/test_web_keys_e2e.py`
  (`environment-keys-light.png`).
- **Test infrastructure fix found on the way:** the browser-test fixtures now ask the OS for a free port instead of a fixed preferred
  one: two test files running in parallel could pick the same port and one of the servers failed to start (a refused connection).

### D-201 — Tesseract and Gemini are asked about first, then tested for real (user decision 2026-10-03)
- The Environment drawer asks **"Is Tesseract installed on this computer?"** and **"Is Gemini enabled for you?"** (Yes / No buttons on each
  row). Nothing is tested until the answer is yes; a row with no answer says "Answer the question to test it", a no says "Not in use".
  The answers are saved per machine in `environment.json` and shown again next time; the page only re-tests what was a yes. The
  **server enforces it too**: `POST /api/environment/check/<id>` for these two returns "not in use" without running anything unless
  the saved answer is yes (`POST /api/environment/answer`, optional tools only). New status `off` (not in use) next to ok/warn/fail.
- **Tesseract is tested properly:** Forge finds the program, runs `--version`, then draws the word "Forge" with Pillow (already a
  dependency) and has Tesseract read it back from a temp file: that proves the install, its language data and the command line work
  together. Because the user said it is installed, not finding it is a *failure* ("add its folder to PATH, or answer No"); a
  Tesseract that runs but cannot read the image is a *warning* (check eng.traineddata). The real test ran against the Tesseract 5.4
  installed on the build machine. **Gemini:** after a yes, the checks are the same as before (project and location in .env,
  Google credentials file present); a live call needs the parked provider code (D-150) and a machine with credentials, so it waits
  for that. Tesseract and Gemini are still reserved: this version of Forge does not use either.
- Options considered: test automatically and let the user hide a failing row (rejected: the user asked to be asked first), a global
  "enable optional tools" switch (rejected: the two are independent). Tests: `tests/test_environment.py` (including the real OCR
  test, skipped where Tesseract is not installed), `test_optional_tools_are_asked_before_they_are_tested`
  (`environment-ask-light.png`).

### D-202 — Forge's own variables are hidden from the commands the model runs (user decision 2026-10-03; closes the open point of D-187)
- A command the model runs used to inherit the whole user environment, so a key the user had exported themselves, `FORGE_ENV_FILE`
  (which names the .env file) or the Azure settings showed in a plain `Get-ChildItem Env:` (no approval needed) and redaction only
  knows values loaded from Forge's .env. The shell's environment (`ShellSession.environment()`, used by `run_command` and
  background processes) now drops **Forge's own names**: every name in Forge's .env, `FORGE_ENV_FILE`, `FORGE_HOME`, and the provider
  settings from config.yaml (the Azure endpoint, key and version names, each model's deployment name, and the Gemini project and
  location when that provider is present). Names are matched case-insensitively (Windows); the list follows the .env file's modified
  time, so a key added on the Environment drawer is hidden from the next command on. What Forge sets **on purpose** is added after the
  removal and kept: the scratch database of this requirement (`db.command_environment()`).
- **Cost the user accepted:** an app Forge builds or tests that reads a name from the environment which is also in Forge's .env (for
  example `LOCAL_PG_URL`, or the Azure settings for an app that calls Azure OpenAI itself) no longer sees it in a command Forge runs;
  the scratch database URL for the requirement is still provided. Options considered: only ask before listing variables (not chosen:
  `$env:NAME` and `python -c` still read them) and leave as is. Not changed: `diagnose` (runs the repo's app for a failing build, not a
  model-driven command) and the venv creation step. Code: `toolkit/private_env.py`; tests: `tests/test_private_env.py` (including a
  real process started with the scrubbed environment).

### D-203 — The `ocr_image` tool: Forge uses Tesseract (user decision 2026-10-03: "an ocr tool the model calls")
- New tool **`ocr_image`**: reads the exact text in an image or PDF with Tesseract, on this computer. Arguments: a path (repo-relative or
  `.forge/inputs|scratch_images|reports|screenshots/...`, the same rules as `view_image`; secret files are refused), `pages` for a PDF
  (1-based, up to 10 at a time, the first 10 by default), `region` `[x1,y1,x2,y2]` for part of an image, `layout` (page / block / line /
  word) and `language` (letters and `+` only). Small images are enlarged 3x first (Tesseract reads small type badly). It is for characters
  that must be exact (function signatures, code, numbers, tables in a screenshot); `view_image` stays the way to understand a picture,
  and every result ends with a reminder that OCR can confuse look-alike characters. It is **read-only** (it works on temporary copies
  outside the workspace, so it also works in plan mode) and nothing leaves the machine.
- **When it is offered (D-201):** only after the user answered Yes on the Environment drawer *and* the last Tesseract test passed
  (`store.tesseract_ready`). A new session reads that at start; on the drawer a Yes whose test passes gives the **open session** the tool
  at once, and a No takes it away at once (`ToolRegistry.remove`). Subagents do not get it. The drawer's test and the tool share one
  OCR code path (`vision/ocr.py`), so a green tick means the tool works.
- Options considered: OCR every attachment automatically (rejected: every attachment pays the time and tokens, and noisy OCR can
  mislead), OCR only for pasted signatures in Standalone projects (rejected: narrowest, least benefit), a tool the model decides to call
  (**chosen**: costs nothing unused, the model asks when exact text matters). Tests: `tests/test_ocr.py` (real Tesseract: a screenshot, a
  region, a two-page PDF, a blank image; skipped without Tesseract) plus the gating tests. Gemini is unchanged: still only detected, and
  it cannot be verified on the build machine (see memory note on build-machine tools).

### D-204 — The settings-file guide and the test-by-request drawer (user decisions 2026-10-04; replaces D-200)
- **The first run now shows a guide, not a form.** "Set up Forge" says **where the .env file is** (its exact path, whether it exists, and
  when the location comes from `FORGE_ENV_FILE`; a Copy path button), says plainly that **the page cannot see the keys** (it only checks
  which names are filled in; a key is never shown or sent to the browser) and asks the user to edit the file themselves. It lists every
  name Forge reads, grouped, with what each should hold and whether it is required, offers a **Copy template** (generated from Forge's
  own configuration in `environment/guide.py`, placeholders only), and after the user saves the file a **Check the file** button shows
  each name as filled in or missing (names only). The two optional-tool questions (Tesseract installed? Gemini enabled?, D-201) are
  asked here too. **Continue** needs the required Azure names filled in; "Skip for now" stays. The same guide opens later from the
  Environment drawer ("Where is the file, and what goes in it?").
- **Two databases, two rows (user decision):** the **Forge database** (`LOCAL_PG_URL`: where Forge develops, writing only its own
  scratch schema per requirement) and the **Development database, read-only** (`DEV_PG_URL`: an existing database Forge may read, never
  writes). Both optional, each with its own text and its own Test; there is **no "use one database for both" suggestion** anywhere.
  `FORGE_PG_URL` (the build repo's own test database) is not in the template. A database that is set but does not answer is **Failed**
  with the reason (the doctor's "warning" is raised to a failure here); one that is not set is a Warning that names the variable.
- **The drawer tests only when asked:** opening it shows the last results ("Tested 5 minutes ago") and tests nothing; each row has a
  **Test** button, and **Test all** tests every row that applies (the two optional tools only after a yes). Wording: Connected / Failed /
  Warning / Not in use / Not tested yet ("Working" for the two rows that are not connections). Saving the models needs Azure tested.
  After the guide's Continue the drawer opens by itself. A row cannot be tested before its yes/no is answered; the server holds to that.
- **Keys are never typed into the app (user decision), so the writing path is gone:** `POST /api/setup/secrets`, the first-run form
  (`Setup.tsx`) and the drawer's key form (`AzureKeys.tsx`, D-200) are removed; no endpoint of the web app can write the .env file.
  A project that is already open keeps the keys it started with (the model router reads them when the session starts); a new project or
  a restart picks up edits, and the drawer's Azure test always reads the file fresh. Tests: `tests/test_setup_guide.py`,
  `tests/test_web_setup_guide_e2e.py` (`setup-guide-light.png`, `environment-tests-light.png`), updated drawer tests in
  `tests/test_web_login_e2e.py`. `write_secret_values` stays in config.py, now unused by the web app.


### D-205 — Gemini provider built from the office-laptop signatures, verified there only (2026-10-04)
- Context: this dev machine has no Google credentials, so no live Gemini call can run here; the user's notebook
  screenshots (text, `thinking_budget`, function declarations, inline image `Blob`, per-model probe) are the evidence.
- Built: `llm/gemini.py` (client `vertexai=True`, `client.aio`, SDK retries off, automatic function calling disabled),
  `llm/translate_gemini.py`, `llm/gemini_errors.py`, router dispatch on `model.provider`, `gemini` extra in pyproject.
- Choices (small, reversible): tool schemas go in `parameters_json_schema` (full JSON schema; the screenshot used the
  OpenAPI-style `parameters`, so this is the one unverified call: the smoke script tests it with a real schema);
  thinking uses the integer budget only (`thinking_level` is rejected there); the model's raw parts, with thought
  signatures, ride in `provider_items` and are replayed only to the same model; `output_tokens` includes thinking.
- Not done: `view_video` (video mechanism still unprobed), Google Search as a hosted tool.
- Verify: `scripts/dev/gemini_smoke.py [model]` on the office laptop.
- Drawer (user request 2026-10-04): the Gemini row now makes one real call once the user answers Yes (was detect-only).
  If it fails for any reason (names missing in .env, `google-genai` missing, no credentials, model 404), the row shows the
  reason and an (i) icon that opens the numbered steps (`GEMINI_STEPS` in `environment/checks.py`). Any check can carry `steps`.

### D-206 — A second Azure OpenAI resource as the fallback model (user decision 2026-10-04)
- Context: the user has another resource (`gpt-4o-2024-11-20`, vision works, own quota). Value is resilience: when the first
  resource returns 429/5xx after the retries, the router's fallback role goes to a resource with separate quota.
- Chosen: a model entry may name its own `endpoint_env` / `api_key_env` / `api_version_env` (all three or none, Azure only);
  new model `gpt4o` (`AZURE_FALLBACK_ENDPOINT`, `_API_KEY`, `_API_VERSION`, `_DEPLOYMENT`) is the default `fallback` role.
  gpt-4o is not used for any other role: accuracy first (D-161).
- Optional by design: a model used only as the fallback is not "required" (setup guide rows are optional, doctor skips it
  when unset, the router skips it and re-raises the original error). A machine without the four values behaves as before.
- The user's own `.env` lowercase entries (`openai_api_*`, `deployment_name`) were renamed to these names and
  `openai_api_type` was removed (implied by `provider: azure`); a notebook that read the lowercase names must be updated.
- Live check (2026-10-04): gpt41, gpt51 and gpt4o all answer; gpt-4o uses the Chat Completions API (auto-fallback from Responses).

### D-207 — Installing third-party skills the way Claude Code treats them (user decision 2026-10-04)
- Context: Claude Code can be told to use a skill repository (ui-ux-pro-max-skill, taste-skill); Forge had skills but no way to
  take one from GitHub, and `load_skill` returned only SKILL.md (a skill that ships data or scripts lost them).
- Claude Code's model, copied: installing a skill is the user's decision to trust it; nothing scans it; every command its
  instructions lead to still goes through the normal approval. Differences, both stricter: Forge ignores a skill's
  `allowed-tools` pre-approval (it only shows it), and only the user's own command can install (the model has no tool for it).
- Built: `forge skill add <github.com link | folder> [--list] [--yes] [--force]`, `forge skill list`, `forge skill remove <name>`
  (`parity/skill_install.py`). Fetch = the repo's zip from codeload.github.com (no git needed; 50 MB / 5000 file caps; every
  archive path checked, symbolic links never created; public github.com repositories only). Each skill found (any depth) is shown
  (description, file count, programs inside, allowed-tools) and asked about; same-named copies in one repo are skipped; an existing
  name is never replaced without `--force`. Installed into `<home>/skills/<name>/` (cleaned name).
- `load_skill` now appends the skill's folder and file list and takes `file=` to read one text file inside that folder (path
  contained, 200 KB cap, no links). A program in the folder runs only through the shell, which asks.
- Checked live (listing only, nothing installed): nextlevelbuilder/ui-ux-pro-max-skill (7 skills, several with Python scripts) and
  leonxlnx/taste-skill (many single-file skills) both parse. Many of those skills assume Claude/Codex tools (image generation,
  a skill's own search script), so some instructions will not apply in Forge.
- **Found by a live run (2026-10-04, ui-ux-pro-max installed for real):** Mode B refuses to run or read anything outside its code
  folder, so the skill's script in `<home>/skills` was blocked (safety invariant 2 holds; no exception made). Fix: `load_skill`
  copies the skill's folder into `<code folder>/.forge/skills/<name>/` (never delivered: `.forge/` is in the default excludes) and
  tells the model that full path. Re-run: the model ran `search.py` from the copy and got the design-system recommendation.
  Side finding: a workspace created under a Windows 8.3 short folder name (`DEBANG~1`) makes the path check treat the resolved long
  path as outside the workspace; not fixed (rare), use a normal path.
- Not built: install from the web UI, private repositories, updating an installed skill, a skill marketplace.

### D-208 — The user can open files and folders for reading, in Mode B too (user decision 2026-10-04)
- Context: copying each installed skill into every project (D-207's first fix) wastes space, and Mode B ignored an explicit
  "read this file". Safety invariant 2 (Mode B never reads outside the workspace and profile folder) is amended, not dropped.
- Options considered: (A) `/allow-read <path>`, (B) a path the user types or @-mentions, (C) ask on the model's own reads.
  Chosen: A + B + installed skills always readable; C rejected (the model could talk the user into opening host code).
  User answers: grants last for the project; a folder includes everything under it.
- How: `workspace/read_grants.py` (`ReadGrants`). Always-readable root: `<home>/skills`. Grants are stored in
  `<home>/read_grants/<hash of the workspace>.json`, outside every folder a tool can write, so only the user's own actions can add
  to it: `/allow-read [path]` (no path lists), `/revoke-read <path>`, `@C:\full\path`, or a full path typed in a message that also
  has a reading word (read, open, review, inspect, analyse, summarise, study, examine, go through, refer to, check out). A long paste
  never grants. Each grant is announced (`read_grant` notice) with how to undo it, and the model is told the full path to use.
- Where it applies: `Workspace.path_of` / `is_secret` (so read_file, list_dir, glob, grep, view_image), and the shell's readable roots
  (reading only; a program still goes through approval). `..` paths that land in a granted place also work (the model often turns a
  full path into `../x`). Writes: the write jail is unchanged, a grant never allows one. Secret files (.env, keys) still show key
  names only; the shell still asks for them.
- Refused as too broad: a drive root, the user's profile folder or any folder containing it, and Forge's own folder (keys, accounts).
- Supersedes: `load_skill` no longer copies a skill into the project; it names the skill's own folder.
- Live check (Mode B, real Azure): told to read a file by its full path and use ui-ux-pro-max, the model read the file, ran the
  skill's script from `~\.forge\skills`, and used the brief's colour; the project folder held only the page.
- Not built: a button or panel in the web UI for grants (commands only), a per-grant expiry.

### D-209 — Web research as a chain of independent stages that never ends in nothing (user decision 2026-10-04)
- Context: `web_fetch` was one path (Tavily or a plain GET); any failure was an error, a script-built page came back empty, PDFs were
  rejected, and nothing stopped it reaching `localhost` or the intranet. The user asked for it to be modular so that something
  is always returned, with subagents to dig deeper.
- Design (modules in `tools/`): `web_guard.py` (address policy), `web_extract.py` (HTML via Trafilatura if installed else the
  in-house converter; PDF via pypdfium2; text/JSON), `web_render.py` (read-only headless Edge/Chrome via Playwright),
  `web_chain.py` (the stages), `web.py` (the tools). Stages for one page: cache -> direct HTTP (3 tries, backoff, Retry-After,
  per-host pacing, guarded redirects) -> headless browser (only when the page came back empty/thin) ->
  archive.org copy (only if the page could not be reached) -> the search snippet seen earlier. Each stage that cannot help records why;
  the result says which stage answered. A thin page or a snippet is a PARTIAL result (ok, with the reason and what was tried), not
  an error; only when nothing at all exists is it a failure, and then it lists every attempt and what to do next.
- Guard (default on): loopback, private, link-local, shared and metadata addresses, `*.local`/`*.internal`, credentials in the URL
  and non-http(s) schemes are refused; names that resolve to internal addresses too; every redirect hop and every browser
  sub-request is re-checked. `web.allow_hosts` opens a named internal host; `web.deny_domains` / `web.allow_domains` are lists.
  `web.ask_new_domains` (default off, speed first, D-161) asks once per site, remembered per host, through the existing
  approval flow; the user's `permissions.deny` rules can also name a site, e.g. `web_fetch(*evil.example*)`.
- Browser: fresh profile, no cookies, downloads and service workers off, images/media/fonts not loaded, 25 s limit; no click/type
  on external pages (a page's hidden instructions could drive them). Unavailable (Playwright or browser missing) is recorded, not fatal.
- Search: SearXNG added as an optional provider (`SEARXNG_URL` in .env, first in the default order, skipped when unset); every
  result's snippet is remembered so `web_fetch` can fall back to it.
- Subagent `researcher` (`spawn_subagent`): searches and reads several sources, cross-checks, reports claims with URLs, what
  disagrees and what could not be read; if it stops early the caller still gets a message with next steps. Skill `web-research`
  holds the protocol for the main agent.
- Security fix found on the way: subagents did not inherit the web settings, so in Mode B an explore/reviewer subagent's
  `web_search` skipped the host-term filter and its own keys. They now inherit them all (`inherit_web_settings`).
- New optional dependency: `trafilatura` (Apache-2.0; pulls lxml BSD, justext BSD, courlan and htmldate Apache), extra `webtext`;
  without it the in-house converter is used. Playwright was already an optional extra.
- Left out on purpose: click/type/scroll tools on external sites, login or cookie storage for the web, robots.txt checks for single
  pages the user asked for. Not built: domain rules in the web UI.

### D-210 — Tavily search through the company's agent platform; the direct Tavily key is gone (user decision 2026-10-04)
- Context: the Tavily key only works from a server, not from the office laptop (the network blocks it). The user deployed
  a Tavily tool on the agent platform and registered it as an API (a bearer-token POST to `.../tool-operation/execute-tool`
  with `{"args": {query, topic, max_result, exclude_domains, include_domains}, "tool_instance_id": N}`; read from the user's
  screenshots, 2026-10-04). The platform wraps the reply (a JSON string inside JSON).
- Removed: every direct use of the Tavily key: the `api.tavily.com` search, the Tavily `/extract` stage of `web_fetch`
  (D-209), `TAVILY_API_KEY` everywhere (guide, `.env.example`, tests). The platform tool only searches, so `web_fetch` has no
  Tavily stage any more.
- Added: `environment/tavily_tool.py` (client). Settings come from the `.env` file only: `TAVILY_TOOL_URL`, `TAVILY_TOOL_ID`,
  `TAVILY_BEARER_TOKEN` (the token is registered for redaction like any `*TOKEN*`). Provider `tavily` in the search order, now
  second (after SearXNG, before DuckDuckGo): the reason it was last (blocked network) is gone; a failing call falls through to
  the next provider. The reply is unwrapped until `{"answer", "results"}` is found, so a change in wrapping does not break it;
  the answer is shown above the results.
- Asked, as for Tesseract and Gemini (D-201): the drawer and the first-run guide ask "Is the Tavily web search service
  available to you?"; after a Yes the Test button makes one small real search. No keeps Tavily out of the search order
  (`tavily_declined`). A failure shows an (i) icon with the steps. Following the user's rule (D-204), the token, URL and id are
  not typed into the app: the question tells the user which three lines to put in the `.env` file.
- Expired token: HTTP 401/403 says so ("put a fresh one in TAVILY_BEARER_TOKEN"); the token never appears in a message.
- Unverified (no token on the build machine): the reply shape of the real `execute-tool` call (parsed tolerantly), whether
  `topic` accepts `General` (the only known-good value is `News`; a refused topic is retried once with `News`), and
  `max_result` as a string (as the platform's own test sends it). `web.tavily_topic` sets the topic.
- The platform address in the screenshots is `sit.nonprod`: the user should confirm the production address before relying on it.

### D-211 — A Mode B project folder may already hold other files (user request 2026-10-04)
- Context: creating a standalone project refused any folder that was not empty ("choose a new folder"); the user picked a folder that
  held their sample inputs and wanted that to work. Mode A never had the rule.
- Now: any folder is accepted, except one that is already a Forge project (open it instead), a file, or one that already uses a name Forge
  needs for its own folders: `project`, `_harness`, `output`, `.forge`, `.venv` (the error names them). Existing files are never changed.
- Isolation kept (invariant 2): in Mode B the shell's workspace is only Forge's own folders (`ShellScope.own_folders`), so a command cannot read
  or list the user's other files in the folder (`type ..\notes.txt` is blocked; `..` itself is no longer allowed). The file tools already only
  reach `project/` and `_harness/`. Code the model runs can still open files by itself (the same limit as everywhere), which is why
  the rule is "Forge's folders only" and not a promise about what a program does.
- Nothing deletes the project folder: `forge cleanup` only drops recorded database objects, and the output builder only clears `output/`.
- Not changed: the folder is still required on the form (the Create button waits for a value).

### D-212 — Questions in a chat session are clickable options plus a text box; files beside project/ are not "the workspace" (user report 2026-10-04)
- Found in the first live run of the Capability Lab prompt (the project folder was the sample-inputs folder):
  1. The model asked its question as plain text. The clickable question card (options, Recommended badge, "type your own answer") already
     existed, but its `ask_user` tool was registered only for orchestrated runs, so a normal chat had no way to use it.
     Now every chat session has `ask_user` (via `ToolContext.ask_user` -> `SessionHost._ask_user` -> the question broker); orchestrated
     runs keep their own path. Both system prompts tell the model to use it instead of asking in plain text. A typed message still answers
     an open question as free text. The returned text is "The user chose: X (. They added: ...)" or "The user answered: ...".
  2. The model could not read `brief.md` / `.env` beside `project/`: with D-211 those files are in the project folder but not in Forge's own
     folders, and D-208 treated "inside the workspace root" as already handled, so typing their path granted nothing. Fixed with
     `Workspace.own_folders()` / `is_own()`: Mode B's workspace is Forge's own folders only, so a typed path (or `/allow-read`) to a file
     beside them is a normal read grant (file only; `.env` still shows key names only). The shell's own-folders rule (D-211) uses the same method.
- Side effect to know: a chat session now offers `ask_user` to the model; subagents do not get it.

### D-213 — A plain-text question becomes a card; a resumed project reopens the files its request named (user report 2026-10-04)
- Correction to D-212: in the web UI (orchestrated sessions) `ask_user` and its option card already existed all along; the model simply
  chose to write its question as text (even with "Option A/B/C" lines) in the first run and again after a resume, whatever the prompt said.
  D-212's `ask_user` for direct chat sessions stays (it helps non-orchestrated sessions) but was not the cause.
- Fix: in `AgentLoop.run`, when a turn ends with a reply that asks the user something (ends in "?" or lists options) and `ask_user` is
  available, the loop adds one system note ("ask it again with ask_user, 2-4 options, or carry on with your judgment") and lets the model
  continue; at most once per turn, and never for subagents (they have no ask_user). Cost: one extra model call on such turns.
  A false positive just costs that call: the model carries on or ends the turn again.
- The resume bug: reopening a project re-runs its saved request, which bypassed the step that opens the files a typed path names, so a
  project whose first message pre-dated the fix stayed closed ("does not exist"). `Orchestrator.resume` now calls
  `grant_from_message` on the saved request (and change request) and announces anything newly opened.

### D-214 — The question is a pop-up with select-then-submit; a working helper shows what it is doing (user request 2026-10-04, screenshots)
- Before: clicking an option sent the answer at once, with no sign of what was selected, and the question sat in the chat.
- Now (`ui-react/src/components/QuestionDialog.tsx`): the oldest unanswered question opens as a pop-up. Options are a radio list
  (click selects, click again clears; keys 1-4 select); a box takes the user's own answer, or a note when an option is selected; a line
  above the button says exactly what will be sent; "Submit answer" sends (Enter or Ctrl+Enter also). "Answer later" (X, or Esc, which does
  not stop the run) leaves the question in the chat as the same form, with "Show as a pop-up" to bring it back. After answering, the chat
  card shows "You chose: X" (or "You answered: ..."). A question that is no longer pending (e.g. a reopened project) never pops up.
- Helpers: a running helper agent's row in the chat opens by itself, so its tool calls and notes appear as they happen, and folds away when
  it is done (unless the user opened or closed it themselves). The activity line above the message box now says "<Role> is working" with
  its call count and its newest step instead of repeating the task text.
- Tests: `tests/test_web_question_e2e.py` (real path in headless Edge: the model asks, the user selects, changes their mind, adds a note,
  submits; the next model call carries the answer; "Answer later" and the way back) and an added check in `test_react_subagent_steps_are_nested`.
- Not deployed to the running server when built (the user's session was in progress): the UI change reaches a browser on its next reload
  and the Python side is unchanged by this entry.

### D-215 — Approval card layout with long commands (user screenshot 2026-10-04)
- A long answer such as "Always allowed 'python "C:\...\search.py" "reading list…"'" squeezed the title ("Allow run_command?") to nothing, so the two
  overlapped, and the "Always allow <command>" button wrapped into a tall pill with centred text.
- Now: the answer badge is capped at 40% of the header and cut with an ellipsis (the full text is its tooltip); the title keeps the rest and never
  collapses; "Always allow <command>" is its own full-width, left-aligned row with the command cut on one line (full command as tooltip).
- Test: `tests/test_web_approval_e2e.py` (the model asks to run a long command; the card is measured: no overlap, one-line button).

### D-216 — The to-do strip is one line by default, in smaller text (user choice A, 2026-10-04)
- Options discussed: A collapsed by default (chosen), B inline in the chat, C side panel only. Claude Code shows the checklist inline and the
  active item on its status line (from memory, unverified); A is the closest without losing the list.
- Now: the strip above the message box shows "Todo 3/6 · <item in progress>" in 12 px text; a click opens the whole list (12 px, smaller icons,
  max height 10 rem); the choice is remembered in the browser (`forge.todo.open`, optional: blocked storage just means collapsed); when every
  item is done it folds by itself ("Todo 6/6 · All done"). The side panel's Tasks tab keeps its normal size.
- Tests: `test_react_todo_list` (collapsed first, opens, small text, remembered across a reload) and
  `test_react_todo_strip_folds_when_everything_is_done`.

### D-217 — A missing page is reported as missing; a turn does not end with the to-do list half done (found in the live Capability Lab run, 2026-10-04)
- Live finding 1: `web_fetch` of a URL that answers HTTP 404 went on to the headless browser, which rendered the site's error page, and the tool
  reported that as a successful fetch ("Example Domain, via browser"), so the model never saw the 404. Now a 404 or 410 skips the browser
  (it can only show the error page; the archive is still tried), and the browser stage itself refuses any page the site answers with HTTP 400 or
  more ("browser: unavailable (the site answered HTTP 404)"). The result is a failure that lists the 404 and the archive attempt.
- Live finding 2: after the prompt's "tell me briefly when each phase starts and ends" the model ended its turn with a status message after
  Phase 3 while its todo list still had Phases 4-6 open, and Forge announced "Done: work finished" and delivered. D-163 (a plain answer ends the
  turn) stays the rule, with one addition, in `AgentLoop.run`: when a turn ends with text, the model's todo list still has pending or
  in-progress items, the text is not a question to the user and the mode is not plan, the loop adds one system note ("carry on with the next item,
  or use ask_user, or update the list") and continues; at most twice per user message, never for subagents (their todo list is empty).
  The orchestrator no longer treats a turn as settled (no export, no "work finished") while that list has open items.
- Cost: one or two extra model calls when the model stops early. If the model still stops, the user simply says "continue".
- Not changed: design-system search chose "Meditation & Mindfulness" for a reading-list app (the skill's own keyword matching); the model
  can pass better keywords.

### D-218 — Four fixes from the live Capability Lab run (user screenshots 2026-10-04)
1. **Buttons greyed out on a new request.** Cause: each session numbered its requests from 1 again, so a new request ("question-1", a step
   for the user) shared its id with an old, answered one, and the page marked it answered. Fix, both sides: ids now carry a per-session part
   (`question-ab12c-1`, `approval-ab12c-1`), so they never repeat across sessions; and the page keys answers by the card, not by the id, and
   treats only the newest card of an id as possibly open (so old logs that already have repeated ids behave).
2. **Forge does the work itself where it can.** The model asked the user to install Flask into the project's virtual environment
   (`request_user_action`). `request_user_action`'s description and both system prompts now say: installing a package into the workspace's own
   venv is done by the model with `run_command` (the user gets the usual approval card, pip install always asks); a step is handed to the user
   only for what Forge cannot do, or after its attempt was refused or failed.
3. **Two different cost numbers.** The top bar showed the session's cost, the strip above the message box the project's total (all sessions).
   Both now show the project total ("Project total"); the top bar's tooltip says so.
4. **"Thinking..." all the time.** Between tool calls the activity line now says what the model is busy with, taken from the todo item in
   progress (the work word that comes first in its text: Researching, Designing, Testing, Planning, Coding, Reading, Writing) with the item
   as the detail, else from the last tool used (Coding after an edit, Researching after a web call, ...), else "Thinking". A working helper
   still shows "<Role> is working" (D-214).
- Tests: `test_a_new_request_that_reuses_an_old_id_can_still_be_answered` (real browser), `test_request_ids_do_not_repeat_from_one_session_to_the_next`,
  and added checks in `test_activity_line_and_run_totals`.

### D-219 — Long-running work is never a blind wait (user request 2026-10-04: "can we make it generic")
- Context: a full test suite run piped through `tail` showed nothing until the end; the user asked that Forge handle any long job the way the
  assistant handled it (run it so it does not block, watch its output, report progress, cover every way it can end), not only tests.
- Layer 1, needs nothing from the model or the program: `toolkit/progress.py` (`ProgressTracker`) watches the output of every command (and
  `monitor`) and publishes `tool_progress` events at most every 2 s, only when something changed: the newest line (ANSI and carriage-return
  redraws handled), a progress figure when the output shows one (`NN%`, `[n/m]`, `n of m`; the last figure is kept), the line count, the elapsed
  time, and `stalled_s` once nothing has been printed for 2 minutes (repeated each further minute). The page shows it on the activity line:
  the line, the figure with a thin progress bar, "no output for N min" in the warning colour. Redaction runs on the events like any event.
- Layer 2, model side: the prompts tell the model to start anything likely to take over a minute with `start_background`, say what it is
  watching, follow it with `monitor` (whose pattern covers failure as well as success) and report where it stands and the outcome;
  `monitor` now publishes the same progress while it waits and ends its result with a note when the output holds Traceback/FAILED/ERROR/Killed/
  fatal lines ("silence is not success"); a foreground command that hits its time limit is told to use start_background + monitor.
- Decided with the user (recommended defaults): live output lines on the activity line (redacted, at most one update per 2 s); the quiet-time
  note after 2 minutes. **Not built yet:** moving a foreground command to the background by itself at ~5 minutes (the process is started with
  its own pipes, so handing it over needs more care), and layer 3, a Jobs strip listing every background process with its live tail and a Stop button.
- Tests: `tests/test_progress.py` (figures, throttling, redrawn bars, quiet time, a real PowerShell command, `monitor`) and added checks in
  `test_activity_line_and_run_totals` (browser). Found by them: a progress bar redrawn without newlines showed the previous figure.

### D-220 — Recovery hint on a Mode B path block; Forge suggests next steps (user request 2026-10-05)
- Context: in the Capability Lab run a skill script was refused because of `--output-dir ".."`; the model told the user the script "can't be run here"
  instead of retrying. The user also noted Claude Code is recommendative (flags small gaps, offers next steps) and Forge is not.
- Decided (recommended defaults): the Mode B "outside the workspace" block text now tells the model to retry with the path inside the project/output
  folder; both system prompts say skill scripts run from the skills folder and add a "helpful colleague" rule: flag gaps/risks in one line with a
  recommendation, end a finished turn with 1-3 next steps (ask_user when there are real options), never start unrequested work, skip when nothing
  is worth saying. Prompt-only: reversible by deleting the bullet. Not built: a dedicated "suggestions" UI chip row (discuss first if wanted).

### D-221 — The todo strip above the message box is removed (user request 2026-10-05)
- Context: the strip stayed on the last list after a task finished and carried over into the next request, so it looked stale; the user asked for it to go.
- Decided: `TodoStrip` is deleted (supersedes D-216). The model's list still shows in the side panel's Tasks tab; `todo_write`, events and the
  open-todo nudge (D-217) are unchanged. Test `test_react_todo_list` now checks that no strip exists; the fold test is gone.

### D-222 — From the Capability Lab log review (2026-10-05)
- Runtime data (`*.sqlite`, `*.sqlite3`, `*.db` and their journal/wal/shm files) is never delivered: `compute_changes` skips them, in both modes
  (a run had shipped an app database with test rows). Test: `test_runtime_data_files_are_not_delivered`.
- `system_modeb.md` has a "Paths in Mode B" rule (paths relative to project/, no `project/` prefix, bare `python`, start apps by module,
  keep every path inside project/output/_harness); about 12 of the run's 26 failed calls were path guesses.
- A subagent's own model and tool calls are saved to `.forge/transcripts/subagents/<utc-stamp>-<agent-id>.jsonl` (redacted, text deltas left
  out), so a run can be judged afterwards. The session log still holds only start/finish. Ids restart each process, hence the timestamp.
- Event timestamps already carry a UTC offset (`+00:00`); the "no timezone" worry in the review was a misreading of truncated output.

### D-223 — Sandboxed npm failed with EPERM, so Forge handed "run the app" to the user (2026-10-09)
- Seen in a Mode B build: `npm create vite` / `npm install` ran at low integrity and could not write `%LOCALAPPDATA%\npm-cache` (EPERM), so the
  frontend never installed (SWC native binding missing) and the model told the user to run the commands themselves.
- Options: (a) redirect the node package-manager caches into `.forge/sandbox/` like `PIP_CACHE_DIR` (chosen: keeps the sandbox, reproduced and
  verified with a real sandboxed `npm create vite`); (b) turn the sandbox off for npm (rejected: weakens invariant 1); (c) only change the prompt (rejected: the failure was environmental).
- `ShellSession.environment()` now sets `npm_config_cache`, `npm_config_devdir`, `npm_config_update_notifier`, `YARN_CACHE_FOLDER`, `npm_config_store_dir` while sandboxed.

### D-224 — Asked for an uninstalled skill, Forge improvised from a web fetch (2026-10-09)
- On the office laptop `ui-ux-pro-max` was not installed (skills were installed with `forge skill add` on the build machine only, D-207), so the model
  read the repo through web_fetch and applied "ideas manually" without telling the user how to install it.
- Fix: the prompts (both modes) and the `load_skill` not-found message now say the skill is not installed here and give the exact `forge skill add` command.
  Still the user's own command; no model install tool (D-207). A chat `/skill add` command was not built (new UI feature: discuss first).

### D-225 — `/skill` chat command (2026-10-09)
- `/skill add <github link|folder> [--yes] [--force]`, `/skill list`, `/skill remove <name>` in the chat (`engine/skill_command.py`), same code as
  `forge skill add`. Without `--yes` it only shows each skill's summary (what it does, scripts, size); `--yes` installs. A new skill is pinned to the
  index at once (no restart). Options for the confirm step: a two-step command (chosen, works in terminal and web alike), an approval card (more UI
  work), install-on-first-run (no look first, rejected). The model still has no install tool (D-207): "use a skill from GitHub" makes it tell the user
  the command; it never downloads on its own. D-224 prompts/`load_skill` message now point at `/skill add`.

- The prompts (both modes) also tell Forge how to explain installing and using a skill when the user asks (/skill add, /skill list, naming the skill in a request).

### D-226 — Delete a project from the project list (user request 2026-10-09)
- Each row in "Your projects" has a Delete button; it asks first (path shown), then `POST /api/projects/delete` removes the project's whole workspace
  folder (repo copy, output, transcripts, saved outputs) and its recent-list entry. Closes the session first if the project is open.
- Refused: a folder Forge does not list as a project, a folder holding Forge's own home, or one that contains the user's original repo. Read-only files are
  cleared before removal (Windows). Code: `web/project_delete.py`, `WebSessionManager.delete_project`.
- Options for the memories / Mode B host profile: delete with the project, or keep (chosen). They belong to the repository or host and are shared by
  every project of it (and a Mode B profile is reused when the same name returns), so removing them with one project would silently wipe the others' knowledge. A
  separate "forget what Forge learned" action can be added if wanted.

### D-227 — "What Forge learned": pick and forget notes, grouped by project (user request 2026-10-09)
- A button on "Your projects" opens a list of everything Forge keeps (notes, the handoff, FORGE.md), grouped by memory scope. A scope is shared by every
  project of a repository or host, so the group title lists those projects; the user's own preferences are one more group, and notes whose project was deleted
  appear as "No project (left behind)". Tick items (or a whole group), confirm, forget. `web/learnings.py`, `GET /api/learnings`, `POST /api/learnings/delete`.
- Only known groups and `note:<name>` / `instructions` items are accepted, so no path from the browser reaches the disk. The Mode B host profile itself
  (structure, exemplars) is not listed; only its FORGE.md. Options: per-project grouping with copies of shared notes (rejected: the same note would
  appear twice and deleting one copy would be misleading), or one flat list (rejected: the user asked for grouping).
- Update (same day, user asked): the Mode B host profile is now listed as an item ("Host profile") in its group. Forgetting it removes the whole profile folder
  (its description of the code, examples, and the FORGE.md kept there); projects using it still open (a missing profile is handled) and start from scratch, and
  a new project with the same name recreates it. The item's description says so before the user ticks it.

### D-228 — Tesseract not found on the office laptop (user report 2026-10-09)
- The Environment test said "cannot find it" although Tesseract was installed: Forge looked only on PATH and in `C:\Program Files\Tesseract-OCR`, and a no-admin
  install usually lives elsewhere. Now it also looks in Program Files (x86), `C:\Tesseract-OCR`, `%LOCALAPPDATA%\Programs\Tesseract-OCR`, `%LOCALAPPDATA%\Tesseract-OCR`
  and the scoop folder, and reads an optional `TESSERACT_CMD` from the `.env` (a full path to tesseract.exe or its folder; it wins). The failure message says
  how to set it. Not verified on the office laptop itself.

### D-229 — The projects pane on the left can be folded (user request 2026-10-09)
- A button at the top of the pane folds it into a thin rail (show-projects and new-project buttons); the choice is remembered in the browser (`forge-sidebar-collapsed`). Small reversible UI change.

### D-230 — Start-Forge.cmd: double-click to run the downloaded version (user request 2026-10-09)
- `Start-Forge.cmd` in the repo root calls `scripts/run_forge.ps1 -Extras mcp,browser` (process-scope execution-policy bypass, no admin): venv in the folder, editable
  install, open the UI. Chosen over a signed `.exe` (unsigned downloads are often blocked on managed laptops) and over a shared %LOCALAPPDATA% install (an older
  copy can shadow a newer one, seen live). Pauses with a message when it fails. Tested here from a clean copy of the repo (venv created, installed, UI started);
  the office laptop's SmartScreen/AppLocker behaviour for a downloaded `.cmd` is untested. Supersedes the parked installer idea for the simple case.

### D-231 — Chat message text 14.5px -> 13.5px (user request 2026-10-09)
- Only the conversation text (your messages and Forge's replies) in the main chat area; headings, code blocks, tool rows and panels are unchanged.

### D-232 — An answered question shows its options and the chosen one (user request 2026-10-09)
- After the user answers one of Forge's questions, the chat card becomes "Question · Answered · 1 question" (folds with the chevron): the question, every option, the
  chosen one ticked and highlighted, the user's note under it, or their own typed answer as "Other". New event `question_answered` (id, choice, text) published by
  `QuestionBroker.ask`, so a reopened project shows the same card (it replays from the event log). Questions answered before this change (no event in the log)
  keep the old look: a card with the short answer badge. Approvals and "a step for you" cards are unchanged.

### D-233 — The middle (chat) column is 8% smaller (user request 2026-10-09)
- CSS `zoom: 0.92` on the chat column (`.chat-scale`), so messages, cards, tool rows, code and the message box shrink together, on top of D-231 (message text 13.5px).
  Side panels, top bar and the left pane are unchanged. To change it, edit the one value in `ui-react/src/index.css`.

### D-234 — No "Recent" pane inside a project; the project name in the top bar is a switcher (user choice 2026-10-09)
- Options discussed: remove the pane and make the name a switcher (chosen), keep the thin rail collapsed by default, remove it with no replacement. Supersedes D-229 (the
  fold button): `Sidebar.tsx` is gone. The name in the top bar opens a menu with the recent projects (the open one ticked), a trash icon on each row (asks first; deleting
  the open project returns to Home) and "New project". Home / "Open a project" still show the full list. The top bar got its own stacking level so the menu sits above the chat.

### D-235 — The Tavily token may be pasted with or without "Bearer" (user question 2026-10-09)
- Forge builds the header as `Bearer <token>`; a pasted `Bearer eyJ...` (or a quoted token) is now tidied (`clean_token`) instead of sending "Bearer Bearer ...". The guidance stays: paste the token only.

### D-236 — Tavily test failing although the API works (user report 2026-10-09)
- Forge sent the topic only as "General", then "News". Now it tries the configured topic, the same word in the other letter case (Tavily documents lowercase `general`, `news`, `finance`),
  then `News` / `news`; if all are refused, the failure lists each topic with the platform's own words (up to 700 characters in the Environment row), so the real cause is visible.
  `web.tavily_topic` in config.yaml still sets the first topic (for example `finance`). The real reason for the user's failure is not known yet: it needs the message from their laptop.

### D-237 — Forge can install a skill the user linked, after the user approves (user request 2026-10-09; changes D-207's "the model has no install tool")
- Options discussed: an approval card limited to a link the user typed (chosen), the same for any link the model proposes (rejected: a web page or file could steer it to a hostile
  repository, leaving the user as the only safeguard), keep it as it was.
- New tool `install_skill(source)` (`tools/skill_install_tool.py`). Safeguards: (1) only a github.com link whose `owner/repo` appears in the user's own messages this session
  (`SessionHost.user_github_repos`, filled in `submit`, survives compaction); subagents have no such list, so they cannot use it; (2) Forge fetches the repository first and the question
  card is built from its real contents (skills, files, programs inside), not from model text; (3) only the option "Install" proceeds, a typed answer or "Don't install" installs nothing,
  in every permission mode (plan mode still denies the tool); (4) a skill's `allowed-tools` is still ignored and every command it leads to still asks. After approval the skills are
  re-indexed at once (`skills_changed` -> `refresh_instructions`), so they are ready to load in the same turn. Prompts (both modes) and the load_skill not-found message now say this.
  `/skill add` and `forge skill add` are unchanged. Not tested with the live model, only the tool and its safeguards (`tests/test_install_skill_tool.py`).
- Also fixed: `tests/test_ocr.py` replaced `find_tesseract` with a no-argument function after D-228 added the argument; added a test for `TESSERACT_CMD`.

### D-238 — Dependencies section: libraries of the open project and their known vulnerabilities (user request 2026-10-09)
- User choices: the open project's dependencies (not Forge's own); vulnerability data from BOTH OSV.dev and pip-audit, and each vulnerability must say which source found it.
- New module `deps` (tier 5): `scan.py` reads requirements*.txt (with -r includes), pyproject.toml (project, optional groups, dependency-groups, poetry), poetry.lock, uv.lock,
  Pipfile.lock, package.json + package-lock.json (v1-v3), and the `*.dist-info` folders of the project's Python environment (file reading only: nothing in the project is run).
  A direct library without a pinned version takes the locked, then the installed version; if there is none it is listed as "version unknown" and not checked. A standalone (Mode B)
  project has no manifests of the host, so the host profile's package list is used. Skipped folders: node_modules, venvs, .git, build output; depth 3.
- `osv.py`: `api.osv.dev` querybatch + per-vulnerability details (summary, severity from the advisory's label, fixed versions; fixing commit hashes are dropped). `audit.py`: runs
  `pip-audit --no-deps --disable-pip` on a temporary file of `name==version` lines (Python only; optional extra `forge[audit]`, Apache-2.0, added to Start-Forge.cmd's extras; absent
  = a status line "not installed", not an error). `check.py` runs both at once and merges: the same vulnerability under different ids (GHSA/PYSEC/CVE) is one finding with
  `found_by: [osv.dev, pip-audit]`. A source that fails becomes a status line (never an exception).
- **Data leaving the computer (security-relevant):** only library names and versions, only after the user clicks "Check for vulnerabilities" and confirms a notice that says so (with an
  extra sentence for standalone projects, whose names describe the host). Listing is offline. The last result is kept in the project (`.forge/dependency_check.json`, written through the
  write jail) and shown on reopening. The model has no tool for this.
- UI: a "Deps" tab in the right panel: counts by severity, one line per source (ok / not installed / unreachable), search, "Vulnerable only", libraries worst-first; expanding one shows
  each vulnerability (link, severity, summary, aliases, fixed-in, Found by). Routes in `web/deps_routes.py`.
- Verified live (build machine): osv.dev and pip-audit both answered for requests 2.19.0, jinja2 2.10, lodash 4.17.15; of 15 merged findings 11 came from both sources and 4 (npm) from OSV only.
  Not verified: the office laptop's access to api.osv.dev and pypi.org (a block shows as "unavailable" with the reason). Not built: Forge's own libraries, yarn/pnpm locks, other ecosystems,
  CVSS scores (severity is the advisory's own label), a `forge doctor` line for pip-audit (the tab says so itself).

### D-239 — License information in the Dependencies tab (user request 2026-10-09)
- User choices (options discussed): source = installed files first, deps.dev for the rest (alternatives: installed files only; PyPI + npm registries directly); use = show the license
  plus a risk category (alternatives: license name only; plus a company allow/forbid policy in config.yaml, not built).
- Read offline (`license_read.py`): Python `*.dist-info/METADATA` (`License-Expression`, else the `License ::` classifier, else a short `License:` line; a long value is the license text itself
  and is ignored) for the installed version only; npm `node_modules/<name>/package.json` (`license`, the old `licenses` list) when its version matches. Libraries not installed here
  stay empty until the user's "Check" click, which also asks `api.deps.dev` (`licenses.py`: names and versions only, 8 at a time, cap 600, "non-standard" = unknown; several licenses on one
  version are joined with AND, the cautious reading). Result stored with the project's last check and re-applied to the list on reopening.
- Category (`license_kinds.py`, informational, not legal advice): permissive (MIT, BSD, Apache, ISC, PSF, ...), weak copyleft (LGPL, MPL, EPL, CDDL, EUPL), strong copyleft (GPL, AGPL, SSPL),
  unknown (no license, "UNKNOWN", proprietary text). SPDX expressions: `A OR B` takes the easier alternative, `A AND B` the stricter, `WITH` exceptions are ignored.
- UI: each library shows its license (red for strong, amber for weak copyleft); chips above the list count each category and filter it; the Check notice and the source lines mention deps.dev.
- Found by a live run on this repository (242 libraries, ~3 s): a leftover `~orge-0.1.0.dist-info` folder (half-removed reinstall) made pip-audit reject its whole input and the failure message
  showed only "^". Now such names are skipped (also in the library list) and the message is the ERROR line. Unit tests with fakes had not caught it.
- Verified live: deps.dev answered for Python and npm; 187 of 242 licenses came from installed copies, 55 from deps.dev, 5 stayed unknown (the project itself, a font package). Not verified: the
  office laptop's access to api.deps.dev.

### D-240 — Presentation making: a built-in skill plus two tools that build a real .pptx and look at it (user request 2026-10-09)
- Question: Claude Code has strong presentation skills; can Forge have the same? **Anthropic's own pptx/docx/xlsx/pdf skills cannot be copied**: their LICENSE.txt forbids keeping copies outside Anthropic's
  services and making derivative works (checked in github.com/anthropics/skills). So this is Forge's own work, using only its own ideas and the open python-pptx library (MIT).
- User choices (options discussed): output = real editable `.pptx` (alternatives: HTML deck exported to PDF; both); visual check = PowerPoint if installed, else layout rules only (alternatives: rules only;
  installing LibreOffice).
- Built: module `slides` (tier 5): `spec.py` (outline as JSON/YAML, ten layouts: title, section, bullets, two_column, image, table, chart, quote, stats, closing; mistakes reported in words), `themes.py` (clean,
  dark, warm; fonts every Office has), `fit.py` (text sized to its box, pessimistic estimate), `build.py` (python-pptx: every slide uses the "Title Only" layout so each has a real title; native charts and
  tables; speaker notes; alt text; nothing is a picture of text; min 16 pt; warnings name the slide), `preview.py` (PowerPoint exports a PNG per slide through PowerShell COM, paths via environment variables,
  Forge's own variables hidden (D-202), PowerPoint closed afterwards only if this started it). Tools `build_presentation` and `preview_presentation` (`tools/presentation.py`) run in Forge's own process, so the
  project's Python environment is not involved; python-pptx is the optional extra `forge[slides]` (added to Start-Forge.cmd). The built-in skill `make-presentation` teaches the story-first method, the outline
  format, the design rules and the build, look, fix loop. `Workspace.write_bytes` writes binary output through the same gate as text (jail, checkpoint, log).
- Verified live on this machine (PowerPoint installed): the real model loaded the skill, wrote an outline, built a 6-slide deck, had PowerPoint draw it and looked at the pictures, with no invented numbers
  (`tests/test_live_slides.py`, `-m live`; it keeps the deck and pictures in test-artifacts/slides-live/). Looking at the pictures found and fixed: centred titles, small table text, top-heavy short lists.
- Known limits: the pictures need PowerPoint (without it the model only has the rules; it is told to say so); the look is a template, not free design (Claude's skills can restyle anything), so decks
  are clean but plain; slide titles in the live run were topics rather than takeaways despite the skill; no slide master/template import, animations or speaker-view timings; the office laptop's PowerPoint COM
  behaviour (Protected View, policies) is untested.

### D-241 — Read and edit existing decks, and use a company template (user request 2026-10-09, after the comparison with Claude's skill)
- User chose to build the biggest practical gap first: reading and editing existing decks. Template use came with it, through the deck's own layouts.
- Tools (`tools/presentation.py`): `read_presentation` (read-only: every slide's layout, title, shapes with ids, tables, chart numbers, picture alt text, notes, and the layouts the deck offers;
  `.pptx` and `.potx` only; nothing is run) and `edit_presentation` (a list of operations applied in order to the deck loaded by python-pptx, so the deck's own formatting stays; if any step fails
  nothing is saved). Operations (`slides/edit.py`): replace_text (works across formatting runs, optionally in notes), set_text (new text takes the first run's and paragraph's look; two leading spaces =
  one bullet level), set_notes, delete_slide, move_slide, duplicate_slide (pictures and links are copied; a slide with a chart or embedded object is refused, not copied wrongly), add_slide (by the deck's
  layout name, fills title/body/placeholders, removes empty placeholders, optional position), update_chart (keeps the chart's formatting), update_table (same size only).
- Template use: `edit_presentation(path=template.potx, output=new.pptx, ...)`: a `.potx` opens as a deck built on its layouts (content type patched in memory), slides are added from its layouts and the sample
  slides deleted. A template is never overwritten (output required). `Workspace.write_bytes` records every save as a checkpoint, so in-place edits can be undone.
- Found by tests: a damaged `.potx` raised a raw zip error (now "could not be opened ... damaged or password-protected?"). Builder: sub-bullets now carry their bullet level, so reading a Forge deck shows indentation.
- Live check (real model): asked to describe a deck, retitle slide 2, add a "Risks" slide after slide 3 and save a copy, it used read_presentation + edit_presentation, did not rebuild, put the slide in the right
  place and left the original untouched (`tests/test_live_slides.py`). Not tried: a real company template (only a template made from a Forge deck), and PowerPoint's rendering of edited decks beyond the preview tool.
- Still not built (the rest of the gap to Claude's skill): free-form slide design, building a new deck directly on a template's styles through `build_presentation`, animations/comments/master edits, other formats (.docx, .xlsx, .pdf).

### D-242 — Free-form slide design (user request 2026-10-09, the next gap after D-241)
- New layout `freeform` (`slides/spec.py`, `slides/freeform.py`): the model places every element in inches on the 13.333 x 7.5 canvas, in drawing order. Elements: `text` (size, bold, colour, alignment,
  optional fill/line/rounded card, bullets, title/body/mono font, shrink-to-fit down to `min_size`), `shape` (rect, rounded, oval, triangle, diamond, chevron, pentagon, arrow_right, plus; label; rotation),
  `line` (connector with arrow head and dash), `image` (contain, or cover with centred crop; alt text), `chart`, `table` (the last three share code with the fixed layouts: `add_chart`, `add_table`,
  `add_picture` were extracted from the layout methods). Colours are theme names (`text`, `muted`, `accent`, `accent_text`, `surface`, `background`, `series1..6`) or `#RRGGBB`, so a deck stays consistent
  across the three themes. Every slide keeps a real title (navigation and screen readers); `title_visible: false` parks it above the slide for cover designs; `title_box` moves and sizes it.
- Guard rails, because nothing is laid out for the model (each names the slide and element): extends beyond the slide, unfilled text closer than 0.3 in to an edge, two elements colliding (a card or
  shape fully containing another element is not a collision), text not fitting even at `min_size`, text under 12 pt, text contrast under 4.5:1 (3:1 for large text) measured against what is really behind it
  (own fill, else the card it sits on, else the slide background), a picture without alt text. Found by the first test: even a hand-made test slide collided with its own title and put white text on orange.
- The skill (`make-presentation` section 6) carries the design knowledge: canvas and margins, type scale, grid and whitespace, colour discipline, structure by shape, and recipes (cover, three steps,
  comparison, big number, timeline, picture-led).
- Verified: unit tests; a hand-built cover, process diagram and deliberately bad slide looked right in PowerPoint pictures (the bad one tripped every check); and a live run: the real model designed a
  4-slide dark deck as free-form slides, previewed and looked at it (`tests/test_live_slides.py`, keeps the result in test-artifacts/slides-freeform-live/). Honest result: clearly better than the plain
  templates (bold cover, step diagram, comparison cards, closing line) but still conservative: it used rectangles where the recipe suggested chevrons and left empty space at the bottom of cards. The
  quality of a free design depends on the model; the checks stop the ugly mistakes, they do not make it a designer.
- Not built: gradients, shadows, rotated text, grouping, icons or an icon library, image generation, animations, master/template-aware free-form (free-form slides use the deck's blank "Title Only" layout and
  theme, not an imported template's look).

### D-243 — show_app: open the running app in the user's browser, only after proving it is the app (user request 2026-10-09)
**Context:** "Run the app" only started it; checks used a hidden browser. Ports are often taken by other programs, so an
answering port proves nothing. **Options:** (a) open the URL start_background printed; (b) a tool that first checks the
port belongs to the started process tree (psutil), then that the page answers (< HTTP 500), then opens it; (c) ask the
user each time. **Chosen:** (b), `tools/show_app.py`, local 127.0.0.1 only, no approval question (it only shows a page on
this computer). If the port is held by something else it names the holder and the model fixes it. When psutil cannot list
the process's sockets it falls back to the port the app printed itself. Prompt lines added to both system prompts.
**Not done:** the Auto-mode `full` level (nested shells/network/installs) still waits for the user's decision.

### D-244 — Rename the product to "DebCraft" (user request 2026-10-12; the visible part only)
Context: the rename was parked on 2026-10-09 (docs/TODO_LATER.md). Options: (A) visible name only; (B) A plus a `debcraft`
command; (C) full internal rename (package, `.forge` folders, `FORGE.md`, `FORGE_*`) with fallbacks to the old names.
Chosen: B. Everything people read says DebCraft (web UI and window title, prompts, CLI help, docs, scripts, tests);
`debcraft` is a second entry point next to `forge`; `Start-Forge.cmd` became `Start-DebCraft.cmd`. Kept on purpose: package
`forge`, `%USERPROFILE%\.forge` and project `.forge` folders, `FORGE.md`, `FORGE_*` settings, the `Forge` TypeScript type,
history in DECISIONS/CHANGELOG, and the repo path/URLs. Side effect: the name is 3 characters longer, so `E501` is ignored in
ruff (the formatter still wraps code). C stays a separate, later decision (it needs read-the-old-name fallbacks).

### D-245 — Aesthetics are part of done: style audit on every screenshot, a look before a UI task closes (user request 2026-10-12)
Context: a Vite + React + Tailwind demo came out unstyled (Tailwind produced no CSS) and DebCraft could not improve it, even with a design skill and the screenshot given: it tuned classes that generated nothing.
Options: (a) only a stronger prompt; (b) prompt + skill + measurable checks + a gate; (c) a separate design-reviewer subagent. Chose (b); (c) can follow.
Built: `tools/ui_audit.py` — `browser_screenshot` now audits the rendered page (utility classes with no effect = BLOCKER, default look, overflow, default links/buttons, unpadded or touching boxes, contrast, tiny text, broken images, no type hierarchy) and takes `width`/`height` for a phone view; `tailwind_setup_problem` reads package.json/vite.config/CSS (v3 vs v4 mix-ups). `task_update(done)` after UI edits now also needs a screenshot after the last edit, no BLOCKER, and a sound Tailwind setup; the end-of-turn nudge asks for the same. New built-in skill `ui-design-quality` (setup fixes, design decisions, layout, components, UX, look-and-fix loop) and a line in both system prompts.
Limits: the audit measures, it does not judge taste; the model still has to critique the image. Not yet run against a real Forge session on the office laptop.

### D-246 — Retry reason visible in the web chat; no style questions (user report 2026-10-12)
Context: after a "restyle like Stripe" request DebCraft asked which style (the user answered after ~20 minutes), then the chat showed only the word "retry", status Idle, and no change was made. The web chat prints a notice's `text`, and the retry/fallback notices had none, so the failure reason was hidden.
Done: retry and fallback notices now carry a readable `text` (model, reason, delay, attempt); both system prompts say not to ask the user to pick a design direction (choose, state it in one line, offer alternatives afterwards).
Open: the actual reason for the failed call on the office laptop is unknown until the user reads the new retry text.

### D-247 — show_app tries every loopback address; rules for design variants (user report 2026-10-12, three-designs run)
Context: asked for three design variants opened in the browser, DebCraft never opened them (show_app "ConnectError") and handed over commands; the user opened ports 5171-5173 by hand and all three showed the same dark "design-c" page (tab titles all "design-c"), although the model called them distinct and polished.
Cause 1: show_app connected to 127.0.0.1 only. Vite on Node 17+/Windows listens on `localhost` = ::1, so 127.0.0.1 refused while the user's browser worked. Fix: try 127.0.0.1, localhost, [::1], open the first that answers; message names all three.
Cause 2 (not proven, project files not seen): variants were copies of one project or all three ports served design-c. Added section 6 to the ui-design-quality skill: separate folder and own title per variant, different on palette/type/layout, prove each port serves its own folder (titles, sha256 of screenshots, file hashes), run servers itself and never hand commands over.
Open: no code-level check yet that variants differ (a screenshot-hash comparison tool would be the next step).

### D-248 — start_background takes a cwd and names the folder it started in (user's hash check, 2026-10-12)
Finding: the three design folders were different (own sources, own titles) but all three ports served design-c. Cause: start_background had no folder argument and used the shell's persistent working directory, which an earlier `cd` had left in design-c; the model assumed otherwise.
Done: `cwd` argument (relative to the repository root, same rule as run_command, clear error for a missing folder); the result now ends the ready line with `[cwd: ...]`; the ui-design-quality skill tells the model to pass it. Test: tests/test_tools.py.

### D-249 — Make DebCraft's UI/UX output as good as possible: reference code, an independent design critic, a stricter audit (user request 2026-10-12)
Context: Claude's own designs were clearly better than DebCraft's. Causes: advice without examples (a model copies concrete good code far better than it follows prose), the builder grading its own work, an audit that only caught gross defects, and no check that variants differ.
Options: (a) more prompt text; (b) reference implementations + independent critic + stricter measurable checks; (c) a bigger or different model for design. Chose (b) now; (c) is the user's call.
Built:
- `skills/ui-design-quality/recipes/`: `index.css` (Tailwind v4 tokens, @utility components, focus ring, reduced motion), `landing-reference.tsx` (complete page: nav, hero with drawn visual, stats, steps, validated form with success state, FAQ), `palettes-and-fonts.md` (palettes by mood, font pairings, scales, layout ideas so variants differ, assets without photos, dashboard/form/settings/empty-state patterns). Built, audited (clean at 1280 and 375) and looked at before shipping; the build caught a v4 mistake (custom classes must be `@utility` to be used in @apply). `pyproject` ships nested skill files.
- `design-critic` subagent (`subagents/critic.py`): fresh context, browser + view_image, scores seven lines 1-5, concrete fixes, VERDICT SHIP/REVISE. `task_update(done)` after UI edits now also needs a SHIP after the last edit, or three REVISE rounds (then the model states what is open). Subagent browsers are now closed when the subagent ends.
- Audit additions: font families, text sizes, text colours, corner radii, missing/small h1, over-long text lines, false-positive fixes (SVG art, collapsed details). `browser_screenshot` flags a screenshot pixel-identical to one of another URL (the three-identical-designs failure).
Tested: unit tests; live test (real Azure model) shows the critic rejects an unstyled page with a fixes list.
Not tested: a full live build with the new skill and critic on the office laptop; the critic's SHIP threshold may need tuning there. Cost per UI task rises (critic runs up to 3+ times); accepted under D-161.

### D-250 — DESIGN.md workflow, taste checks, redesign protocol, brand references (user pointed at awesome-design-md and taste-skill, 2026-10-12)
Context: two public repositories were evaluated. VoltAgent/awesome-design-md (MIT): ~83 per-brand DESIGN.md files, nine sections, exact tokens; says it claims no ownership of any site's identity. Leonxlnx/taste-skill (MIT, copyright Leonxlnx): a ~10,000-word anti-generic skill family with design dials, a redesign audit protocol and a long checklist; opinionated (bans Inter/serifs/Lucide, Next.js and GSAP assumptions) so not usable whole.
Options: (a) bundle both; (b) distil the useful, checkable parts in our own words, fetch brand files on demand, let the user install taste-skill themselves with `forge skill add`; (c) ignore. Chose (b): no third-party text copied into the repo, no stale bundle, no licence notice duty.
Built: `recipes/design-md-template.md` (nine-section project DESIGN.md with design read and three dials) and a workflow in the skill (write it first, build to it, the critic scores against it; a user-supplied one is binding); skill section "Taste" (generic tells, one accent, type, hero fold, copy, motion rules), section 7 redesign protocol (scan, prove styling, diagnose, DESIGN.md, fix in priority order, critic; a second "restyle" request means the first change was too small), section 8 on-demand reference styles from awesome-design-md via web_fetch (fails gracefully on a locked-down network). Audit: first action below the fold, headline over three lines, em dashes, placeholder text; static source scan for alert(), scroll listeners, `transition: all`, `h-screen`, lorem/John Doe, `<img>` without alt. The reference page became asymmetric (sticky intro and stacked steps instead of three equal cards) and was re-audited (clean at 1280 and 375).
Open: raw.githubusercontent.com reachability from the office laptop is untested; the user may install taste-skill separately (`forge skill add https://github.com/Leonxlnx/taste-skill`) if they want its full rule set.

### D-251 — A tested library of CSS, motion and design competencies instead of vendored third-party code (user: no stronger model available; asked to bring in CSS, design and animation skills from open-source sources, 2026-10-12)
Context: the model cannot be upgraded, so quality has to come from what it is given. Web research (shadcn/ui, Magic UI, Aceternity, React Bits, daisyUI, Flowbite, HyperUI, Open Props, Motion, GSAP, Animate.css, Hover.css, icon sets, modern CSS scroll-driven animations and view transitions) showed: most are MIT and fine to install or copy-paste; React Bits is MIT + Commons Clause, Aceternity has per-component terms, GSAP's free licence is not open source and has a competing-builder restriction, Hover.css reports conflict. A model imitates concrete working code far better than it follows prose, and a locked-down laptop may have no network.
Options: (a) vendor third-party components (licence notices, stale, size); (b) write an original tested library inspired by the techniques and list vetted external sources with licences and install commands for when the network allows; (c) rely on the model's memory. Chose (b).
Built in `skills/ui-design-quality/recipes/`: `style-directions.md` (ten complete visual directions), `css-techniques.md` (modern CSS catalogue), `motion.css` + `motion.tsx` (reveal, stagger, count-up, marquee, shimmer, skeleton, spotlight, tilt, border beam, aurora, glass, grain, shine, float; reduced-motion safe), `components-native.tsx` (dialog, tabs, toasts, empty state, skeleton, sortable table with no dependency), `sources.md` (vetted sources, licences, install commands, what to avoid). All code was built with Vite + Tailwind v4 (`tsc -b` strict), run in headless Edge (no console errors, dialog/tabs/table work, audit clean) and looked at; the screenshot caught two visual flaws the audit cannot (shimmer text invisible on dark, beam drawn as a wedge), both fixed.
Also: `browser_screenshot` with full_page now scrolls through the page first, otherwise reveal-on-scroll sections photograph blank (and the critic would see blank sections).
Limits: the visual effects are checked by eye here, not by a test (tests only confirm files ship and the audit/scroll-through behave); real-run effect on the Azure model is untested.

### D-252 — Audit learns three visible defects found in the user's three-design screenshots (2026-10-12)
Context: with the cwd/show_app fixes the three ports served three different pages, but all three showed bugs the audit missed: a sticky header with no background that text scrolls under, form fields with border and fill almost equal to the background, and text clipped by an overflow-hidden card. The C page was identical to the first run's, so DebCraft had probably reused the existing projects instead of rebuilding (these shots show the older pipeline).
Done: audit checks for see-through sticky/fixed bars, nearly invisible form fields (border/fill contrast under 1.4:1) and clipped text (sr-only and marquee excluded); calibrated so the reference page and motion kit stay clean. Test added.
Next: rerun with "rebuild from scratch" wording (or delete designs/) so the critic, recipes and audit actually shape the output.

### D-253 — The picture DebCraft looks at is shown in the chat (user request 2026-10-12)
Context: the chat said "Image sent to the vision model: .forge/screenshots/shot-….png" but showed nothing, so the user saw no sign of the work being done and could not follow what the model was judging.
Options: (A) thumbnail under the notice with click to enlarge; (B) an expandable image inside the tool card; (C) a gallery panel. Chose A: smallest change, visible where the user already looks, no new panel (new panels are a design-theme decision for the user).
Built: `view_image` and `browser_screenshot` notices now carry a workspace-relative `path` (the screenshot notice used to carry an absolute machine path); `GET /api/image?path=` (web/image_routes.py) serves images only (png, jpg, webp, gif), inside the open workspace, never secret files, 12 MB cap, behind the same local login and token as every other route; the chat shows a thumbnail (width up to 384 px, tall full-page shots cropped to their top 288 px), click opens the whole image, Esc or a click closes it. A broken or missing image simply hides the thumbnail. Tests: tests/test_web_image_e2e.py (headless Edge decodes the image, enlarges and closes it, both notice kinds; the route refuses non-images, paths outside the workspace and missing files); screenshots in test-artifacts/react-ui/.
Limits: only images inside the workspace are shown (an image the user granted from elsewhere is still sent to the model but not shown); the thumbnail is not part of the Run map.

### D-254 — Component-library mode (daisyUI, MUI, shadcn/ui, Tabler) and an audit that reads modern colours (user asked about MUI, opensourceui, Tabler, Uiverse, daisyUI, 2026-10-12)
Context: five sources were evaluated. daisyUI (MIT, Tailwind plugin, themes) is the best fit for Tailwind apps; MUI (MIT core; paid MUI X Pro and Store) suits data-heavy business apps but looks generic unless re-themed; Tabler (MIT, Bootstrap 5) gives about 5,000 icons and dashboard layouts to copy as patterns, not to mix with Tailwind (its bundled ApexCharts has revenue-based terms); opensourceui (MIT, Tailwind v4 + React 19) is a promising same-stack source but unjudged; Uiverse elements are MIT only per the Galaxy archive (the site's own terms could not be read), quality varies.
Built: `recipes/component-libraries.md` with a mode decision table and quickstarts that were built and looked at: daisyUI v5 with built-in themes and a custom brand theme (theme must be set on `<html>`, a wrapper leaves a white strip), MUI with a hard re-theme (bundled Fontsource fonts render offline; system props belong in `sx` or the strict TypeScript build fails), shadcn/ui and Tabler notes; `sources.md` rows for MUI, Tabler, opensourceui, Uiverse Galaxy; TODO items for the rest.
Found while testing: the audit read colours with a regex on `rgb()` strings, so oklch and color-mix colours (Tailwind v4's default palette and daisyUI) gave false contrast and field findings. Colours are now converted to sRGB through a 1x1 canvas; outlines drawn on a sibling fieldset (MUI) or a tight wrapper border now count for the nearly-invisible-field check. Tests added (oklch).

### D-255 — One TODO list with a build order; external ideas are distilled, studied first and never vendored (user, 2026-10-12)
Context: open work was spread over TODO.md, docs/TODO_LATER.md and docs/PPT_PARITY.md, and the user asked for one place and for the work to be ordered so it can be taken up later. Along the way the user evaluated many external repositories and skills (awesome-design-md, taste-skill, MUI, Tabler, opensourceui, Uiverse, daisyUI, shadcn/ui, Magic UI, Superpowers, mattpocock/skills, Anthropic's skills, awesome-agent-skills, awesome-claude-code, claude-code-best-practice).
Decisions:
1. `TODO.md` is the single list of open work: section 0 is the build order (phases A to G with dependencies and a "done when"), sections 1 to 6 hold the items with stable IDs (`D` design, `L` libraries, `X` parallel, `S` speed, `C` coding, `W` documents, P0.x to P3.x presentations), section 7 the history. The other two files keep background and sizing only. CLAUDE.md carries the rule.
2. External ideas are distilled into our own words, tested here, and shipped in the skill folder; third-party code is not vendored, because it goes stale, bloats the context, needs licence notices and conflicts in style. Libraries that must be installed are documented with their licences in `recipes/sources.md`.
3. Anthropic's `docx`, `pdf`, `pptx` and `xlsx` skills are source-available and are not copied; DebCraft builds its own Word, Excel and PDF capabilities with the same clean-room rules already used for presentations (TODO W0 to W5).
4. Before any development derived from Superpowers or mattpocock/skills, the two repositories are studied in detail and what to take is decided in `docs/SKILLS_STUDY.md` (TODO C18); the dependent items are blocked until then. The user chose not to add further items from awesome-claude-code ("too much").
5. The model cannot be upgraded, so quality comes from process and assets: an asset catalogue with search and copy tools is the foundation for every library (TODO L0), the coding benchmark and speed benchmark come before tuning (C1, S2), and nothing that trades quality for speed or cost is accepted (D-161).
Not built yet: everything in TODO.md sections 1 to 6; the user's rerun of the three-design task on the office laptop is the next input.

### D-256 — design-critic runs in parallel; screenshot names are unique (TODO X1, overnight run 2026-10-13)
Context: only explore and reviewer could overlap. Each subagent has its own tool context and browser session, so two critics do not share a page; the only collision was the screenshot file name (stamp to the second).
Decision: `design-critic` joins `PARALLEL_SUBAGENT_TYPES`; `unique_stamp()` in tools/browser.py adds nanoseconds and a random suffix. Verifier and debugger stay serial. Tests: tests/test_parallel_critic.py.

### D-257 — Build-process rules in the skill and round-trip hints in the prompts (TODO D1, L7, S5, X5; overnight 2026-10-13)
Decision: `ui-design-quality` gets section 5b (plan sections and tokens, write each screen whole, one section at a time, rewrite instead of a fifth patch). Both system prompts get one bullet: parallel independent tool calls, whole-file writes, installs in the background. Why: cheap, reversible, no quality cost (D-161). Measuring the effect waits for the timing breakdown (S1) and the rerun.
Deferred: X3 `run_parallel` is parked because it touches the approval gate (security-relevant); options are recorded in TODO.md.

### D-258 — Timing: waiting for the user is separate from tool time (TODO S1, overnight 2026-10-13)
Context: `tool_call_finished.duration_s` included the time an approval card or question was open, so a 5-second install behind a 25-second approval looked like a 30-second tool. Model latency and first-token time were already recorded.
Decision: `duration_s` now excludes the wait; `waited_s` (only when at least 0.01 s) holds approval time, and for ask_user, propose_requirements, propose_plan and request_user_action the whole call counts as waiting. `forge log-summary` prints the total. Older logs simply have no `waited_s`. Run-map display is left open in TODO.

### D-259 — `forge run-report`: a scrubbed report to send for analysis (TODO C17, overnight 2026-10-13)
Decision: `engine/run_report.py` builds a markdown report from events.jsonl only (so no source code): the run summary, subagent table with cost, critic/reviewer verdicts with score lines, failed tool calls, screenshot count and the final task list. The redactor masks secrets; the workspace path, the home folder and the account name are replaced with placeholders. Written to `.forge/run-report.md`. Options not taken now: a UI download button (open in TODO).

### D-260 — Token lint in the screenshot audit (TODO L8, overnight 2026-10-13)
Decision: `tools/token_lint.py` reads the project's own UI source (no browser). It speaks only when the project defines tokens (`@theme` or a `:root` with custom properties). Flags: a file with three or more distinct hard-coded colours that are not token values; font families outside the theme tokens; Tailwind default palette classes (`bg-blue-500`) when the project defines its own colours. Not counted: black, white and grey (and translucent overlays of them, spread of 8 or less), colours that are only the fallback of `var(--x, ...)`, token values written literally, one or two odd colours (drawn graphics). Our own recipes folder passes the lint (test). Why a threshold of three: SVG illustrations legitimately use a few literal fills; three or more is drift. Off-scale spacing is not linted (arbitrary values are too common to judge without false alarms); revisit after the rerun.

### D-261 — Harness parity audit against Claude Code (TODO C12, overnight 2026-10-13)
Method: read the code for each feature the TODO lists; nothing was run.
| Feature | DebCraft today | Gap | Next step |
|---|---|---|---|
| (a) hooks | only `hooks.post_edit` (config, run after each successful edit; loop.py `_post_edit_hooks`) | no before-tool hook, no stop hook (verify before a turn ends), no session-start hook | the stop hook is the same job as the quality gates in `C2`; build both together after `C1` shows which checks pay off. A before-tool hook touches the approval gate (security-relevant): discuss first |
| (b) path-scoped rules | FORGE.md per project/repository (memory/scope.py), always loaded | no instruction file that loads only when matching files are touched | small: a `paths:` front-matter list in extra rule files, loaded when a read or edit matches; useful for Mode A on big repos |
| (c) forked skills | skills load into the main context; subagents exist for explore, reviewer, verifier, critic | no skill that runs in its own context and returns a conclusion | covered in practice by subagents; a `context: fork` flag is cheap but only worth it if `S4` shows noisy skills fill the window |
| (d) rewind | `/checkpoints`, `/undo`, `/rewind <id>` (slash_commands.py) and UI controls (Panels.tsx, Composer.tsx) | none found | nothing to build |
| (e) context warnings | micro-compaction at `micro_compact_at` with a notice, auto-compaction at `auto_compact_at`, `context_updated` events feed the UI meter | no warning before quality drops, no hint to the model | add a notice at about 70% of the budget; measure with `S4` first |
Skipped, already present: plan mode, subagents, skills, memory, MCP, compaction, history. No gap is built in this pass: each needs either the benchmark (`C1`) or a security discussion.

### D-262 — Coding benchmark: tasks, runner and offline validation (TODO C1, overnight 2026-10-13)
Decision: ten pure-Python tasks across the tiers that need no package install (function, small module, bug fix, feature, refactor, CLI, performance, async, data pipeline), each with a prompt, a seed, hidden tests and a reference solution. The normal suite validates the fixtures without a model (reference passes; hidden tests fail without it); `norecursedirs` keeps pytest from collecting the hidden tests directly and ruff excludes the fixtures. `scripts/benchmark/run_code_benchmark.py` runs DebCraft on each task in a Mode B workspace and scores with the hidden tests. Why not run it tonight: it spends Azure tokens and the result is only useful when you choose the baseline moment. Hidden-test design rule: test behaviour the prompt states, never an implementation detail (the async retry-delay test measures time instead of patching `asyncio.sleep`).

### D-263 — The contrast finding names a passing colour (TODO L9 part 1, overnight 2026-10-13)
Decision: when text fails WCAG AA, the audit now lists up to three failing elements with their colours, the ratio and the nearest passing colour (the same hue moved toward black or white in 5 % steps), and tells the model to fix the token rather than the single element. The model applies the change instead of hunting for a colour. Overflow and missing-alt fixers are not built: overflow has no safe automatic fix without seeing the layout, and alt text needs the image's meaning.

### D-264 — Import check before a task closes (TODO C8, overnight 2026-10-13)
Decision: `tools/import_check.py` reads the absolute imports of the Python files DebCraft wrote in this workspace (from the change log, so a host repository's old imports never count) and resolves each in the app's own interpreter with its real PYTHONPATH and without Forge's private variables. A module that does not exist, or a `from x import y` where x has no name y and no submodule y, makes `task_update(done)` refuse with the list and the way to check (`pip show`, install, `dir()`). Not flagged: imports inside `try/except ImportError` or `if TYPE_CHECKING`, any name that matches a file or folder in the project (src layouts, conftest paths), libraries that fail to import for other reasons, and the project's own modules (never executed). Why a gate: invented packages and names are the cheapest wrong code to detect and the model cannot see them without running. Risk: a false positive costs one extra turn; the check never raises and says nothing when the interpreter cannot run it. Both system prompts also say to check the installed version and docs before using an unfamiliar library.

### D-265 — Asset catalogue, search and copy tools, first slice (TODO L0, overnight 2026-10-13)
Context: the model sees one line per skill and `load_skill` lists at most 60 files, so hundreds of assets would be invisible.
Decision: (1) asset standard in `skills/ui-design-quality/assets/README.md`: one markdown file per asset with front-matter (id, type, title, summary, moods, products, density, dependencies, files to copy, licence, source, tested, optional preview). (2) `forge.parity.assets` validates and builds `catalogue.json`, `INDEX.md` and `LICENSES.md` (`scripts/build_asset_catalogue.py`, `--check` for CI; a missing licence, file, wrong folder or duplicate id fails the build; a missing preview is only a warning until previews exist). (3) Tools `find_asset` (deterministic keyword search, no model call; id and title words weigh 3, moods/products/tags 2, summary 1) and `add_asset` (copies the asset's files through the write jail, skips identical files, refuses to replace changed ones without `overwrite`, appends the licence to NOTICES.md, returns the usage note; a copied UI file counts as a UI edit for the task gates). Names are generic (`find_asset`, not `find_design_asset`) because coding assets (C3, C5) will use them too. (4) Migrated the three existing recipe sets: 11 visual directions (generated from style-directions.md, which stays as the readable overview and is checked against the assets), 15 motion effects and 6 native components (they point at the existing tested files, which are copied whole). (5) Retrieval test: 20 prompts, the expected asset in the top 3 for at least 90 % (now 100 %). Honest caveat: this test uses my own wording against my own catalogue; the live test with the real model (TODO L0 g) is the real measure and is not built yet.
Not done: previews, routing-skill split, palettes/CSS techniques/library notes migration, `tested` fields for directions say they were not rendered individually.

### D-266 — Python project skeletons through the asset tools (TODO C5, overnight 2026-10-13)
Decision: new built-in skill `python-project` (SKILL.md plus `assets/skeleton/` and `templates/`). Four skeleton assets: `skel-python-package`, `skel-python-cli`, `skel-async-worker`, `skel-fastapi-service`. `add_asset` gained `variables` for `{{placeholders}}` in file contents and target paths (a missing value is reported before anything is written). Template files are stored with a `.tmpl` suffix so the repository's own ruff, mypy and pytest never read placeholders as code or as config. Every skeleton passes `ruff check`, `ruff format --check`, `mypy --strict` and `pytest` on a fresh copy (tests/test_python_skeletons.py); that test caught two real lint errors while it was being written. Setuptools is the build backend (nothing to download); tests run without installing (`pythonpath = ["src"]`). Preview warnings now apply only to visual asset types.
Not done: coding skills of C3 (the skill text exists for skeleton use only), previews, a live test that the model finds a skeleton from a plain request.

### D-267 — Python recipes: short, tested, found through the catalogue (TODO C3 part 1, overnight 2026-10-13)
Decision: twelve `recipe` assets in the `python-project` skill. Each is 30 to 60 lines: rules first, then one code block starting with `# runnable` that tests/test_python_recipes.py executes (so a recipe cannot rot), then one or two sentences of extra guidance. Topics were chosen from what the benchmark tasks and the campaign apps needed: error handling, logging, settings from the environment, typing, asyncio, pytest, SQL, a security checklist (with a path-traversal guard), performance, refactoring and Python 3.11 to 3.14 idioms (version facts stated per release), CLI design. Recipes are found with `find_asset` (type `recipe`) and returned by `add_asset` (no files are copied). Recipe wording was written for a weaker model: rules in short imperative sentences, no jargon without an example.
While writing, a benchmark flaw was found and fixed: the seed of task t08 returned duplicates in order of the second occurrence while its docstring said first appearance, which would have punished a model that followed the docstring. The seed now matches its docstring.
Not done: the C3 topics listed in TODO; C7 (debugging) and C10 (tests that prove something) wait for the Superpowers/mattpocock study (C18).

### D-268 — Offline fonts: 14 families, 12 pairings, 1.5 MB budget (TODO L3 part 1, overnight 2026-10-13)
Context: pages built on an office laptop may not reach Google Fonts, and the model otherwise falls back to system fonts. TODO asked to decide the size budget first.
Decision: bundle at most 1.5 MB of woff2 (now 0.7 MB). Source: Fontsource's variable packages (`@fontsource-variable/*` 5.3.0, all SIL OFL 1.1), the Latin subset of the weight axis only (plus the Bengali or Devanagari subset for the two Indic families); italics, other axes and Latin-extended are left out to stay small and can be added by the install command. Each family folder holds the woff2 file(s), a generated `@font-face` stylesheet (`font-display: swap`, served from `/fonts/` so Vite's `public/` folder works) and the OFL text with the copyright holders. Catalogue: 14 `font` assets and 12 `font-pairing` assets by mood and product (warm editorial, elegant serif, bold poster, heavy grotesque, clean SaaS, precise fintech, playful rounded, geometric modern, journal, developer mono, Bengali, Hindi). `add_asset` now copies binary files unchanged. `tests/test_fonts.py` checks the budget, the licence text, that every stylesheet points at files that exist, and renders all 14 families in headless Edge from a local server with no outside request.
Not done: families beyond 14, italics, the audit warning for fallback fonts, preview images.

### D-269 — Motion kit part 2: 36 pure-CSS effects (TODO L2 part 1, overnight 2026-10-13)
Decision: one new stylesheet `recipes/motion-more.css` with 36 effects in seven groups (entrances, text, hover and focus, ambient backgrounds, feedback, 3D-lite, scroll). Pure CSS on purpose: no build step is needed to test it, and a weaker model cannot get a hook's dependencies wrong. Colours come from the theme variables with fallbacks, so it works before a palette exists. Scroll-driven effects sit behind `@supports (animation-timeline: ...)` and show the final state elsewhere. One reduced-motion block turns everything off. `tests/test_motion_more.py` builds a demo page with every class, loads it in headless Edge and checks each animation name or computed style, the marker growing, hover effects, the 3D flip, no console errors and the reduced-motion switch; the screenshots go to `test-artifacts/motion/` (looked at). Catalogue: 36 new `effect` assets, total 51 effects. The `type-writer` class sets a monospace font because its width is measured in `ch`.
Not done: the hook-based effects (split text, scramble, magnetic button, number ticker with easing, pinned scroll sequences), page transitions, previews per effect.

### D-270 — Showpiece effects in our own CSS, Magic UI documented (TODO L6 parts a to c, overnight 2026-10-13)
Decision: `recipes/motion-fancy.css` holds eight showpiece effects written from scratch (no Magic UI code copied or read): orbiting circles, rainbow border button (animated `@property` angle), shiny button, flickering grid, sparkles, warp background, dock magnification with neighbours (`:has()`), avatar stack. All pure CSS, catalogue entries (total effects now 59), Edge demo test (`tests/test_motion_fancy.py`: animations run, dots are in three different places, dock scales 1.5 and 1.22, no console errors, everything stops under reduced motion; screenshot looked at). `sources.md` documents how to use the real Magic UI with the shadcn CLI and its known failure points (path alias, missing Tailwind v4 keyframes, runtime dependencies, reduced motion), marked as not verified from this machine because the registry cannot be assumed reachable; the skill carries the rule of one core component plus one supporting effect.
Not done: beam, particles and globe (JavaScript/canvas), and verifying the real components, which waits on the registry check on the office laptop (TODO section 1).

### D-271 — Parallel checks without a new tool or a new approval path (TODO X3, option 1; the user asked for it on 2026-10-13)
Context: the gate takes one command string per call, so a `run_parallel` tool would either bypass per-command permission or change the gate.
Decision: no new tool. In `agent/parallel.py`, a `run_command` is parallel-safe only when it is on a whitelist of checkers and readers (ruff, mypy, pyright, flake8, pylint, bandit, pip-audit, eslint, tsc, black/prettier/isort with `--check`, `ruff format --check`, one pytest run, ls/cat/grep style readers) and has no chaining, redirect or substitution characters and no `--fix`/`--write`. The loop batches consecutive safe calls (at most four, at most one test run, never mixed with an unsafe call) and runs them with `asyncio.gather`. Every call still goes through `_run_one`, so the permission decision, sandbox and events are per command; an `asyncio.Lock` makes approval cards appear one at a time. Both system prompts tell the model to put its checks in one turn as plain separate commands.
Rejected: a `run_parallel` tool (needs one approval for a list, which weakens the per-command check); a broader whitelist (builds and installs write to shared folders and caches).
Tests: tests/test_parallel_commands.py (classification, timing of batches, serial approvals).

### D-272 — Verifier and design critic run together (TODO X4, overnight follow-up 2026-10-13)
Decision: the loop lets a `verifier` join a batch of read-only calls (the design critic, explore, reviewer), in either order, but never a second verifier and never beside the debugger (which runs commands). Why it is safe: each subagent has its own context and browser; the critic only looks; the verifier writes only under `tests/e2e/` and asks for approvals through the main channel, one card at a time (D-271); screenshot names are unique (D-256). The UI-evidence prompt now tells the model to start the app once with `start_background` and give the same URL to both in one turn. Known side effect: the verifier's tests may create records the critic then sees on screen; judge layout, not data. Tests: tests/test_agent_loop.py (timing of the combinations).

### D-273 — Section library and three templates, verified by building them (TODO L1 part 1, 2026-10-13)
Decision: 14 React sections in `recipes/sections/` (NavBar, HeroSplit, HeroCentered, LogoStrip, StatsRow, FeaturesAlternating, FeaturesBento, StepsTimeline, TestimonialFeature, PricingTiers, FaqList, CtaBand, ContactForm, FooterColumns, plus the ArtTile visual). They use only theme token classes (brand-*, ink-*, rounded-card, shadow-*, btn-primary, btn-secondary, card, eyebrow, field, font-display) and have no dependency, so a template's palette and fonts decide the look. Three templates in `recipes/templates/<name>/` each carry their own `index.css` (palette, radius, shadow, fonts) and an `App.tsx` composition: charity (Fraunces + Inter, warm red), saas (Plus Jakarta Sans + Inter, indigo, bento, pricing), portfolio (Playfair Display + DM Sans, near-black, square corners). Catalogue: 14 `section` and 3 `template` assets; a template copies its sections, tokens and fonts in one `add_asset`.
Verification (the point of the harness, `tests/vite_harness.py`): each template is added through the real tool into a workspace, then built with Vite + Tailwind v4 from the packages already in `ui-react/node_modules`, type-checked with strict TypeScript, opened in headless Edge at 1280 and 375 px and passed through DebCraft's own style audit; all sections also build together as a gallery where the form's validation and success state and the FAQ are exercised. The audit found three real problems while building (badge text with no padding, the word "Acme" as placeholder copy, an orphaned bento tile), all fixed; screenshots were looked at.
Honest limits: the visuals are abstract shapes, not photographs; three templates is far from the target of 20; nothing was compared against a human designer's work, so the critic score on a real run (TODO section 1) is still the real test. Tests skip when `ui-react/node_modules` is absent.
Also fixed while doing this (L0 item e): `load_skill` listed at most 60 files, so the growing asset folders pushed the recipes out of the model's view. The listing now shows each bulk folder (assets, fonts, templates, recipes/sections, recipes/templates) as one line with its file count and points to `find_asset`; other files are listed as before.

### D-274 — Presentation decisions 1 to 4 (user answers, 2026-10-13)
1. Design engine: both in stages. Keep improving the free-form element engine (P1 helpers first); start the HTML/CSS path (P3.1) only if the benchmark (P0) shows the engine's ceiling is too low.
2. Rendering: PowerPoint only. No LibreOffice and no own renderer; previews need PowerPoint on the machine and DebCraft states plainly when it is missing. This removes the HTML-render dependency of P3.
3. Icons and images: bundle Lucide (ISC) and Material Symbols (Apache-2.0) offline, with their licence texts, through the asset catalogue. An image model exists on the Azure side; the deployment name and the .env variable names are still needed from the user before any image-generation tool is built (API keys stay in .env only, D-204).
4. Reference decks: Claude-made sample decks as stand-ins, plus the company Office template(s) which the user can only provide from the office laptop; template-driven items wait for that file.

### D-275 — Answers to the open questions (user, 2026-10-13)
Documents: Excel first, then Word, then PDF; the optional `docs` extra (python-docx, openpyxl, pypdf, reportlab) may be installed through pip; sample documents still to come. `write_secret_values` and its five tests removed (the web app never writes keys; D-204). S7 and S8 (faster model for read-only agents, adaptive effort) not now, to be revisited after the speed benchmark. C18 (study of the Superpowers and mattpocock repositories) later; the items that depend on it stay blocked.

### D-276 — Presentation design lint and safe fonts (TODO P1.5 to P1.7, 2026-10-13)
Decision: `slides/lint.py` runs on every build. Per slide: a title that reads like a topic (under four words and no figure) or has more than 12 words. For the deck: three or more identical content layouts in a row, more than 60% of content slides text-only (bullets and two-column), and a thin filled rectangle near the title of a freeform slide. The builder no longer draws its own accent bar under titles. Fonts: the themes use Calibri (clean, dark) and Georgia + Calibri (warm), mono text is Courier New; Segoe UI and Consolas are gone because they are not on every Mac. The safe set is Arial, Calibri, Cambria, Georgia, Times New Roman, Courier New, Bookman Old Style, Century Schoolbook. Calibri is narrower than Segoe UI, so the fit estimate stays pessimistic. The skill carries the same rules as writing guidance. Existing test titles that were bare topics were rewritten as takeaways.
Not done: automatic dark/light sandwich check; a per-theme accent choice (left to the model).

### D-277 — Package validator for .pptx files (TODO P1.8, 2026-10-13)
Decision: `slides/validate.py` (standard library only) checks a finished package against the structural rules that make PowerPoint refuse a file or offer to repair it: it is a zip, `[Content_Types].xml` exists and every part has a type and every override names a real part, every internal relationship target exists and ids are unique, all XML parts are well formed, slide ids are unique and at least 256 and point to real slides, shape ids are unique per slide, `p:spTree` and `p:cSld` ordering, tables have as many cells in each row as grid columns, paragraph child order (`a:pPr` first, `a:endParaRPr` last), font sizes within the schema range, charts have `c:chart`, unique series indexes and their workbook relationship. `build_presentation` and `edit_presentation` run it on the bytes they write; a fault makes the tool result a failure that names each fault (the file is already written, and the message says so). Honest limit: this catches the usual causes of the repair prompt, it does not prove PowerPoint opens the file; only PowerPoint does, which P0.2 (office laptop) will confirm on real decks. It was written from the OOXML structure, not from any other implementation.

### D-278 — Contact sheets in the slide preview (TODO P1.1, 2026-10-13)
Decision: `preview_presentation` now also writes `contact-sheet-N.png` (12 slides per sheet, 3 columns, slide numbers on each tile, Pillow) next to the slide pictures and lists the sheets first with the instruction to judge flow and consistency before single slides. Without Pillow, or if writing fails, the tool falls back to the single pictures. The sheet is made from PowerPoint's own pictures, so it still needs PowerPoint (decision 2: PowerPoint only). Tested with synthetic pictures; not yet seen on a real deck (P0.2).

### D-279 — Layout containers for freeform slides (TODO P1.3, 2026-10-13)
Decision: `slides/layout.py` expands `row`, `column` and `grid` containers in the raw outline before validation, so the builder, the overlap check and the editing tools see only plain elements with coordinates (no change to the element model). Child keys `weight`, `length`, `cross` and `colspan` (renamed from `size`, which collides with a text element's font size) are consumed; containers nest up to four levels; every mistake (missing box, empty children, fixed lengths that do not fit, a colspan wider than the grid, no room after padding) is a layout problem in words that names the slide and element. Rounded to three decimals. Tests: tests/test_slides_layout.py, including a built deck of three cards with no warnings.

### D-280 — Rich text, spacing and vertical text in freeform elements (TODO P1.4, 2026-10-13)
Decision: a text element may set `rich: true` to use inline `**bold**`, `*italic*`, `[text](url)` and `{colour}text{/}` (`slides/richtext.py`); off by default so existing text with asterisks or brackets is unchanged. Also `line_spacing` (0.8 to 3, a multiple), `letter_spacing` (points, written as the run's `spc`), and `vertical` (`up` = bottom-to-top, `down` = top-to-bottom, written as `vert270` or `vert` on the body). The fit estimate measures the plain text (markup removed), divides the height by the line spacing, and swaps width and height for vertical text. An unknown colour name is a warning, not a crash. The package validator accepts the result. Not done: font size changes inside a line, per-run fonts, underline and strike-through, bullets with rich runs in the fixed layouts.

### D-281 — 19 slide themes and a brand kit (TODO P2.1 part 1, 2026-10-13)
Decision: `slides/themes.py` now has 19 themes (clean, dark, warm, forest, ocean, sunset, slate, midnight, paper, mint, plum, terracotta, mono, sky, coral, graphite, ruby, olive, indigo), four of them dark, each with a mood and topic words; `suggest_themes(topic)` ranks them and the skill table lists them (a test keeps the two in step). Every theme passes WCAG-style checks in tests: text on background and on cards 4.5:1, muted text 4.5:1, text on the accent 4.5:1, accent on background 3:1, and chart series colours are nudged toward the text colour only as far as needed to reach 3:1 against the background (so yellows and oranges stay visible). Fonts stay Calibri and Georgia (safe set, D-276). A deck's `theme` is now any of the names (unknown names give an error that lists them). `brand` in the outline overrides accent, background, text, muted, surface, accent_text and the two fonts; missing colours are derived (readable text, a surface mixed 8% toward the text, muted text moved until it reaches 4.5:1, accent_text black or white), and brand problems appear as deck warnings together with the font warning.
Not done: a logo in the brand kit, saving a kit with the project, font pairings beyond the safe set, user-visible theme previews.

### D-282 — Gradients, transparency, shadows, picture frames and backgrounds (TODO P2.2, 2026-10-13)
Decision: `slides/effects.py` writes the DrawingML python-pptx has no call for, in schema order (fill before outline before effects): linear gradient fills (`fill_to`, `gradient_angle`), fill transparency (`opacity` as an alpha), shadows (soft, lifted, hard), rounded and oval picture geometry, and sending a layer to the back. Freeform text and shape elements gain `fill_to`, `gradient_angle`, `opacity`, `shadow`; pictures gain `frame` and `shadow`; a slide gains `background_to`, `background_angle`, `background_image` and `scrim`. Background layers are full-bleed shapes at the back (not slide-background XML), so reading, editing and the validator treat them as ordinary shapes, and they are left out of the overlap check. The contrast check uses the worst gradient stop, blends transparent fills with the background, and for a background picture uses its average colour mixed with the scrim; text over a picture with a scrim under 0.3 gets a warning. A circle frame on a non-square box is a warning. The package validator passes every case (tests/test_slides_effects.py). Not done: picture transparency, per-corner radius, shape outlines with gradients.

### D-283 — Icons as native shapes, offline (TODO P2.3, 2026-10-13)
Decision: bundle Lucide (ISC; every icon, 1,877, with its search tags) and a curated 164 Material Symbols (Apache-2.0, outlined style) in `src/forge/data/icons/` as gzip JSON (160 KB), with both licence texts; `scripts/dev/build_icon_data.py` rebuilds them from the npm packages (`lucide-static` 1.55.0, `@material-symbols/svg-400` 0.48.0). `slides/icons.py` reads SVG path data itself (all path commands, arcs by the SVG endpoint-to-centre rules, curves sampled finely) and turns an icon into contours; the freeform `icon` element draws them as one native freeform shape (Lucide as round-capped outlines, Material as filled), recolourable and editable in PowerPoint, with alt text, optionally on a circle or rounded badge (icon at 56% of the badge). Why not pictures: no rasteriser is available offline (a browser would be needed), pictures cannot be recoloured, and native shapes survive any resize. `find_icon` searches by name and tag (plurals match). Tests: every bundled icon parses to finite points inside the frame; arcs, flags, relative and smooth commands; the element, badge, warnings (unknown name with suggestions, non-square box); the package validator accepts the output. Looked at in PowerPoint's own export (build machine has PowerPoint): outline and filled icons render crisply; large outline icons need a lower `weight`, which the skill says. Note for P0.2: PowerPoint picture export works on this build machine.
Not done: a bigger Material set (7,800 exist), two-tone icons, icons in the fixed layouts (stats, bullets).

### D-284 — Charts at full strength (TODO P2.4, 2026-10-13)
Decision: `slides/charts.py` replaces the old chart code; the `chart` layout and the freeform `chart` element share one options model (`ChartBase`). Kinds: clustered and stacked column, bar and area, line (smooth option), pie, donut, scatter, and column + line combinations with a second value axis (the line series are moved into a `c:lineChart` with its own hidden category axis and a right-hand value axis, written in schema order). Options: title, axis titles, Excel number formats on axes and labels, data labels (auto: on for pie, donut and single series), legend position or none, series colours, per-category colours, gridlines on/off, axis limits, gap width, second-axis title and format. Quiet defaults: no frame, light gridlines in the theme's surface colour, muted axis text, no tick marks, markers in the series colour. Data can come from a CSV or Excel file in the workspace (`data_file`: first column categories, other numeric columns series; thousands separators and a trailing % are handled; clear errors for a file with no numeric column). Warnings: more than 6 pie slices, a negative pie value, more than 14 categories. Found by looking at real PowerPoint renders: python-pptx's `chart.value_axis` returns the secondary axis once one exists, so the styling went to the wrong axis; axes are now addressed in document order. `docs` optional extra added to pyproject (openpyxl, python-docx, pypdf, reportlab; approved D-275) and openpyxl installed for the Excel test. BuildError moved to `slides/errors.py` so charts and builders raise the same type.
Not done: bubble charts, trendlines, error bars, charts with more than two axes, formatting edits of existing charts (P2.12), chart title position control.

### D-285 — Tables at full strength (TODO P2.5, 2026-10-13)
Decision: `slides/tables.py` replaces the old table code; the `table` layout and the freeform `table` element share `TableBase`. Cells are plain values or `CellSpec` objects (bold, italic, colour, fill, align, size, colspan, rowspan); merged cells are laid out on an occupancy grid, checked (every row must fill exactly the columns), and merged through python-pptx after the content is written. Options: relative column widths, per-column alignment (default numbers right, text left) and Excel-like number formats (`#,##0`, `0.0%`, `$#,##0.00`, `0.0"k"`), four styles (striped, plain, horizontal lines, full grid; borders are written as `a:lnL/R/T/B` before the fill, in schema order), header fill, bold first column, and a heat map that shades each chosen numeric column against its own range between two colours. Text colour on any custom fill or shade is chosen automatically (dark or light, whichever reads best). `split_rows` on the layout continues a long table on further slides with the header repeated, "(continued, n of m)" in the title and the notes only on the first; without it more than 10 rows still warns and names the option. Found by looking at the render: the first heat map normalised all chosen columns together and left small-valued columns unshaded, so each column is normalised alone. Tests: tests/test_slides_tables.py (formats, layout errors, alignment, merges, borders, heat map, splitting, package validity).
Not done: table styles from a template, cell borders per cell, images inside cells, formatting edits of existing tables (P2.12), automatic column-width fitting by rendering with PowerPoint (P2.18).

### D-286 — Diagram toolkit (TODO P2.6, 2026-10-13)
Decision: freeform elements gain an optional `id`; lines gain `start` and `end` anchors (`{"id", "side"}`) and `kind` (straight or elbow), so a connector is glued to the sides of shapes drawn earlier (rectangles and rounded boxes: sites top 0, left 1, bottom 2, right 3; ovals 0, 2, 4, 6; other shapes get the line at the right place without gluing) and follows them when edited in PowerPoint; a `group` element binds shapes by id; `align` (to left, center, right, top, middle, bottom) and `distribute` (horizontal or vertical, three or more) move the named elements before the slide is built. Seven recipes (`slides/diagrams.py`) expand in the layout stage into ordinary elements with ids, so the existing checks, editing and the validator apply: process, cycle, hierarchy, 2 x 2 matrix, timeline, funnel, roadmap. Found by looking at real PowerPoint renders: the elbow connector bends sideways first (bentConnector3), which is wrong for top-to-bottom trees, so the hierarchy draws a bus from plain lines (down, across, down); mid-tone funnel bars got dark text on lighter tints instead of borderline light text; roadmap cards fit their content. The element limit per freeform slide went from 40 to 80 because diagrams add connectors. Tests: tests/test_slides_diagrams.py (every recipe builds a valid slide with no warnings, glue sites in the XML, groups, align and distribute arithmetic, error messages).
Not done: elbow connectors for vertical flows (needs rotated connector geometry), curved connectors, SmartArt, diagrams with more than the listed item counts, auto-routing around obstacles.

### D-287 — Text measured by PowerPoint decides overflow (TODO P2.18, 2026-10-13)
Decision: `slides/measure.py` opens the saved deck in PowerPoint (same safety as the preview: the path in an environment variable, none of DebCraft's variables, a PowerPoint the user already had open stays open) and reads every shape's position and size, the true text height and width of text ranges (`TextFrame2.TextRange.BoundHeight/BoundWidth`) with the box margins, and the height tables grew to. `overflow_problems` turns that into sentences in inches: text taller than its box (with 0.04 in of rounding slack), a line wider than its box, and tables or boxes that run past the slide edge. `preview_presentation` appends the result to its answer (problems to fix, or "all fit their space"); without PowerPoint nothing changes and the build-time estimate stays. Not run on every build because starting PowerPoint takes several seconds. Validation of the estimate itself: a deck built from the normal title, bullets and stats layouts measures clean in real PowerPoint (tests/test_slides_measure.py, which needs PowerPoint and is skipped elsewhere), so the estimate is not producing false confidence on those layouts.
Not done: measuring inside table cells (only the table's grown height), measuring after the model's edits through edit_presentation, using the measure to auto-fit text sizes.

### D-288 — Decks built on a company template (TODO P2.10, P2.11, 2026-10-13)
Decision: the outline's `template` field makes `build_presentation` open the template (`slides/template_build.py`), drop its sample slides and map DebCraft layouts onto its own: title/closing, section, content (bullets), two-content use the template's placeholders and inherit its fonts and bullets; chart, table, stats, quote, picture and freeform slides use its title-only layout and draw in the free area, coloured from the template's theme (`slides/template.py` reads colour scheme, master colour map and fonts). 16:9 templates of any size work by scaling DebCraft's 13.33 in canvas; other shapes are refused with a message that points to `edit_presentation`. Missing layouts fall back to title-only/blank; empty placeholders are removed at the end. `analyze_template` (read-only tool) reports the same facts to the model. Options considered: rebuilding the deck through edit_presentation only (kept for non-16:9); copying template layouts into our own deck (loses masters).
Tested on templates generated from python-pptx's default (light, dark, other size, missing layout) and a PowerPoint render; the real company template is still to be tried on the office laptop.
Not done: layout pictures in the analysis, templates with unusual placeholders (listed as "other"), 4:3 templates.

### D-289 — Edit operations at full strength (TODO P2.12, 2026-10-13)
Decision: `edit_presentation` gained replace_picture (new image, same crop and frame), format_text (per run, a phrase is split out of its run), set_theme (fonts and colours in the theme part, so master text follows), table row/column add/delete (table keeps its width, frame height follows), change_chart_type (rebuilt in place from the same data, same name and stacking position), format_chart, set_footer/slide numbers (placeholders cloned from the layout), set_notes_bulk, delete_shape (groups whole), remove_empty_placeholders, and shapes can be found by `"text:..."`. Code in `slides/edit_more.py`, `edit_objects.py`, `edit_find.py`, `edit_text.py`; images come through the same read-image hook as build_presentation.
Not done: chart axis formatting, edits inside merged cells, colour of single points except in pies. Footers on decks DebCraft built double up with the footer it draws itself.

### D-290 - Corporate template mode: samples first, then layouts, then creative slides in the theme (TODO P2.21, 2026-10-13)
User request: given a corporate template, read it, pick the slide that fits each piece of content and put the content into it; when nothing fits, create a new slide that keeps the theme.
Decision: `slides/template_samples.py` reads the template's own sample slides (kind, slots with their current words, repeated groups, fixed company text); `template_build.py` keeps them while building and removes them at the end. Order of preference per slide: (1) the outline's `template_slide {source, fill}` copies a named sample and fills it; (2) ordinary title/section/bullets/two_column/stats/closing slides are matched automatically to a sample of that kind (round robin); (3) otherwise the template's layout; (4) charts, tables, images and freeform slides are drawn in the template's free area in its colours and fonts and carry the plain decoration its samples share. Slots left unfilled are removed (no sample wording stays); spare repeated groups go with their backgrounds and the rest are re-centred; too many items are refused. `analyze_template` lists samples and can render them with PowerPoint for the model to look at.
Options considered: only layouts (what P2.10 did: loses the template's designed slides); letting the model edit the template with edit_presentation (works but slow and fragile); picking the sample by an extra model call inside the builder (more cost, less predictable; the agent already sees the pictures).
Not done: inserting into empty picture placeholders, samples with charts (copy refused; the chart is built on a layout instead), automatic agenda/timeline matching. Tested on a generated "Acme" template with a PowerPoint render; the user's real template comes from the office laptop.

### D-291 - Slides in the web UI (TODO P1.2, 2026-10-13)
User chose (from three options): an inline strip of thumbnails in the chat plus a full viewer. `preview_presentation` publishes a `slides_ready` notice (deck, picture paths, speaker notes) next to its normal result, so the model's view is unchanged. The chat shows the strip; a click opens a viewer (thumbnails, big slide, notes, arrow keys, Esc). A .pptx opened in the Files tab shows the same viewer using `GET /api/slides` (the pictures PowerPoint already made, speaker notes, whether the deck changed since) and `POST /api/slides/render` (renders on demand, only where PowerPoint is available). The pictures go through the existing narrow `/api/image` route; the new routes use the workspace jail and the secret check. Code: `web/slides_routes.py`, `ui-react/src/components/Slides.tsx`.
Not done: rendering without PowerPoint (a LibreOffice or in-browser renderer was not asked for), editing slides in the UI.

### D-292 - Benchmarks run requests in parallel; PowerPoint jobs take turns (2026-10-13)
The deck and code benchmarks take `--parallel N` (4 is a good start): requests run at the same time, each with its own DebCraft home and workspace, results reported in order. Parallel runs share one PowerPoint, and preview/measure quit PowerPoint when they started it, so the first to finish would close it under the others: `slides/powerpoint_lock.py` makes PowerPoint jobs take turns across processes with a lock file (a stale one is taken over after 5 minutes). The speed benchmark is deliberately not parallel (shared rate limits and CPU would skew the timings). The test suite already runs in parallel (`pytest -n 6 --dist loadfile`).

### D-293 - add_slide copies the deck's own look and lands before the closing slide (2026-10-13)
Baseline-1 and -2 (request d07) showed the model adding a slide after "Thank you" in a different style, whatever the skill text said. The rule moved into the tool: `add_slide` without a layout copies the deck's last text slide (`like` picks another), puts the new title and lines in its two main texts, drops the copied wording, and places the slide before a closing slide (a last slide of a few words saying thank you, questions and the like). With a layout name the position default is the same. Not done: slides that must hold a chart, picture or table in the deck's look (use `like` on a text slide, then update_chart / replace_picture).

### D-294 - `cards` and `steps` layouts (2026-10-13)
Baseline-2: nine of twelve decks were still judged "too many plain bullet lists" although the skill and lint said otherwise: a row of cards needed a hand-placed freeform slide, so the model took the easy bullets. Two ordinary layouts make the better choice as cheap as bullets: `cards` (2-4 cards with heading and text, optional numbered badges) and `steps` (2-5 numbered steps joined by a line). Drawn in the theme, centred in the free area, sized to fit with a warning when text does not; in a template deck they use the template's own sample of that kind (cards / steps) when it has room for all items, else draw in the template's theme. Code: `slides/layouts_more.py`. To be measured by baseline-3 (share of bullet slides, judge polish).

### D-296 - `forge template-probe` (2026-10-13)
The company template can only be opened on the office laptop. `forge template-probe <template>` (slides/probe.py) reads it as DebCraft would, builds a probe deck on it with placeholder text (each sample slide with normal and with long text, each ordinary layout, chart, table, diagram), renders pictures and contact sheets with PowerPoint, measures overflow, and writes `report.txt`, `probe.json` and the pictures; `--hide-text` keeps the template's words out of the report. The user sends back the report and contact sheets, so fixes can be made without the file. Steps are in docs/TEMPLATE_PROBE.md. Nothing is sent anywhere by the command.
### D-295 - Automatic quality gates before a task is done (TODO C2, 2026-10-13)
`tools/quality_gates.py`, called from `task_update(done)` after the import check, on the Python files DebCraft wrote this task: ruff (the project's own rules when it has any; otherwise real bugs only: syntax errors, pyflakes, mutable defaults, `raise ... from`, and complexity above 15), mypy only when the project configures it, bandit (medium and above, asserts and non-crypto random skipped) only when it is installed. Tools are taken from the workspace's own environment, ruff also from DebCraft's; a tool that is missing is skipped, never a blocker. Findings (at most 8 per tool, 10 shown) go back to the model; after two rounds on one task the next `task_update` is accepted whatever the findings, so a wrong finding cannot trap the model in a loop. `.forge/gates.json` switches everything off (`enabled`) or each tool and `max_complexity`. Options considered: a hard block until clean (loops on false positives); a warning only (ignored, as the lint warnings on decks showed); running the project's whole configured lint command (unpredictable, slow).
Not done: coverage of changed lines, pip-audit in the gate (the Dependencies tab has it), format checks (a formatting nit is not worth a round), JS/TS gates (eslint/tsc exist in the parallel check whitelist but not as a gate). To be measured on the coding benchmark (quality and time).

### D-297 - Path-scoped rules (TODO C12 b, 2026-10-13)
A big repository's rules should not all sit in the context all the time (Claude Code's `.claude/rules` with `paths`). `parity/path_rules.py`: a Markdown file with a `paths:` list in its front matter (flow list, comma line or block list; globs with `**`, `*`, `?`, a pattern without a slash matches in any folder) is a rule. Folders: `<forge home>/rules` (every project), the repository-level folder's `rules` (this repository or host profile, so Mode A needs no file in the user's repo), `<workspace>/.forge/rules`. When the model reads, writes or edits a file that matches, the rule is appended to that tool's result, once per rule per session, capped at 600 tokens, at most 4 rules per call. Rules without `paths` are ignored (always-on text belongs in FORGE.md). The agent loop owns the hook (`RULE_TOOLS`), the session host builds the folder list and reloads on refresh. Options considered: pinning all rules (what FORGE.md does: costs context all the time); a `read_rules` tool the model must remember to call (it forgets); a pinned item replaced per file (breaks the prompt cache).
Not done: a UI to write rules (files only), rules for search results, glob negation.

### D-298 - Context-usage warnings (TODO C12 e, 2026-10-13)
Claude Code tells the user when the context is filling up; DebCraft compacted silently. After each model call the agent loop compares the context fill with two thresholds (`context.warn_at` 0.7, `context.warn_again_at` 0.9 of the usable window) and shows a notice once per level: the percent, that DebCraft summarises on its own at the auto-compact point, and what the user can do (`/compact [what to keep]`, a new requirement for unrelated work, `/clear`); the second level says answers get slower and less reliable. The level resets after the context drops below 60 percent (a compaction or `/clear`). Only the main coder agent warns, not subagents. Logic in `context/warnings.py`. Not done: a coloured meter in the top bar (the percent is already in the context event), automatic compaction earlier than today (the thresholds for that are unchanged).

### D-299 - Follow-up to baseline-3 (2026-10-13)
Found by rebuilding the baseline-3 outlines with the new `scripts/dev/overflow_check.py` (no model run): (1) the PowerPoint overflow in d03/d17/d18 came from the new `cards` and `steps` layouts: the fit estimate was too optimistic and the text boxes small. Now the text fits into 88 percent of the width and 85 percent of the height of its box, cards and steps use up to 4.6 / 4.4 in of the free area, the quote mark's box is taller; d03 went from 12 overflows to 0. (2) PowerPoint's bound width of wrapped text can exceed its box by a few points: the width check now has 0.2 in of slack (`measure.py`). (3) d07: the model's batch added a slide and then moved "slide 5" to 6, undoing the tool's own placement. `add_slide` now says where the slide landed and that no move is needed, and a layout name on a deck without placeholder slides (a DebCraft-built deck) copies the deck's look unless `exact_layout` is set. (4) Speaker notes: a deck-level warning when slides have no real notes (fewer than 6 words), which also covers template slides; the skill says notes on every slide with content and facilitator notes for workshops.

### D-300 - Template slides: synonyms, and content that would be lost fails the build (2026-10-13)
baseline-4 (d13, a template with sample slides): the model filled a stats sample with `value`/`label` (the sample's parts are number/heading/text) and a bullets sample with `bullets` (the slot is `body`), got build warnings, never rebuilt, and the delivered deck dropped the numbers and the asks. Now `fill` understands common synonyms (bullets/points/content -> body; value/figure/metric -> number; label/title -> heading; description/detail -> text; with a fallback to the nearest part the sample has), and an explicit `template_slide` whose content still has no place makes the build FAIL with the sample's slots, not a warning the model can skip. Automatic matches (our own mapping) still only warn. Also: the repeated-layout lint ignores `template_slide`; the d07 request now says "just before the thank-you slide" (the old wording "final slide" made the placement before the thank-you slide look wrong to the judge).

### D-301 - Study of Superpowers and mattpocock/skills (TODO C18, 2026-10-13)
Both read (README and the skill files for subagent-driven development, parallel agents, to-tickets, implement-spec, code-review, tdd, systematic debugging, codebase-design, domain-modeling); both MIT, ideas taken in our own words. Written up in docs/SKILLS_STUDY.md with a take/adapt/skip table. Taken: the builder protocol (brief file in, report file out, four statuses, no blind retry, fix loop of five with a stronger model late, a breaker ruling at the cap, a progress ledger that survives compaction), two-axis review, the task graph with blocking edges and a frontier run in parallel (with our own concurrency cap and write-scope check, which implement-spec lacks), test-first and four-phase debugging as nudges, deep-module guidance and light glossary/ADR records. Skipped: grilling interviews (we have propose_requirements and ask_user), issue-tracker integration, the bootstrap skill. Unblocks X2, X7, C4, C6, C7, C13, C16, C19-C21, D7.

### D-302 - Servers become ready when their port answers (TODO S6, 2026-10-13)
Found in speed-2: four 60-second waits (two `start_background`, two `monitor`) for a plain `python -m http.server` because Python buffers its output when piped, so the "Serving HTTP" line the model waited for never arrived. Now (1) every command runs with `PYTHONUNBUFFERED=1`, (2) `start_background` reads the port from the command (`--port`, `-p`, `http.server N`, `host:port`; ports below 1024 are not guessed) when there is no `{port}` placeholder, and (3) a process is ready as soon as its port answers, whether or not the expected line was printed. Tests start a real server with a pattern that never matches and expect it ready in under 20 s.

### D-303 - Prompt cache and context size measured (TODO S3, S4, 2026-10-13)
`scripts/dev/cache_report.py` over the speed and coding runs: 80 to 94 percent of input tokens were served from the cache, one run had a single miss (call 4 of 11 in t14: 20k cached -> 8k, 12k tokens re-read), so trimming and compaction are not breaking the prefix. The first model call is long only on spec-heavy tasks (t14 89 s, 7.6k output tokens; t12 51 s; t11 41 s): that is reasoning time, which D-161 says not to cut. The context peaked at 11 to 26 percent of the window in all 25 deck, coding and speed runs with no compaction at all, so keeping the context leaner would save nothing at this task size; the usage warnings (D-298) cover long sessions. No code change.

### D-304 - Where the time went, in the Run map (TODO S1, 2026-10-13)
The Run map's header now has a bar and legend built from the events: model calls (`llm_call` latency), tool time (`duration_s`, which already excludes waiting), waiting for the user (`waited_s`), and the rest (engine work and overlap), with the wall time first. Derived from events like everything on the map, so a reopened project shows it too. Hidden for runs under 5 seconds. Not done: per-agent splits and a chat summary at the end of each run (`forge log-summary` has the text form).

### D-305 - Parallel builders (TODO X2, 2026-10-13)
`spawn_subagent` has a `builder` agent: it gets a brief and a `folder`, may write (and move, delete) only below that folder, runs in its own shell session (working directory per session) with its own free port (ports handed out are reserved for 3 minutes so two builders never get the same one), cannot start helpers or ask the user, runs its own checks and ends with one of four statuses (DONE, DONE_WITH_CONCERNS, NEEDS_CONTEXT, BLOCKED; no status counts as BLOCKED). The controller saves its report to `.forge/builders/<name>-report.md` and appends a line to `.forge/builders/ledger.md`; the result text tells the main agent what to do for that status. The agent loop runs builder calls of one turn side by side when their folders are disjoint, at most `limits.max_parallel_builders` (default 3; 0 or 1 switches it off); approvals stay one at a time (the existing lock). The protocol follows docs/SKILLS_STUDY.md; the fix loop (five rounds, a ruling at the cap) is taught in the `parallel-builders` skill, not hard-coded. Honest limit: the write jail covers the file tools; a shell command inside a builder can still write elsewhere, so the builder's commands start in its folder and its prompt forbids leaving it. Not yet measured: it needs the three-design task end to end (speed benchmark, S2).

### D-306 - Automatic parallel planning, conservative (TODO X7, 2026-10-13)
Plan tasks (`propose_plan`, `update_plan`) can carry `folder` (where the task writes) and `resources` (exclusive things: a fixed port, the db schema, a root package.json). `workflow/scheduler.py` computes the frontier (pending tasks whose dependencies are done; unknown dependencies and cycles make a task serial) and picks the largest batch it can prove independent: separate non-overlapping folders, no shared resource, at most `limits.max_parallel_builders` (default 3). A task without a folder never runs in parallel. The new `run_ready_tasks` tool starts that batch as builders (D-305) at the same time, records each status on its task (BLOCKED and NEEDS_CONTEXT mark the task blocked), and sets `last_edit_step` (and `last_ui_edit_step` when the folder gained page files), so `task_update(done)` still requires a passing test run and a look at the page: nothing built in parallel is counted without the main agent proving it. When fewer than two tasks qualify it says why and the main agent works serially (the safe fallback); `max_parallel_builders` of 0 or 1 is the off switch. Integration, the whole-app tests and the single design review stay with the main agent (parallel-builders skill). Options considered: a fully automatic planner that decides the graph itself (rejected: the model already plans, the scheduler only proves independence); an optimistic scheduler with conflict detection after the fact (rejected: wasted builds). Not done: a per-branch cost and time view in the Run map (the builders appear as agents with their own cost), measuring speed-up and quality on the three-design task.

### D-307 - Adaptive reasoning effort not adopted (TODO S8, 2026-10-13)
Measured the existing `FORGE_ADAPTIVE_EFFORT=low` switch (low effort for steps after read-only tool results) on t01-t14: 18 percent less wall time, 21 percent less model time, 16 percent lower cost, but 307 instead of 309 hidden tests (t01 lost two edge-case tests on slug cutting at word boundaries). D-161 rejects a speed change that costs quality, so the default stays the configured effort; the switch remains as an opt-in experiment. One run per arm: a repeat (three runs per arm) is the way to reopen it, and the saving would have to hold on a request type where edge cases matter less than in this benchmark.

### D-308 - Coding-quality skills and the two-axis code review (TODO C4, C6, C7, C9, C19, C20, 2026-10-13)
Built from the C18 study (docs/SKILLS_STUDY.md), own words. Skills: `test-first` (spec first, written without waiting for approval; vertical slices with a verified red; behaviour through the public interface; expected values from an independent source; never weaken a test; the whole suite at the end), `debugging` (a fast deterministic reproduction first; root cause before any fix; one hypothesis, smallest change; stop after three failed fixes), `deep-modules` (small interface, deep behaviour, the deletion test, two adapters make a seam, design it twice), `project-docs` (glossary and light decision records, decided without an interview). Candidate solutions judged by tests are a section of `parallel-builders` (C9). The `code-review` agent (`subagents/code_review.py`) runs two reviewers at once in fresh contexts, one against the project's documented standards plus a smell list, one against the request; reports stay apart (about 400 words each), blocking findings must quote evidence that is really in the file (the existing `verify_findings`), a closing line gives counts and the worst finding per axis, and one `VERDICT: SHIP|REVISE`. The spec axis is skipped when no request is known. An optional gate (`review.gate`, off by default) refuses `task_update(done)` for a code task until a SHIP review ran after the last edit, two rounds then the task may close. The system prompts tell the model when to load these and to treat a review as a colleague's (check, fix the real findings, answer a wrong one with evidence). Not measured yet on the benchmark as a gate; the reviewer can be the fallback model by setting `llm.roles.reviewer`.

### D-309 - Tests that prove something (TODO C10, 2026-10-13)
`tools/test_quality.py`: static warnings (a test with no assertion, `assert True`, a comparison of an expression with itself, a test that mocks three things and checks little) join the quality gate as `tests:` findings for changed test files, and a `mutation_check` tool makes up to eight small deliberate mistakes in a source file one at a time (flipped comparison, + for -, and for or, True for False, a function returning None), runs the tests after each and reports the mistakes nothing noticed; the file is always restored. It runs only when the model asks for it (a few test runs).

### D-310 - Guided script for user actions (TODO C21, 2026-10-13)
`request_user_action` with three or more steps also writes `.forge/handoff/<title>.ps1`: a PowerShell walk-through that shows each step, waits, shows the check command and runs it only after the user agrees, and saves a result file. Step text and the command pass through the redactor, here-strings cannot be broken out of, no variables or files are read or printed. The card's step list gets one extra line with the command to run it. The script parses as valid PowerShell (tested).

### D-311 - Skill style and the skill-use rule (TODO C13, 2026-10-13)
Every skill description now starts "Use when ..." so a weaker model can choose by situation; Gotchas sections exist for the skills with observed failures; `scripts/dev/add_gotcha.py <skill> "text" --task <id>` appends a dated entry. The system prompts carry a short skill-use rule (read the index, load a skill that plausibly applies, say "Using <skill> to <purpose>", no excuses, user instructions beat skills). Open: the retrieval test (does the model pick the right skill from its description) and a benchmark comparison with and without the rule.

### D-312 - Web design: variants compared, screens guarded, the design concept enforced (TODO D3, D4, D6, D7, D8, 2026-10-13)
D3 `compare_designs` (tools/visual_diff.py): the layout similarity of two screenshots is how alike their edge structure is (colour and text do not count; a first try with a difference hash called a sidebar layout and a hero layout alike), above 0.75 a pair is TOO SIMILAR; given each variant's folder it also flags the same first colour or first font in the DESIGN.md files; a BLOCKER tells the model to change the layout and typeface, not just the colours. D6 `visual_baseline` / `visual_check`: approve a screenshot per screen, later compare a new one: share of changed pixels (tolerance 24 per channel, noise under 0.2 percent counts as unchanged), the changed rows, a red diff picture under `.forge/visual/`. D4: all three speed-benchmark page redesigns shipped without a DESIGN.md although the skill asks for it first, so `write_file`/`edit_file` now refuse the first page or style file (html, css, scss, jsx, tsx, vue, svelte) of a project without a DESIGN.md in its folder, a parent folder or docs/, with the list of what to write (colours, type roles, ASCII wireframe, alignment rule, principles); at most twice per session, builders (write jail) and DESIGN.md itself are exempt, `ToolContext.design_first` is the switch. D7: the critic's round note tells the builder to take a fresh screenshot and check each suggestion against the page before applying it. D8: sections 0d (token plan, boldness in one place, structure as information, error copy, a named cliche list) in `ui-design-quality`, in our own words. To be measured on the page-redesign speed task (does the DESIGN.md step improve the quality score and cost time?).

### D-313 - Reference pictures for the bundled templates (TODO L10, 2026-10-13)
The model has vision, so a picture of a template says more than its description. `scripts/dev/build_reference_shots.py` builds each `template` asset the way the asset tests do, photographs it in headless Edge at 1280 and 375 px (full page, capped at 3000 and 3600 px of height) and writes JPEGs (about 120 to 200 KB each) to `assets/preview/<id>-desktop.jpg` and `-mobile.jpg`. `add_asset` copies them to the project's `.forge/reference/` and tells the model to open them with `view_image` and match the feel, not the texts; `find_asset` marks assets that have pictures. Pictures per direction and per section need a demo page each and are not done. Remake the pictures after changing a template.

### D-314 - Accessibility pass for decks (TODO P2.9, 2026-10-13)
`slides/accessibility.py`: `check_deck` reads any .pptx (document title, a title on every slide, alt text on pictures, charts and tables, table header row, the title read before other text, footer read last, vague link text, text language, chart colours that fall together in a colour-blind view) and the `check_accessibility` tool reports it; `improve_deck` runs at the end of every build and repairs what needs no guessing: document title, language on every text run (`Deck.language`, default en-US), reading order, table header flag, alt text for charts and tables from the slide title. The reading order is also the drawing order, so a shape only moves when that cannot change what is seen: the title does not go behind a shape it overlaps, a footer does not go on top of a later shape it overlaps (a first version moved titles behind background pictures and broke three tests). `slides/colorvision.py` simulates protanopia, deuteranopia and tritanopia (Machado et al. 2009) and `accessible_palette` chooses the chart colours from the theme: the combination (accent always kept) with the best worst-case separation, then the closest pair is pulled apart in lightness while keeping 3:1 against the background. All 19 themes reach a separation of at least 17.5 (CIE76) for two and three series; four or five series are only partly separable (the median is 18.5 and 15.5), so the check warns and the skill says to add data labels. Pictures' alt text stays the model's job (`alt`).

### D-315 - Real master, layouts and theme in generated decks (TODO P2.7, 2026-10-13)
`slides/masters.py::install_master` rewrites python-pptx's 4:3 Office template for each deck: the theme part gets the DebCraft colour scheme (text, background, muted, surface, palette as accents, links) and font scheme; the master gets a scheme-colour background, left-aligned bold title style, 20 pt body style and title/body/date/footer/slide-number placeholders at the builder's places; only four 16:9 layouts remain (Title Slide, Title and Content, Title Only, Blank). Footer and slide number are real placeholders (the number is a `slidenum` field), no longer text boxes. Options: (a) keep hand-drawn slides (status quo, no re-theming); (b) real master + placeholders (chosen); (c) also move body text into body placeholders (rejected for now: layouts position text freely, and the fit/measure code depends on explicit frames). Slides still carry explicit colours and positions, so a theme change in PowerPoint re-colours the background, footer, number and new slides but not hand-set colours on existing slides. Checked in PowerPoint (render) and `validate_package`.

### D-316 - Slide features: hidden, transitions, animations, sections, comments (TODO P2.8, 2026-10-13)
`slides/features.py` writes the XML python-pptx lacks: `show="0"`, `p:transition` (fade, push, wipe, split, cover; speed; auto-advance), entrance effects in the main sequence (appear, fade, wipe; on click, with or after the previous), the `p14:sectionLst` extension and classic comment parts (modern comments are read only). Outline: `hidden`, `section`, `transition` (also on the deck), `animate` (all content of the slide on one click); edit operations `hide_slide`, `set_transition`, `animate`, `clear_animations`, `set_sections`, `add_comment`; `read_presentation` lists them. Deleting or moving slides keeps sections valid; duplicating keeps hidden, transition and animations. Options for animations: per-bullet build (rejected: needs paragraph-level targets, easily broken by edits), whole-slide on one click (chosen for the outline), per-shape through the edit operation. Verified by opening a built deck in PowerPoint (sections, hidden flag, transitions, 2 effects, 1 comment all read back).

### D-317 - Reading decks out: Markdown, pictures, conversion (TODO P2.16, 2026-10-13)
`slides/extract.py`: `deck_markdown` (slides as headings, bullets by level, tables, chart data, links, alt text, notes, comments, hidden flag, sections, transition and animation summary; footer and slide number left out) and `extract_pictures`. `slides/convert.py`: PowerPoint (PowerShell and COM, same pattern and cross-process lock as the preview) converts old formats to .pptx and decks to PDF. Tools: `read_presentation` gains `format: outline|markdown` and opens old formats through PowerPoint; new `convert_presentation` (to pptx, pdf or pictures). The contact sheet per slide already exists in `preview_presentation`. Note: PowerPoint opens any text file named .ppt as an outline deck, so the "refuse old formats" test now fakes "no PowerPoint".

### D-318 - Review mode (TODO P2.17, 2026-10-13)
`slides/review.py::review_deck` + tool `review_presentation`: deterministic findings with a fix hint each, for any .pptx: story (label titles, long or repeated titles, too many content slides for the minutes), density (words per slide, bullets per box, long paragraphs), consistency (more than two font families, many sizes, text under 12 pt, titles off their usual place), contrast (explicit text colour against the shape or slide fill, 4.5:1, 3:1 for large text), layout (shapes off the slide, overlapping text boxes, four same layouts in a row, text-only decks, empty placeholders), notes, plus the accessibility findings. Options: (a) a model-written critique (variable, costs a call, cannot be tested), (b) deterministic checks the model acts on (chosen; the model still looks at pictures for story and taste), (c) both (the model already does (a) when it previews). Fixing is done by the model with the edit tools; no automatic fix mode, because most fixes are content decisions.

### D-319 - Duplicating slides with charts (TODO P2.13, 2026-10-13)
`slides/clone.py::clone_part` copies a part and everything it points to (chart XML, embedded workbook, chart style and colour parts, images) under new part names, keeping relationship ids because the chart XML refers to them; it refuses parts outside charts, embeddings, media and drawings. `duplicate_slide` uses it for charts; ole objects, video, audio, SmartArt data still refuse with the instruction to build a new slide. The same function serves the import of slides from another deck (P2.14). Checked: the copy and the original update independently, `validate_package` is clean, PowerPoint opens the deck with both charts.

### D-320 - Import, merge and split (TODO P2.14, 2026-10-13)
`slides/importer.py` + `clone.py::copy_slide`: `import_slides` copies slides between decks (edit operation `import_slides`; tools `merge_presentations`, `split_presentation`). Options for keeping the source's design: (a) copy shapes onto the target's layouts only (loses master art such as logos), (b) clone the source master, layouts and theme into the target (chosen as `keep`; a master with identical XML, theme and layout names is reused, so merging two decks built with one theme adds no master), (c) flatten master art onto each slide (rejected: breaks re-theming). Master and layout ids are renumbered to stay unique; part names are allocated through the memo because cloned parts are not yet linked into the package (a first attempt wrote duplicate part names, caught by `validate_package`). Different slide sizes force `match` and scale top-level shapes (text sizes unchanged). Slide-jump links to the other deck are dropped; video, audio, OLE and SmartArt refuse. A merge adds a section per source deck. Checked in PowerPoint: a merged clean + midnight deck shows each part in its own look, charts intact.

### D-321 - Raw-file escape hatch (TODO P2.15, 2026-10-13)
Tools `unpack_presentation` / `pack_presentation` (`tools/presentation_raw.py`, `slides/rawpackage.py`). Unpack writes only XML parts (pretty-printed when that cannot change text) to `work/<name>_xml/` with a manifest; pack starts from the original file, swaps in the folder's XML, adds new files, drops removed XML parts, validates with the P1.8 validator and refuses when PowerPoint would repair. Options: (a) unpack everything including pictures (many writes, large, no benefit), (b) XML only, binaries stay in the original (chosen), (c) let the model run zip tools in the shell (no validation, jail bypass risk). Safety: archive checks before reading (entries, total size, per-entry size and compression ratio, unsafe names, encryption), DOCTYPE/ENTITY refusal, macros and executables refused, external links the edit adds are reported. The same archive and XML checks are to be applied to every deck the tools open (TODO P3.4).

### D-322 - Storyline guides (TODO P2.20, 2026-10-13)
`skills/make-presentation/storylines.md` (read with `load_skill file="storylines.md"`, linked from section 1): eight guides (board update, pitch, QBR, design review, training, project status, proposal, all-hands) with slide order using our layouts, counts per length, speaker-note style and what to avoid, plus a pre-build checklist. Kept out of SKILL.md so the skill stays short for decks that need no guide. A test keeps the layout names in the guides valid.

### D-323 - Security review of the presentation tools (TODO P3.4, 2026-10-13)
Reviewed every deck tool against hostile files; written up in docs/PRESENTATION_SECURITY.md. Changes: `rawpackage.check_package` (archive limits, unsafe names including NTFS streams and device names, DOCTYPE/ENTITY refusal) now runs in `open_deck` for every tool; PowerPoint automation starts with macros force-disabled and the previous setting restored; skill gotcha that deck text is data. Options for external links: (a) strip all on open (changes the user's file on a round trip), (b) never follow, report new ones on pack (chosen), (c) ask on each. Risk R56 recorded.

### D-324 - Performance and size of decks (TODO P3.3, 2026-10-13)
Measured with a 151-slide deck (bullets, charts, tables, cards): build 86 s, review 25 s, accessibility check 6 s before; 3.9 s, 3.2 s and 1.1 s after. The cost was python-pptx resolving the position of footer and slide-number placeholders (which inherit it) through XPath on the layout and master at every read, many times per slide in the overlap checks. `slides/geometry.py::Geometry` reads each shape once per pass and answers inherited positions from a per-layout table (equal to python-pptx for every shape of a built deck, tested; the cache holds the elements so a freed lxml proxy cannot reuse an id). Also: `slides/images.py::prepare_image` (exif rotation, 2560 px long side, JPEG q85, big photo-like PNGs become JPEG, transparency kept, unknown formats and failures untouched); build warning above 20 MB; PowerPoint time limits grow by 2 s per slide (preview, measure, convert); the preview tool lists at most 30 single pictures and points to the contact sheets. Options for pictures: (a) leave them as they are (files of 60 MB, sideways photos), (b) shrink at build (chosen), (c) ask the user each time. Not changed: time limits for build itself (it is fast enough), chart or table size limits (the 10-row table cap and bullet limits already bound slides).

### D-325 - Presentation documentation (TODO P3.5, 2026-10-13)
`docs/PRESENTATIONS_GUIDE.md` (how to ask for a deck, work with files and templates, edit, review, combine, convert; what needs PowerPoint; limits) and `docs/GALLERY.md` with contact sheets in `docs/gallery/`, generated from a deck-benchmark run by `scripts/dev/make_deck_gallery.py` (six decks from `baseline-3`: the request, slide count, judge average and PowerPoint's own pictures, 110 to 170 KB each). Rerun the script after a better benchmark run to refresh the gallery. The user guide is for the person asking; the skill stays the model's instruction.

### D-326 - Image generation tool (TODO D5, 2026-10-13)
`tools/imagegen.py::generate_image(prompt, path, shape, style, quality)` calls an Azure image deployment (`images.generate`, base64 reply, saved through the workspace). Settings in the .env file: `AZURE_IMAGE_DEPLOYMENT` and `AZURE_IMAGE_API_VERSION` (user gave `aicloud-dall-e-3` and `2023-12-01-preview`) required; `AZURE_IMAGE_ENDPOINT` and `AZURE_IMAGE_API_KEY` optional, defaulting to the main resource. The prompt is redacted before sending, content-filter refusals and failures become plain messages, 12 pictures per session. Licence: the picture comes from the user's own Azure deployment, so no third-party licence; the tool tells the model to say the picture is AI-generated. **Live check 2026-10-13 against the build machine's resource: the deployment name is found but Azure answers 410 ModelDeprecated (DALL-E 3 is retired there), so a real picture was not produced; only transport-level tests ran.** The tool turns that 410 into a message asking for a deployment of a current image model. If that model is gpt-image-1, `style` and `response_format` do not apply, sizes are 1024x1024, 1536x1024 and 1024x1536: add that mapping once the user names the new deployment.

### D-327 - Image generation moves to Vertex AI; Azure images dropped (TODO D5, 2026-10-13)
User decision: "do not use the azure image generation". Reason found by checking: both Azure resources' `aicloud-dall-e-3` deployments answer 410 ModelDeprecated and neither has a `gpt-image` deployment (all deployments of both resources listed). `tools/imagegen.py` now calls Vertex AI through the google-genai SDK with the same Application Default Credentials as the Gemini chat provider: `generate_content` with `response_modalities=["IMAGE"]` and an aspect ratio for Gemini image models (default `gemini-2.5-flash-image`), `generate_images` for names starting `imagen`; `GEMINI_IMAGE_MODEL` in the .env file picks the model; the Azure settings and DALL-E parameters (style, quality) are gone. Redaction, session cap (12), path checks and plain failure messages stay (D-326 replaced). Not verifiable on the build machine (no Google credentials): `scripts/dev/image_smoke.py` is the live check for the office laptop. The user's `~/.forge/.env` still holds four unused `AZURE_IMAGE_*` lines (one is a key): they can be deleted.

D-327 update (2026-10-13): the user ran the live check on the office laptop and a picture was generated, so Vertex AI image generation is verified there.

### D-328 - find_image / fetch_image and the reachability smoke test (TODO D5, 2026-10-13)
User request: a find-image tool, and a smoke test that gives the complete picture of what can be reached. `tools/image_sources.py` (providers) + `tools/findimage.py` (tools): Iconify (icons, licence per set), Openverse, Wikimedia Commons, NASA without a key; Pexels, Unsplash, Pixabay when `PEXELS_API_KEY`, `UNSPLASH_ACCESS_KEY` or `PIXABAY_API_KEY` is in the .env file. Only licences allowing commercial use and changes are listed (CC0, public domain, CC BY, MIT, ISC, Apache-2.0, the three sites' own licences; non-commercial, no-derivatives, share-alike, unknown are dropped). `find_image` asks all fitting sources at once and names every source it could not reach with the reason and a hint (certificate, proxy, DNS, block page). `fetch_image` downloads into the project (public addresses only, every redirect hop checked, 25 MB cap, image content only, SVG with scripts or outside links refused), records the file in NOTICES.md and returns the credit line and alt text; Unsplash's download ping is sent; nothing is hot-linked. Wikimedia refuses anonymous agents, so requests carry a descriptive User-Agent with the repository address (found by the live run: 403 before). `scripts/dev/reach_smoke.py` probes 23 resources (the image sources through DebCraft's own code with a real download each, GitHub raw and API, shadcn registry, npm, PyPI, jsDelivr, unpkg, osv.dev, Google Fonts, Fontsource, Vertex AI, Google sign-in, the Azure and Tavily-platform hosts from the .env file, MDN), classifies each failure and writes `reach-report.md` and `.json` (no keys). Result on the build machine: 23 of 23 reached, 3 optional keyed sources skipped. Options for sources: (a) bundle everything offline (huge, stale), (b) search live and download on use (chosen; icons also stay bundled for offline work), (c) only one provider (single point of failure).

### D-329 - The picture ladder: bundle, fetch, generate (TODO D5, 2026-10-13)
User liked "bundle, fetch and generate". Made real: (1) bundle: the 1877 Lucide and 164 Material icons that ship for slides (P2.3) are now also offered by `find_image` first (ids `bundled:...`) and `fetch_image` writes them as standalone SVG files in a chosen colour and size (`slides/icons.py::icon_svg`; colour validated, so no attribute can be injected), offline; (2) fetch: online sources as in D-328, and every picture fetched is kept in a local library (`~/.forge/library/pictures` with an index and its licence, `tools/picture_library.py`, up to 2000 pictures) that `find_image` searches first, so a second project finds it without a network; the library only ever grows by use, nothing is bulk-downloaded; (3) generate: `generate_image` (D-327); (4) draw SVG or diagrams. The skills for decks and web pages state the order. Not done: bundling more icon sets (Tabler, Phosphor, Heroicons are MIT and would add roughly 0.5 MB each; add if the user wants more variety offline), a UI for browsing the library.

### D-330 - Any open font on request (TODO L3, 2026-10-13)
User request: wide font support and downloading instructed fonts whenever required. `tools/font_sources.py` + `tools/fonts.py`: `find_font` searches the Fontsource catalogue (about 2,100 families; fetched once, kept 7 days in `~/.forge/library/fonts/catalogue.json`, falls back to the 14 shipped families offline; only OFL-1.1, Apache-2.0, MIT, ISC and UFL-1.0 are offered, icon fonts left out; search by name, category and script words such as Hindi or Bengali). `fetch_font` writes the weights, scripts and formats asked for into the project: woff2 plus a complete `@font-face` CSS file (rebuilt from every file present, so a second call keeps the first call's weights), and ttf plus `install-fonts.ps1`, a per-user install without admin (copy to `%LOCALAPPDATA%\Microsoft\Windows\Fonts` and an HKCU registry entry); the user runs it, DebCraft never installs anything outside the project (a write outside the jail is a security decision). Fonts the user names by address (`url`: a font file or a zip, archive and name checks, private addresses refused, licence unchecked and recorded as such) are handled the same way. Every download is kept in `~/.forge/library/fonts/<id>/` and used first, so a repeat needs no network. Decks: the build note and `lint.font_warning` now say what to do for a font that is not on every computer, and `slides/installed_fonts.py` (registry) flags a deck font that is not installed on this Windows computer, because the PowerPoint preview and the fit check would otherwise use a substitute unnoticed. Not done, on purpose: embedding fonts inside the .pptx (PowerPoint's embedded format is an obfuscated, compressed EOT variant that python-pptx cannot write; a PDF export carries the fonts instead), and Fontsource's variable-font files (static weights are enough). Live check 2026-10-13: catalogue 2,100 families online, Inter and Noto Sans Bengali downloaded as woff2 and ttf; `reach_smoke.py` probes the catalogue and a file.

D-328 update (2026-10-13): `reach_smoke.py` now prints only the environment (2 lines), the count and one short line per failure; resources that need an optional key that is not set are left out of the report altogether; the full table is still written to `reach-report.md` and `.json`, and `--full` prints it. The .env parse warnings of python-dotenv are muted in this script.

### D-331 - Quick look at a large template (TODO P2.23, 2026-10-13)
`slides/look.py` + `scripts/dev/template_look.py`: because the user could not run the full probe on a very large company template, a light command writes one summary (about 30 lines: masters, layouts, sample slides, all twelve theme colours and the fonts of every master, fonts missing on this computer, what the samples hold), a palettes picture, contact sheets of one slide per layout (round-robin over the masters, at most 40, four columns by five rows) and of the template's own slides (at most 40, evenly thinned), and a zip. Tested on a generated two-master template with real PowerPoint renders. `make_contact_sheets` gained `per_sheet` and `prefix`.

### D-332 - What the real company template showed (TODO P2.23, 2026-10-14)
The user ran `template_look.py` on the real template (photographs of the summary, palettes and the deck in PowerPoint): 12.2 MB, slide size 10.00 x 5.62 in (not 13.33 x 7.5), 9 masters with 29 layouts, 76 sample slides (31 with pictures, 6 charts, 2 tables), fonts Calibri and Calibri Light as theme fonts. Findings and what was done:
1. **PowerPoint was reported as missing although installed.** The old check ran `reg query HKCR\PowerPoint.Application`; `preview.status()` now asks the registry directly (four places), then Windows' ProgID lookup, then looks for the program file, and says why; `reach_smoke.py` prints the result in its environment line. Until the user pulls this, no pictures can be made there.
2. **The nine masters are not nine palettes.** All carry the same theme ('TCS Theme Color 2024': accents 4E84C4, 54B948, FBB034, EF4135, F15A29, 595959). The variants are looks of the layouts: black cover with waves, blue gradient, white with a wave, black full-wave, dark and light twins of the same infographic. `template_look` now says how many rendered layouts are dark, mid or light and which; choosing a variant by mood (dark or light) is the item to build, not choosing a palette.
3. **Most samples are not placeholder layouts**: 59 of 76 sit on 'Title Only' with shapes drawn on them (triangles, process rings, five pillars, icon circles, timelines). Filling layout placeholders would miss most of the template; the sample-slide approach of P2.21 (copy the sample, replace its text slots) is the right one and must be tested on these.
4. **Instruction notes on the samples**: yellow sticky notes 'Delete before using ...' (replace the box with the customer logo, change the picture through Format Shape), and instructions in the slide notes. `template_samples.INSTRUCTION`/`remove_instructions`: such shapes (also inside groups) are never offered as slots and are removed from every copy; sample notes are never copied (the build already used only the new deck's notes).
5. Other features to keep when copying: logos in the corners, footer text such as '29 | TCS confidential', a 'Customer/partner logo' box, picture frames that expect 'Change picture', transitions or animations (stars in the slide sorter), layout names with typos ('Ttile Slide').
`forge template-probe` now tries at most 20 sample slides spread evenly (`--max-samples N`, 0 = all) because 76 samples built twice each is too much for a first run.

D-332 update (2026-10-14, the pictures from the real template): PowerPoint is now detected on the office laptop and the layout and sample contact sheets were made (17 of 29 layouts dark, 12 light; 38 of the 76 samples shown). What the pictures show: the layouts are a cover family (black with full waves, white with medium waves, blue gradient), thank-you closers, "Title Only" and "Title and Content" in dark and light, and layouts with a large circular picture frame. The content samples are mostly dark infographics with the title top left and the TCS and Tata logos in the corners: percentage circles, process rings, icon chains, KPI dials, donut and bar charts with captions, a comparison table, org-style trees, timelines, a five-pillar slide, quote and portrait slides. So (1) the deck's mood (dark or light) picks a variant, dark first; (2) most useful samples are infographic slides whose text boxes must be replaced one by one (items with number, heading, text), including charts and tables, which the probe skipped until now; (3) circular picture frames need the picture-into-frame step (P2.21 gap). `template_look` no longer leaves scratch folders in the output folder (OneDrive kept `_samples` and `_work` alive).

### D-333 - Chart and table samples, covers, separators, notes (TODO P2.23, 2026-10-14)
From the real probe (43 slides built, 0 failed): `slides/sample_objects.py` (`fill_chart` replaces the data of a sample's chart in place so its colours and look stay; `fill_table` grows or shrinks a sample's table by cloning its own last row and column and keeps its width), `Sample.chart_families` / `table_sizes`, and TemplateBuilder `chart_slide` / `table_slide` use the template's own chart sample of the same family (column, bar, line, pie, donut) and its table sample when the template has them (else the quiet native chart or table in the template theme; more than 12 rows also falls back). `template.name_is` recognises layout names with spelling mistakes ('Ttile Slide_Black ...' is a title slide); a short sample whose text says 'separator', 'section title' or 'divider' is a section; `instruction_shapes` removes the whole sticky note (text patterns such as 'Changing image: right-click ...', names like 'Sticky Note', and the tilted paper under the text; straight content under the note stays). Tested on an imitation of the real template (`tests/slide_templates.py::make_infographic_template`: 10 x 5.625 in, dark and light samples, misspelt cover layout, sticky note with tilted paper, donut and column chart samples, table sample, corner logo, footer) and checked in PowerPoint renders. Not yet done: choosing a dark or light variant by mood, text that is longer than the sample's box (shrink to fit), pictures into round frames.

### D-334, D-335 - Mood, fit and pictures in frames (TODO P2.23, 2026-10-14)
`slides/backgrounds.py` reads how dark a slide is from the file (its own background, else its layout's, else the master's: solid colour, the mean of a gradient's stops, the mean of a picture's pixels, theme colours through the master's colour map); `Sample.dark`; `Deck.mood` (auto, dark, light): the first sample used decides the side, later samples of the same kind prefer it, and a kind with no sample on that side falls back to any. `_set` makes text longer than the sample's smaller so it fits its box (down to 60 percent and at least 9 pt) and reports a text that still does not fit. `put_picture` fills circle-cropped pictures, shapes filled with a picture and empty picture placeholders, cropping the picture to cover the frame (the first version stretched it); `fills.picture` accepts a list for several frames. All tested on the imitation template; the real template's dark/light twins and photo frames are what the next probe should show.

### D-336 - The design of an uploaded deck, as a summary (TODO P2.24, 2026-10-14)
`slides/design_reader.py::read_design` and tool `describe_design`: from any .pptx without rendering it reads the slide size, the theme colours and fonts, how many slides are dark or light (from the backgrounds, D-334), where the titles sit (most common position and size), the text margins (the smallest start of the text on a fair share of the slides), the shapes that repeat on at least half the slides in the same place (logo, bars, footer lines, with their share), the layouts, the fonts and sizes the text really uses, the fill colours most used, and a brand kit for the outline (theme accent, a background on the deck's usual side, the text colour that reads on it, the fonts). The tool also says what to do next: a 16:9 deck is built on as a template (its sample slides are copied and filled), anything else uses the brand kit with the same title position and frame shapes in freeform slides. `Design.as_dict()` is the format the image reader (P2.25) produces too. Tested on the imitation template and a deck DebCraft built.

### D-337 - A design shown as a picture, measured (TODO P2.25, 2026-10-14)
`slides/image_reader.py`, tools `analyze_reference_image` and `compare_to_reference`: from a screenshot or photo of a slide, the dominant colours with their shares (median-cut quantisation), the background (the colour of the picture's rim, matched to the palette), dark or light, the text colour, the accents (colourful palette entries), content regions (a 16 x 9 grid of edge density and distance from the background, connected into regions, in percent and in inches on a 13.33 x 7.5 slide), marks in the corners (logos), and a brand kit; fonts and photographs are stated as not readable. `compare_to_reference` scores a rendered slide against the reference (8 x 5 grid of mean colours, CIE76, score 100 = same; palette match) and names the worst cells, for up to three fix rounds with `preview_presentation`. First version, offline: tested on drawn dark and light slides. Not done (needs the user's reference pictures): the live loop on real examples and a benchmark of five references with a target score; the photo-of-a-screen case (a screen's frame and glare around the slide) is only roughly handled (the rim colour is the frame): crop first.

### D-338 - Decks from documents (TODO P2.19, 2026-10-14)
`slides/sources.py` + tool `read_source_document` (`tools/presentation_sources.py`): Word (python-docx: headings with their text, bullets, tables, picture count), Excel and CSV (openpyxl read-only with cached values, csv with delimiter sniffing and a byte-order mark: header, rows, sample, min/max/total/last of numeric columns, chart-ready series with the cell range, at most 200,000 rows and 12 sheets), PDF (pypdf: text per page, encrypted files and scans reported with what to do). Every fact carries its place, so slide notes can cite it. The libraries are the optional `docs` extra (installed on the build machine with the user's earlier permission; a missing one gives an install message). A section in the make-presentation skill turns a digest into a deck: story first, only numbers the digest holds, charts from the series, sources in the notes. Not done: Word comments and tracked changes, text boxes and headers of Word files, table detection in PDFs, merged cells in Excel, formulas (cached values are read).

### D-339 - Excel workbooks (TODO W0 + W2, 2026-10-14)
Context: the user's work needs spreadsheets as well as decks. Options for placement: (a) inside `slides/` (wrong name, mixes concerns), (b) a new tier-5 package `sheets/` beside `slides/` (chosen), (c) a generic `documents/` package for Excel, Word and PDF together (rejected for now: Word and PDF have different needs; can be added beside it).
Built: `sheets/{spec,build,read,edit,check,excel}.py`, tools `build_workbook`, `read_workbook`, `edit_workbook`, `check_workbook` (`tools/workbook.py`), skill `make-spreadsheet`. Outline (JSON or YAML) gives real formulas ("=..." cells), column formats and widths, Excel table, frozen header, total row (SUM/AVERAGE formulas), named ranges, data validation (`choices`, `whole`, `decimal`), conditional formatting, cell notes, native charts. `check.py` works everywhere (openpyxl tokenizer): error values, missing sheets, circular references, text in number cells, numbers typed inside formulas (hint). `excel.py` has Excel calculate the file through COM (macros force-disabled, env-var paths, no DebCraft variables) and lists the cells showing errors; `check_workbook recalculate=true` also stores the calculated values into the file when there are no errors (a library-made file has no stored values). Verified live against Excel on the build machine.
Editing keeps formulas, but openpyxl drops charts, pictures and macros on save: `edit_workbook` refuses such a workbook unless `allow_loss` is set, naming what is lost. Result is always .xlsx. Clean-room rules in `docs/DOCUMENTS_CLEAN_ROOM.md` (W0): only specifications, library documentation and our own tests are used; no other vendor's skill files.
Limits: no pivot tables, no sparkline, no formula spill checking beyond Excel's own report; renaming a sheet does not rewrite formulas in other sheets (the tool says so). Unverified: the check on very large workbooks (cycle search expands ranges up to 2000 cells).

### D-340 - Faster tools, part 1 (TODO S6, 2026-10-14)
Commands the model runs get `npm_config_prefer_offline=true`, `npm_config_audit=false`, `npm_config_fund=false` (set only if not already set). Packages npm already has come from its cache; new ones still come from the network, so nothing is skipped. `view_image` already downscales to 2048 px; the 17 s seen was the vision model's answer time, and a smaller picture would cost accuracy (D-161), so it is left alone. Not done: auditing only changed pages (needs a record of which pages changed between screenshots).

### D-341 - Run report download button (TODO C17, 2026-10-14)
`GET /api/run-report.md` writes the scrubbed run report (D-259) for the open project and sends it as a download; the Files panel has a "Run report" button beside "Download output". A project that has not run yet gets a short report instead of an error. Nothing new is scrubbed or exposed: the same builder as `forge run-report`. D6 (visual regression) was already built as `visual_baseline` / `visual_check` (D-312).

### D-342 - Word documents (TODO W1, 2026-10-14)
New tier-5 package `documents/` beside `sheets/` and `slides/` (same reasons as D-339). `documents/{spec,build,read,edit,check}.py`, tools `build_document`, `read_document`, `edit_document`, `check_document` (`tools/document.py`), skill `make-document`. Outline blocks: heading, paragraph (runs with bold, italic, https/http/mailto links), bullets, numbered, table (repeating header row, caption), image (alt text required by the outline), quote, page break; table of contents and page number as Word fields; title, author, language; optional company template (styles, header, footer kept, sample body removed). Read gives Markdown, comments, tracked-change counts, pictures without alt text. Edit: replace text across runs (also tables, headers, footers), set/delete/append paragraph, add comment (python-docx 1.2). Check: title, language, alt text, heading order, empty headings, bold-faked headings, empty-paragraph spacing, tables without header row. Verified: a built file opens in Word and its fields update (COM, build machine).
Not done: Word preview pictures (like the PowerPoint export), LibreOffice path, footnotes, accepting/rejecting tracked changes, package validation shared with P1.8 (W4).

### D-343 - PDF toolkit (TODO W3, 2026-10-14)
New tier-5 package `pdfs/` (reasons as D-339). `pdfs/{read,edit,build}.py`, tools `read_pdf`, `edit_pdf`, `split_pdf`, `extract_pdf_images`, `build_pdf` (`tools/pdf_toolkit.py`), skill `pdf-toolkit`. Read: reading-layout text per page (pypdf layout mode), title, author, form fields with values, picture count, warnings for scans, JavaScript/open actions and embedded files (never run or opened). Edit (new bytes, original untouched): merge, rotate, crop, delete/extract pages, diagonal watermark and page-number stamps (reportlab overlay, merged page by page), fill form fields (unknown field names are reported with the real ones), metadata, encrypt, decrypt. Create: reportlab platypus from an outline (headings, paragraphs with one https/http/mailto link, lists, tables with repeating header, pictures, footer, page numbers, title and language). Scans: existing `pdf_render` + `ocr_image` (skill says so). Chosen: pypdf (BSD) and reportlab (BSD); no HTML-to-PDF library (licence and engine weight not checked, so none is used). 
Password handling: an encrypt/decrypt password is a tool argument, so it appears in the transcript; the skill limits it to passwords the user gave for their own file. Not done: true redaction (the skill forbids claiming it), non-Latin fonts in built PDFs, table extraction beyond the layout text, OCR as one step for a whole PDF.

### D-344 - Word extras (TODO W1, 2026-10-14)
Footnotes (`documents/footnotes.py`): python-docx has none, so the footnotes part is created on first use with the two separator entries; outline run field `footnote`, edit operation `add_footnote`; `read_document` lists them. Verified: Word counts and reads the footnote. Tracked changes (`documents/changes.py`): `accept_changes` and `reject_changes` settle every insertion and deletion in the body, tables, headers and footers (a formatting change keeps its new formatting either way, and the tool says so). Preview (`documents/preview.py`, tool `preview_document`): Word exports the document to PDF through COM (macros disabled, fields updated, paths in environment variables), LibreOffice `soffice --headless` when Word is missing, then the existing PDF renderer makes page pictures; `pdf_output` also saves the PDF. LibreOffice path is untested here (not installed). Still open: package validation shared with P1.8 (W4), comments on a text range (comments attach to a paragraph), tracked-change authoring.

### D-345 - Shared document engine, first part (TODO W4, 2026-10-14)
Context: Word, Excel, PDF and PowerPoint tools each had, or were about to get, their own file checks, preview and review. Options: (a) leave each format on its own (duplication, uneven safety), (b) one shared layer (chosen), (c) refactor the older presentation code onto it now (rejected for tonight: risk to a working, heavily tested path; the old `slides/validate.py` and `slides/rawpackage.py` stay and can be moved over later).
Built: tier-1 package `ooxml/` (standard library only). `check.py`: the safety check run on every Word and Excel file before python-docx or openpyxl reads it: entry count, total size, expansion ratio, unsafe names (`..`, absolute, device names), encrypted entries, DOCTYPE/entity XML are refused; macros, program files, external links, embedded objects and ActiveX are reported in the read tools' output and never run, followed or opened. `validate.py`: structure validator for a finished file (content types and overrides, relationship targets, duplicate ids and parts, well-formed XML, the main part and, for Word, picture/link relationships and section properties; for Excel, sheet names and sheet parts); `build_document` and `build_workbook` now append its findings. Tools (`tools/document_preview.py`): `preview_file` (Word, Excel, PowerPoint, PDF to page pictures plus one contact sheet; Excel prints through COM with macros disabled, `sheets/excel.py::to_pdf`; saves the PDF on request) replaces the Word-only `preview_document`; `critique_document` sends the contact sheet to the vision model with a fixed rubric (hierarchy, consistency, readability, tables and charts, completeness) and returns scores, issues with page and fix, and a ship/fix_first verdict. Verified: Excel printing and PDF previews in tests on the build machine; the critic's model call is not covered by an automated test (no FakeLLM, D-008) and needs a live run.
Not done: document themes and brand kits shared with presentations (P2.1), catalogue entries for document templates under the asset standard (L0), the PowerPoint validator moved onto `ooxml`, the critic's calibration against human scores (W5).

### D-346 - Real sample files instead of asking the user (2026-10-14)
The user asked for samples to be found rather than supplied. Claude's training data is not accessible, so that source is not available; instead six real files were downloaded from public-domain or permissively licensed sources and kept in `tests/samples/real/` with their source and licence in `SOURCES.md`: IRS Forms 1040 and W-9 (fillable PDFs with JavaScript), a W3C tagged-table PDF, a Census workbook (title lines, two-row header over merged cells, footnotes), python-docx's comments sample and python-pptx's test deck (MIT). `tests/test_real_samples.py` runs the readers and package checks over them. Findings and fixes: (1) pypdf printed long font warnings to the terminal: its logger is now set to errors only; (2) the Excel digest took the sheet's title line as the header and the years row as data (wrong columns and min/max): `slides/sources.py` now skips title lines, joins a two-row header (group heading carried across merged cells, years under it), moves footnotes and titles to `notes`, and reports the true cell ranges from the original row numbers. Checked by hand on the real files: filling a 229-field form, watermark, page numbers and encryption on the IRS forms all work. Not covered: reference pictures for P2.25 (photographs of other designs) and messy Word files from real offices; deck screenshots we render ourselves test only the machinery. Those still need the user's own examples, but a few are enough.

### D-347 - Shared document engine, open points of W4 (2026-10-14)
1. **Critic checked live** (`tests/test_live_document_critic.py`, real Azure model): a tidy report and a crowded, mixed-font, low-contrast one; the critic scored the tidy one higher in total, gave the bad one `fix_first` and listed issues. This is a sanity check, not a calibration against human scores (still W5).
2. **Brand kit shared by documents** (new tier-1 package `brand/`): same field names as the deck brand kit (accent, background, text, muted, surface, accent_text, title_font, body_font), so one JSON file serves all formats. Word: heading and title styles, body font and text colour, table header shading with readable text; Excel: header fill and text, cell font; PDF: heading and table-header colours, fonts mapped to Helvetica/Times/Courier. Colours that fail 4.5:1 on white are darkened; text on the accent is white or near-black by contrast. `brand_file` argument on `build_document`, `build_workbook`, `build_pdf` and `build_presentation` (same file). The deck's own `BrandKit` (D-281) keeps its copy of the model.
3. **PowerPoint validator on `ooxml`**: `slides/validate.py` now uses the shared content-type, relationship and XML-part checks, and `slides/rawpackage.py` delegates the archive and XML safety to `ooxml.check` (one set of limits for every format; the deck messages still say ".pptx package"). One behaviour added for decks: an Override naming a part that is not in the file is now reported.
4. **Template catalogue entries** under the asset standard: three Word templates (`tpl-doc-report-clean`, `tpl-doc-memo`, `tpl-doc-proposal`, with page pictures made by Word) and starting outlines (`rcp-xl-budget`, `rcp-xl-tracker`, `rcp-pdf-handout`) as assets of `make-document`, `make-spreadsheet` and `pdf-toolkit`, found with `find_asset` and copied with `add_asset` (`.docx/.xlsx/.pptx` are now copied as binary). All authored for DebCraft (licence: original); `scripts/dev/make_document_templates.py` remakes them. The budget outline was checked in Excel (no error cells) and had its typed-in number moved to a named assumption after the check's own hint.
Not done: presentation-style themes (the deck theme list) for documents; the critic's calibration against human scores (W5).

### D-348 - DESIGN.md as the design-system format: parse, lint, diff, export (TODO DS1, 2026-10-15)
Context: the research of 2026-10-14 (11 sources) showed DESIGN.md (Google Labs, Apache-2.0, alpha) is the format all the catalogues and tools now share. Options: (a) keep our free-text template, (b) adopt the format and call its Node CLI, (c) adopt the format and implement it in Python (chosen: no Node or network on the target laptop; the specification is public, no code was copied).
Built: package `designsystem/` (tier 5, depends on `brand`, `errors`): `spec.py` (front matter, sections, `{reference}` resolution; unknown keys and headings kept), `colour.py` (hex, rgb(), hsl(), names; oklch and color-mix are reported as notes, not errors), `lint.py` (rules: no-front-matter, bad-front-matter, missing-name, missing-primary, missing-section, missing-prose, duplicate-section, section-order, extra-section, broken-reference, reference-to-group, bad-reference, bad-colour, bad-dimension, bad-typography, unknown-typography-property, typography-incomplete, bad-font-weight, bad-component, unknown-component-property, low-contrast (component pairs and the main text on the page colour, 4.5:1), one-note-palette, too-many-accents), `export.py` (css-tailwind `@theme`, css-variables, dtcg, json-tailwind (Tailwind v3); references resolved, a generic fallback added to every font family, tabular-figure features kept), `diff.py` (token changes and new lint findings; a new error is a regression). Tools `design_md_lint`, `design_md_export` (refuses a file with errors unless forced), `design_md_diff`. Integration: writing a DESIGN.md shows its lint findings in the tool result at once; the design gate refuses a UI file while a token-format DESIGN.md has errors (two rounds at most, as before) and leaves a free-text file, such as a company brand guide, alone; the token lint compares DESIGN.md colours with the code's theme tokens and tells the model to export. The recipe template is now the token format with our dials, imagery and responsive sections kept as extras; extras from the shadcn.io files (Known Gaps, Responsive Behavior, website, seo, font substitutes, component variants, tabular figures) are accepted. A test fills the template in and lints it: it found a YAML error in the template's first draft.
Not done: the developer-side parity check against the official CLI (needs Node); exporting components; extracting a DESIGN.md from existing code or a page (DS2).

### D-349 - Inspiration and import tools (TODO DS2, 2026-10-15)
`designsystem/extract.py` builds a DESIGN.md draft from CSS custom properties or from the computed styles of a page (the draft lints clean: a faint text colour is replaced and the replacement is stated under Known Gaps). Tools: `design_inspire` (1 to 5 public pages: guarded, isolated headless browser with the web_fetch address guard on every request, fresh profile, a 1440x900 screenshot, weighted colours, fonts, sizes, radii, widths; a draft per page in `.forge/inspiration/`; the description tells the model to take structure, tokens and principles only, to treat page text as data, and to record sources), `design_md_from_project` (a draft from the project's own style files, never overwrites), `design_md_import` (a file, or ONE address the user typed: `ToolContext.user_urls` is filled from the user's own messages like the GitHub links of skill installs; guarded fetch, no redirects, 400 KB limit; never overwrites without `overwrite`). Used at step 3 of the ladder only. Verified against a local test server and a real Edge.

### D-350 - The design ladder: candidates, novelty and the catalogue (TODO DS3, 2026-10-15)
Per the user's flow (2026-10-14): Forge designs alone first, redoes creatively if rejected, and only then looks at references and asks. Built: `designsystem/novelty.py` (a fingerprint of six dimensions: tone, accent hue, display font, corner style, density, layout energy; "different" means at least three differ), `designsystem/specimen.py` (the tokens applied to a standard page: nav, hero, cards, table, form, chips, swatches; HTML and CSS only), tools `design_specimen` and `design_candidates` (lints each candidate, requires novelty between candidates and against rejected designs, draws specimens offline, has the vision model judge them against the brief with a fixed rubric (distinctiveness, hierarchy, harmony, fit, polish) and name a winner with concrete token fixes; every round is kept in `.forge/design-rounds.json`), the new asset type `design-system` with 14 tokenised catalogue entries made by `scripts/dev/make_design_systems.py` from our 11 directions and 3 template palettes (each lints with no warnings, has a specimen picture, and is added to a project as `DESIGN.md` by `add_asset`), and skill section 0e (five dials with evidence, vague-word firewall, fit before variety, autonomous choice with the options recorded, the ladder). Checked live: the real critic chose the playful system over a dark dashboard and a minimal monochrome one for a children's museum. Deviation from the plan: a candidate is judged on a token specimen, not on a built hero section for each (three model builds per round are slow); the winner's real hero is built next and is judged by the normal critic loop. Not done: the CC0 prompts of superdesign-prompts (needs a licence re-check of their LICENSE-DATA and a conversion), DS4, DS5.

### D-351 - Rules in the audit: banned looks and interaction states (TODO DS4, 2026-10-15)
`ui_audit.py` (computed styles, so a Tailwind class or a CSS rule is judged by what it renders): a purple-blue, pink-cyan or rainbow gradient (stops read from the computed background image: saturated stops whose hues fall in those pairs, or four hue families), an empty grey box of 80px or more standing in for an image, four or more saturated colour families each covering over 1.2 percent of the screen (one accent and one signal colour; adapted from the OJO-Design-Skills rule on accent area, in our own words and measure), no `:hover` rule and no `:focus-visible` rule in the page's stylesheets when it has two or more controls, disabled controls without a `:disabled` style, and three or more blocks of running text under 13px at desktop width. Source checks: a form with no error state or no sending state (the 8-state model: default, hover, active, focus-visible, disabled, loading, success, error), and a purple-to-blue Tailwind gradient. The skill (section 0f) lists what is rejected and which check answers which question (audit, critic, token lint, visual check, candidates), the picker idea of better-web-ui in our own words. Limits: cross-origin stylesheets cannot be read (the hover and focus checks stay silent then), and the states success, loading and error are only checked in source for forms.

### D-352 - The design benchmark and what it forced (TODO DS5, 2026-10-15)
Built `scripts/benchmark/run_design_benchmark.py` and two briefs (`tests/benchmarks/design`), results in `docs/DESIGN_BENCHMARK.md`. Three runs on the real model showed that skills and tools alone change nothing for this model, so the design studio now has gates and checks: (1) a DESIGN.md the model wrote itself must be compared with candidates once before the first page (`files.py`, `CANDIDATES_NOTE`; a user-supplied file is never questioned); (2) a front matter with none of colors, typography, rounded or spacing is a lint error (`no-tokens`), so another key vocabulary cannot pass; (3) `design_candidates` refuses candidates that are not different enough (twice, then judges as they are), and the fingerprint finds the display font by name or by size; (4) typography: `system-font` lint warning, the audit reports a page whose text is all in the system font stack as a BLOCKER that stops `task_update` done (a brand guide saying "system fonts are required" lifts it), specimens embed the bundled fonts (`designsystem/fonts.py`) and the tool says when a candidate's font is not bundled, the skill has section 0g (typography by product, mood and script; how to get fonts offline with find_asset, find_font and fetch_font); (5) strict anchored rubrics with a typography score for the candidate judge, the design critic and the benchmark judge (5 is award-winning, 3 template-like, 2 the machine-made look); (6) a concept and a signature move for every candidate (skill 0e); (7) an audit finding for a page with no imagery (the template scaffolds, which hold placeholders, are allowed that one finding in their tests). Not done: composition recipes for plain HTML, real imagery by default, a stronger design-role model, and a fourth benchmark run after these last changes (each run costs about $3 and 45 minutes).

### D-353 - Model options script and the finding for DS8 (2026-10-15)
`scripts/dev/model_options.py` asks each provider what the keys can reach (Azure: lists the resource's deployments when it allows it, then sends a one-token text request and a one-picture request to the configured, listed, extra (`--azure-names`) and common names; Gemini: the API-key model list, and Vertex AI when Google credentials exist) and prints deployment and model names, speeds and picture support, never a key. Run here against the Azure resource in `.env`: the deployments are `aicloud-gpt-4o` = model gpt-5.1 (the configured primary), `aicloud-gpt-4` = gpt-4.1, `gpt-35-t-healthcare-decision-mtx` = gpt-4.1-mini, plus embedding and image deployments that do not answer chat. So the builder is already the strongest Azure model on this resource; a stronger design role has to come from Gemini on the office laptop (the provider exists, D-150) or from process and assets. Not done: a `designer` role in the config (needs the user's option list first).

### D-354 - Compositions, imagery and the concept check (TODO DS7, 2026-10-15)
After the benchmark and the user's feedback (pages look machine-made, fonts do not suit) the layout was the next gap: every page was a centred column. Built: seven complete plain-HTML compositions in `skills/ui-design-quality/recipes/compositions/` (poster hero, vertical type sign, editorial split, ticket stubs, lab notebook, full-bleed colour bands, menu with leaders), each with a drawn SVG motif so the page has imagery that belongs to it, responsive with no build step, CSS variables named like the DESIGN.md export, found with `find_asset` type `section` (ids `lay-*`) with a desktop and a phone reference picture each. They were rendered in Edge at 1280 and 375 px and looked at; the style audit found real faults in the first drafts (contrast, 11px labels, a missing h1, art overlapping the action, sideways scroll on a phone), all fixed, and `tests/test_compositions.py` keeps them clean. `composition: lay-...` in a DESIGN.md front matter is now the seventh dimension of the novelty fingerprint (candidates should differ in layout, not only colour; a file that names none says nothing either way); five catalogue systems name a pairing; the candidates gate note and the template ask for it. Skill section 0h (compose, do not stack cards: a composition per candidate, a hero picture that belongs to the product, one broken-stack move, rhythm, craft details). The design critic now checks the page against the DESIGN.md Concept and signature move and the hero's imagery, and a centred column of cards with a new colour is a BLOCKING miss. Not done: a fourth benchmark run (needs the model decision of DS8 first), compositions for React projects beyond the template sections, more than seven recipes.

### D-355 - Messy tables and whole-PDF OCR (TODO W2 and W3 leftovers, 2026-10-15)
`sheets/clean.py` and tool `clean_table`: a messy CSV, TSV or sheet becomes a clean workbook. Handled: title lines above the header, a header over two rows (merged-cell groups carried across), blank rows and columns, duplicate column names, stray and non-breaking spaces, empty words (N/A, null, -, TBD), numbers as text (thousand separators, parentheses as negative, percent, a currency symbol that sets the format), dates (ISO, numeric day/month/year with the order decided from the whole column, text months) with a stated GUESS when nothing in the column settles day versus month, duplicate rows, total lines kept and flagged. Everything is reported, nothing is changed silently; the original is never touched. `build_workbook` now turns ISO text in a date-formatted column into real dates. `ocr_pdf` (`tools/vision.py`, offered only with Tesseract like `ocr_image`): a whole scanned PDF to a text file in one step, text layer used where it exists, OCR elsewhere, 200 pages at most. Not done: modelling-convention checks for workbooks (colour-coded inputs), redaction, non-Latin fonts in built PDFs.

### D-356 - Colour-coded inputs in workbooks (TODO W2 leftover, 2026-10-15)
`sheets/inputs.py`: the numeric constants that formulas read, directly or through a named range, are found; `build_workbook` styles them blue (`mark_inputs`, default on; the font name and size are kept) and `check_workbook` gives a hint for any that are not, in a workbook made elsewhere. The modelling convention (inputs blue, calculations black) lets a reader see what may be changed. Not done: a separate fill for outputs, a units column check, a check that every input has a label.

### D-357 - Document benchmark (TODO W5, 2026-10-15)
`scripts/benchmark/run_document_benchmark.py` and three tasks (`tests/benchmarks/documents`): a one-page Word sales summary from a CSV, a messy export turned into a workbook with a total made of formulas and a chart, a PDF handout from notes. Scored by deterministic checks (package validity, the figures and phrases that must be present, no invented figure, formulas instead of typed totals, a chart, duplicates and title lines removed, page count, title set) and by a blind vision judgement of the printed pages (Word, Excel or the PDF itself; strict anchored rubric). `tests/test_document_benchmark_checks.py` proves the checks pass on outputs made by DebCraft's own tools and fail on an empty workspace, so a benchmark failure means the model's work, not the checks. Results go in `docs/DOCUMENT_BENCHMARK.md`.

### D-358 - Gemini probe across regions (2026-10-15)
The user's run of `model_options.py` on the office laptop showed Vertex AI answering in us-central1 for gemini-2.5-pro, 2.5-flash and 2.5-flash-lite (text and pictures) and 'not available' for gemini-2.0-flash and both Gemini 3 preview names; the image-generation model the user can use was not in that list because the script only tried text models in one region. `scripts/dev/gemini_probe.py` tries a standard list of regions (`global`, where Gemini 3 is served, and the usual regional ones, plus GOOGLE_CLOUD_LOCATION), asks each region what it lists, and sends a text request, a picture request and (for image models) an image-generation request to every candidate: Gemini 3 and 3.1 pro and flash previews, Gemini image models (2.5 flash image, 3 pro image preview) and Imagen 3 and 4. It prints a table and which region to put in GOOGLE_CLOUD_LOCATION. No key or token is printed. Not done: a `designer` role in the config (waits for the result), and testing it here (no Google credentials on the build machine).

### D-359 - gpt-5.4 and gpt-5.2 on the second Azure resource (TODO DS8, 2026-10-15)
The user said gpt-5.2 and gpt-5.4 are deployed too. They are not on the primary resource (`ai-openai-pg`: gpt-5.1, gpt-4.1, gpt-4.1-mini) but on the second one (`ai-openai-engg`, the AZURE_FALLBACK_* resource): `aicloud-gpt-5.2` (gpt-5.2), `aicloud-gpt-5.4` (gpt-5.4) and `aicloud-gpt-5.2-chat`, each answering with text and pictures in about one to two seconds; the fallback role there points at gpt-4o. `scripts/dev/model_options.py` now also probes the fallback resource. `defaults/config.yaml` gets an optional model `gpt54` (deployment name from the new `AZURE_STRONG_DEPLOYMENT`, the fallback resource's endpoint, key and API version, vision on, reasoning medium, placeholder prices) that no role uses until the user's `config.yaml` says so, for example `llm: {roles: {coder: gpt54, vision: gpt54, judge: gpt54}}`; checked live through DebCraft's own provider. Both benchmark runners take `--all-roles gpt54` (every role names that model in the run's own config; the judge of the benchmark stays on the default model so the comparison is fair) plus `--env AZURE_STRONG_DEPLOYMENT=aicloud-gpt-5.4`. Not done: a measured comparison (design-7 follows design-6), the real tenant prices and context window of gpt-5.4, a default role change.

### D-360 - Speed changes modelled on Claude Code (user request 2026-10-15)
The dashboard brief took 45 minutes (84 model calls of about 27 s, 93 tool calls, three critic and verifier reviews of 264 s, two stalled calls that lost about 375 s); caching was fine (95 percent). Claude Code is faster mainly because it makes few, large steps and does not wait on a slow call. Changes, all quality-neutral (D-161): (1) the system prompts (normal and Mode B) ask for batching: independent calls in the SAME step (reads, searches, writing HTML and CSS together, starting the server while writing tests), bookkeeping calls in the same step as real work, one write_file per new file and one multi_edit per change, a dev server started once, no re-reading of a file already read; parallel tool calls were already enabled and the loop already runs read-only calls, critics and a verifier side by side, but the model never asked for it; (2) one design-critic round is the default: a REVISE with no fix line starting with BLOCKING counts as cleared (the builder applies the cheap suggestions in its next step and reports the rest), a BLOCKING fix still gets follow-up rounds up to the limit of three; `has_blocking_fix` reads the fix lines, not the word in a sentence; (3) a stream idle limit (`providers.azure.stream_idle_s`, default 100 s) replaces the 180 s wait for a streamed answer that has gone quiet; the retry layer already handles the timeout; (4) the critic and verifier note says to start them together; skills tell the model to keep servers running and verify in few steps. Measured by `docs/SPEED_BENCHMARK.md` (dashboard brief, before and after, side by side on the same machine).

Measured (docs/SPEED_BENCHMARK.md, speed-5): 22 percent fewer model calls, 32 percent fewer input tokens, 7 percent cheaper, wall time -3 percent on the dashboard brief; the 45 minutes seen before was mostly caused by other jobs running at the same time. Next lever: less to write per call (recipes and tokens as the starting point).

### D-361 - Live model progress on the activity line (user request 2026-10-14)
Context: on the office laptop a model call that writes a whole file as tool arguments or reasons for a long time showed only "thinking" and a timer, so the user could not tell stuck from working.
Options: (1) show the model's raw reasoning, (2) show stage, size and last reasoning summary line from the stream events already received, (3) only a "still working" heartbeat. Chose 2: honest, no extra model calls, no new data leaves the engine (redaction still applies to events).
Built: `StreamProgress` (llm/base.py, one event per second at most) fed by the Responses stream (reasoning, preparing a named tool with characters so far, writing the reply); `EventType.MODEL_PROGRESS`; the Activity line shows "Preparing: write file - 4,200 characters so far", the latest reasoning line, and "no new data for Ns (after 100 s it retries)" once quiet for 15 s.
Limits: subagent chats, vision and judge calls (not streamed) and the Gemini provider show no progress yet; the Activity line only shows it for the main model call.

### D-362 - Independent designs are built side by side (user request 2026-10-14)
Context: asked for 3 throwaway designs, DebCraft built them one after another. Parallel builders already exist (X2, D-305: own folder each, at most `limits.max_parallel_builders` = 3, ledger, statuses), the same way Claude Code starts several sub-agents in one turn. The prompt only said such pieces "can" be built together and the design skill's variants section described a serial flow, so the model chose serial.
Decision: no new machinery; the system prompts (both modes) now say independent pieces are built at the same time, and ui-design-quality section 6 tells the model to write the briefs and start one builder per variant in one turn. Folder, DESIGN.md and port per builder keep them apart; the write jail is unchanged.
Not measured: wall time of 3 designs serial vs parallel (to do with the design benchmark on a quiet machine).

### D-363 - Node tools trust the Windows certificate store (office laptop, 2026-10-14)
Context: on the office laptop `npx shadcn@latest init/add` failed with "unable to get local issuer certificate" (company HTTPS inspection; Python already used the Windows store through truststore, D-110, Node did not). npm itself worked.
Options: (1) set `NODE_USE_SYSTEM_CA=1` for commands DebCraft runs (Node 22.15, 23.8, 24 and later read the OS store; older Node ignores the variable), (2) pass `--use-system-ca` in NODE_OPTIONS (an unknown option makes old Node refuse to start), (3) require the user to export the root certificate (NODE_EXTRA_CA_CERTS), (4) switch certificate checking off (rejected: removes the protection). Chose 1, with 3 as the documented fallback and `forge doctor` saying which applies.
Built: `ShellSession.environment()` sets `NODE_USE_SYSTEM_CA=1` unless FORGE_SYSTEM_CERTS=0; `forge.net` gets `node_supports_system_ca`, `installed_node_version`; doctor line "Node certificates" (warns for an old Node). Not verified on the office laptop: the user still has to run the shadcn check there (TODO section 1); whether the low-integrity sandbox can read the certificate store is also untested.

### D-364 - Live progress for helpers too (follow-up of D-361)
A builder, verifier or critic writing a big file looked silent: the Activity line showed only its step counts. Helpers now pass the same `StreamProgress` through their private loop (`_tracked_run`), the session receives it as `subagent_step` of kind `model_progress`, the agent view keeps the newest one (cleared at its next step) and the Activity line shows "<helper> is working - N calls - Preparing: write file: 4,200 characters so far" with the same quiet warning. Parallel builders each keep their own state by agent id. Still without progress: calls that are not streamed (vision, judges, the summariser) and the Gemini provider.

### D-365 - S5 follow-up: stop writing things that get thrown away (2026-10-14)
Evidence: per-call output tokens from the event logs (docs/SPEED_BENCHMARK.md, speed-6). Two causes of wasted generation: (1) whole pages written before DESIGN.md and the candidates existed were refused by the gates, twice, then written a third time (about 16,700 tokens); (2) `task_update` refusals named one missing check each, costing a call per check.
Decision: state the order (DESIGN.md, candidates, page) in both system prompts and at the top of the skill; every `task_update` refusal now lists all other missing checks. Rejected: lowering reasoning effort or dropping the ladder (quality, D-161); stashing refused pages (they would be built before the tokens exist).
Measured: the early refusals did not recur in one run; wall time is not comparable between single runs (1188 s and 2658 s on the same brief, different route). Three runs per arm stay on TODO X8.

### D-366 - Application screen recipes (user request 2026-10-14)
Context: asked for "multiple dashboards, tables, forms or settings screens, data entry screens, web application screens". The catalogue had seven marketing-page layouts and nothing for applications; every app screen was written from nothing (the largest share of output tokens in speed-6) and looked generic.
Options: (1) more prose guidance, (2) screens as React components with a build step, (3) standalone plain HTML and CSS screens like the compositions, built by a generator from one shared kit. Chose 3: no build step, each file opens and is audited as is, one place to fix the shared stylesheet, and the model copies instead of writing.
Built: 24 screens in five families (docs/APP_SCREENS.md), five palettes and bundled fonts, an original icon sprite and chart builders, catalogue entries with pictures, skill section 0i, a line in both system prompts, candidates notes that accept `composition: app-...`. Tests: audit and sideways scroll for every screen at both widths, retrieval 24 of 24, copy into a project, prompt wording.
Audit: charts count as imagery; application-like pages are not asked for pictures or a landing headline (the screens exposed both false positives).
Not done: React versions; a live run measuring the saved output tokens.

### D-367 - Progress for model calls made by tools, and for Gemini (tonight's list, item 6)
Context: D-361 and D-364 showed stage, size and quiet time for streamed calls of the main model and of helpers. Model calls made inside a tool (a picture question, the candidate comparison, the document review) and the Gemini provider still showed nothing.
Built: `ToolContext.ask_model(role, request, what)` wraps the router call and emits a `tool_progress` heartbeat every 4 s ("asking the vision model: looking at the picture (12 s)") that the activity line already shows; used by view_image, design_candidates and critique_document. The Gemini provider passes the same `StreamProgress` (waiting, thinking with the reasoning summary, writing, preparing a named tool with the size of its arguments). Tests offline (fake router, SDK chunk types); the Gemini path has not been run live from the build machine.
Not done: the summariser and the eval judge still call the router directly (no tool is on screen for them).

### D-368 - Tools are not the bottleneck; the verifier does not script a static page (tonight's list, item 7)
Measured from the event logs of the dashboard runs (speed-6, speed-new): `browser_screenshot` 2.2 s each (22 s in a 2,658 s run, audit included), `run_command` 1.4 s, `start_background` 2.2 s; `spawn_subagent` 904 s, 34 % of the wall time. So "audit only changed pages" and the sandbox start-up measure (S6) are not worth building: closed as measured.
The 515 s subagent was the verifier on a static page: it installed Playwright (99 s) and wrote a 265-line acceptance script twice for a page with nothing to click or submit. Prompt change: the script is for behaviour (forms, scripts, state, an API, several routes); a static page is checked with the browser tools (console, network, screenshots, DOM). The checks themselves are unchanged. Not measured live yet (X8 and AS1 runs are using the code before this change; a later run will show it).

### D-369 - Audit findings that carry the patch (tonight's list, item 8, L9)
The audit named the nearest passing colour for contrast (D-263) but only counted overflow and missing alt text, so the model searched for them. Now the overflow finding names the outermost elements that stick out (not inside a scrolling frame) with their likely cause (fixed width, nowrap, media wider than its box, min-width) and the missing-alt finding names the image files and says what alt text should be (what the picture shows; empty only when decorative). Chosen over an automatic source rewriter: alt text and layout fixes need the model's judgement and the source can be JSX, HTML or a template; the finding now gives it the target and the cause. Test: tests/test_ui_audit_studio.py.

### D-370 - D1 and D2 (tonight's list, item 9)
D1: a UI file (not a test) changed six times in one run gets a note on that tool result, and again every four changes: stop patching one value at a time, read the whole file, list what is still wrong, name the cause and fix it in one `multi_edit` or write the file once. It is a note, not a refusal: a long legitimate session on one stylesheet is possible, and the note costs nothing when it is not needed. Counts live in `ToolContext.edit_counts`; test in tests/test_agent_loop.py.
D2: cost and time per UI task are measured by the benchmark runs (docs/SPEED_BENCHMARK.md: dashboard brief $1.88 and 1,188 s in speed-5, $3.24 and 2,658 s in speed-6; subagent reviews are 34 % of the wall time) and the critic is already limited to one round unless it names a blocking fix (D-360). Nothing more to build; ticked with that evidence.

### D-371 - Platform housekeeping (tonight's list, item 14)
Fast test run: `tests/conftest.py` adds the marker `browser` to every test of a module that uses playwright or the Vite harness (144 of 1,661 tests, including the `e2e` ones), so `pytest -m "not browser and not live"` skips them; the marker is registered in pyproject. Timing of the fast run comes after the benchmark runs (no suite beside a timing run).
Parallel pytest in built apps: one prompt line in both system prompts (xdist only for a suite over about two minutes whose tests share no ports or files, after an approved install); no project has shown slow runs yet, so the line is advice, not a rule.
MCP campaign case: not run as a separate campaign; it becomes one of the approach challenges of part 4 (a library API the model may misremember), where it is time-boxed and judged on approach.

### D-372 - library_api: the installed library, not memory (tonight's list, item 15, C8)
The import gate (D-264) catches a module that does not exist; it cannot catch a method or argument that does not. New read-only tool `library_api(package, symbol, query)` asks the app's own interpreter (so it is the version that will run, no network): installed version, public names with signatures, one symbol's signature and docstring, a word search; a name that does not exist is answered with the nearest real names (difflib), which is the attribute-level check. Chosen over a docs fetch from the web: it is exact for the installed version, works offline and behind the company proxy, and needs no approval. Runs through the shell sandbox with `python -I`; empty arguments are passed as "-" because Windows PowerShell 5.1 drops empty arguments. Both system prompts and the python-project skill now point to it. Tests: tests/test_library_api.py (including a real run through the shell). Not done: JavaScript packages (the same idea would read node_modules).

### D-373 - True PDF redaction (tonight's list, item 12, W3)
Drawing a black box over text leaves the text in the file, so the toolkit used to refuse to call anything redacted. New `redact_pdf` (pdfs/redact.py): exact terms (case-insensitive), named patterns (email, phone, card, iban, aadhaar, pan, ssn, date_of_birth; loose on purpose, a miss is worse than an extra box) and regions in PDF points; every page is rendered to a picture (200 dpi), the matches are blacked out, a new PDF is built from the pictures, and the result is checked to have no text layer (the tool says "Verified" or warns). Chosen over editing content streams (fragile, fonts and encodings leave remnants) and over PyMuPDF (AGPL): pypdfium2 and Pillow are already dependencies. Cost: the result is a flat document (not selectable, larger); `ocr_pdf` restores searchability after the redaction. A scan has no text to search: regions are required there and the report names the pages without text. Not done: redaction in Word or Excel files. Tests: tests/test_pdf_redact.py (text really gone; the box sits where the text was; refusals; the tool leaves the original alone).

### D-374 - PDFs in any script (tonight's list, item 12, W3)
reportlab's standard fonts draw Latin text only and reportlab does not shape Indic or Arabic scripts (matras and conjuncts end up misplaced even with a font that has the glyphs). `build_pdf` now goes through `build_pdf_any`: an outline whose text contains Devanagari, Bengali, Gurmukhi, Gujarati, Odia, Tamil, Telugu, Kannada, Malayalam, Thai, Arabic, Hebrew, Greek, Cyrillic or CJK is laid out as HTML and printed to PDF by headless Edge or Chrome (Chromium shapes complex scripts and embeds the fonts), with the bundled Noto Sans Bengali and Devanagari (SIL OFL, already in the font catalogue) and Windows' own fonts for the rest; right-to-left for Arabic and Hebrew; title, language and author set; same brand colours. Without a browser the build falls back to reportlab and the tool result carries a WARNING that glyphs may be missing. Latin outlines are unchanged. Chosen over registering fonts in reportlab (no shaping) and over a pure-Python shaper (a new dependency). Tests: tests/test_pdf_scripts.py (script detection, HTML, fallback path) and tests/test_pdf_scripts_browser.py (real Edge: embedded Bengali and Devanagari fonts, extractable text); the browser test was written but is run after the benchmark runs of the night.

### D-375 - Document themes shared with decks (tonight's list, item 12, W4)
Documents had a brand file but no list of looks to choose from, while decks have 19 contrast-checked themes. `brand_file` now also takes `theme:<name>` (Word, Excel and PDF tools, one shared loader in tools/brand_file.py): the deck theme's accent, fonts and colours become the brand kit, so a report and its deck match. The dark deck themes keep their accent and fonts but get white paper and dark text (documents are printed). Contrast of text on white and of table-header text on the accent is tested for every theme (tests/test_document_themes.py). Chosen over a second theme list for documents (two lists drift apart).

### D-376 - Server-lifecycle helper for browser scripts (tonight's list, part 3, C15)
`web-ui-verification/scripts/with_servers.py` (standard library only): `--server name[@folder]::command::ready-path` (repeatable; `{port}` becomes a free port), waits until each answers (a 200 to 499 reply, or a TCP connection when no path is given), runs the command after `--` with `SERVER_<NAME>_URL` and `SERVER_<NAME>_PORT`, returns the command's exit code (3 = a server never came up, its output printed) and always stops the whole process tree (`taskkill /T` on Windows). The skill teaches it and the "look first, then act" habit. Tested with two real servers, an exit-code pass-through and a server that dies at start (tests/test_with_servers.py). The verifier's prompt is unchanged: it can use the helper when it scripts a two-server app.

### D-377 - React versions of the application screens (tonight's list, item 11)
Five of the 24 screens exist as React: dashboard-kpi, table-data, form-wizard, settings-account, inbox (the most used: a home screen, a records table, a form flow, settings, a three-pane app). They are generated from the same Python definitions through a small HTML-to-JSX converter (class and for, camel-case SVG attributes, style objects with a CSSProperties cast for custom properties, defaultValue and defaultChecked for form controls, self-closing void elements, JSX comments), so the HTML and React versions cannot drift apart. Each ships `Screen.tsx`, one plain `screen.css` (same class names, no Tailwind needed) and `tokens.css`; catalogue ids `app-react-<id>`, tag `react`. Chosen over rewriting each screen in Tailwind utilities by hand (24 times the work, two sources of truth). Tests (tests/test_app_screens_react.py): type-check and Vite build, no console errors, no sideways scroll, a clean audit at 1280 px and the same body text as the HTML recipe; the build part ran in the night, the browser part runs after the benchmark runs. Not done: the other 19 screens (the converter makes it mechanical).

### D-378 - The company look is saved once with the project (tonight's list, item 13, P2.1)
Each build needed the look repeated (outline `brand`, or `brand_file` every time), so documents of one project drifted. New tool `save_brand` (a theme to start from and/or accent, text, background, muted, surface, accent_text, title_font, body_font; validated as six-digit colours) writes `brand.json` in the project root and reports how the colours resolve on white paper; `load_brand_file` uses that file when a build names no brand file (decks, Word, Excel and PDF share the loader). A `brand.json` that is not ours (an unrelated file of a copied repository, which the strict brand model rejects) is ignored, never an error; a named brand or `theme:<name>` always wins. Not done: a logo in the kit (it needs a header or corner placement in four formats) and more font pairings beyond Calibri and Georgia. Tests: tests/test_document_themes.py.

### D-379 - Three defects found in the log of the first serial run of X8 (tonight's list, items 1 and 3)
Read from the event log of the first serial run of X8 (98 model calls, 117,774 output tokens for three throwaway designs):
1. **Mangled characters.** The model's `write_file` arguments carried an en dash and a curly apostrophe as the control characters U+0013 and U+0019 (checkpoint 0028), then as NUL bytes (0029); the file was then "binary" and every later `write_file` to it failed with "is a binary file" until the model rewrote the page in ASCII. The file tools now refuse any text that gains control characters, naming the code point, line, column and context and saying how to write the character (plain, or `&ndash;`, `&rsquo;`) (`control_character_problem` in files.py; a file that already had them is not blocked for keeping them). Whether the model or the transport garbled them is not known; the guard works either way.
2. **A test gate for static pages.** The `task_update` gate asked for a passing test run after any edit, so a design task wrote a pytest suite that checks static pages exist (task T4) and was refused twice. `ToolContext.note_edit` now records code edits separately (`last_code_edit_step`): changes only to .html, .htm, .css, .scss, .sass, .less, .svg, .md, .txt, pictures and fonts do not count; the test, import, review and lint gates use it. The browser and critic gates for pages are unchanged.
3. **The design ladder contradicted a tool.** The candidates note tells the model to `design_md_import` the winner from `.forge/candidates/<x>/DESIGN.md`, but the tool resolved its source like an image and refused every `.forge` folder except four image folders (two refused calls, then a hand copy). `.forge/candidates/` is now allowed for that tool; other `.forge` folders stay closed.
Tests: tests/test_file_control_characters.py, tests/test_orchestrator.py (page-only task), tests/test_design_md_import_candidates.py. Status of X8 itself: still running (docs/SPEED_BENCHMARK.md gets the table when it finishes); runs started after these fixes are merged into main use them, so the arms of later runs differ from the first serial run in these three respects; that is noted in the results.

### D-380 - build_variants: the parallel route as one tool call (X8, tonight's list item 1)
Result of the first X8 pair (serial 2,788 s with 100 model calls; parallel 1,441 s with 64): the parallel arm spawned no builder at all. Its reasoning log says the model loaded the parallel-builders skill and then decided to "treat this task as a single-agent job to minimise coordination errors"; it built all three designs itself, so the arms were identical and the difference is route variance, not parallelism (the benchmark was stopped after that pair). Advice in a prompt or a skill did not change the behaviour, so the parallel route became a tool: `build_variants(brief, variants[name, folder, direction])` starts one builder per variant (own folder, shell and port; at most `limits.max_parallel_builders` at once, `limits.max_parallel_builders: 1` runs them one after another), tells each what the others do so they differ, asks each to write its own DESIGN.md in its folder and build from its tokens (builders skip the project design gate), returns every report, and marks the pages as unverified edits so the browser and critic gates apply. Folders must not overlap; names are unique. Both system prompts and the design skill name it. Tests: tests/test_build_variants.py (concurrency up to the limit with fake builders, refusals). X8 restarts with this tool in both arms (arms differ only in the limit), so it measures parallelism if the model calls the tool in both.

Result (D-380 follow-up): three pairs, serial mean 2,487 s and $3.45, parallel mean 1,336 s and $2.82 (46 % faster, 18 % cheaper, faster in every pair, no Azure 429 at three builders). Details and caveats in docs/SPEED_BENCHMARK.md.

### D-381 - Benchmark runs notice a stalled machine (2026-10-15)
Evidence: in the first brief of the night's design benchmark one model call "took" 6,700 s: the log shows Request timed out and getaddrinfo failed, so the machine slept or lost its network for about 1 h 50 min; the run recovered by retries and its wall time was meaningless.
Decision: `timing()` now reports `timing_valid`, `longest_gap_s` and `longest_model_call_s` and marks a run invalid when no event or model answer happened for 15 minutes (STALL_LIMIT_S); the design and parallel-design tables print `(INVALID: stalled N s)` beside the wall time; every benchmark runner calls `keep_awake()` (scripts/benchmark/awake.py: Windows `SetThreadExecutionState`, no effect elsewhere) so the machine does not sleep while the run lives. Tests: tests/test_benchmark_guard.py. The check cannot tell a sleeping laptop from a model that really hangs; either way the timing is not usable.

### D-382 - Forty micro-interactions of our own (tonight's list, item 22; L4 b and L2)
The animation library had page-level effects (entrances, scroll, ambient) but few small controls. Forty micro-interactions written by us as plain CSS: 8 loaders (bouncing dots, wave bars, ring, orbit, moving stripes, ripple, flipping tile, heartbeat), 6 toggles (sliding switch, sun and moon switch, drawn checkmark, popping radio, sliding segmented control, selectable chip), 10 buttons (fill sweep, arrow slide, raised and pressed, drawn border, shine, icon turn, press ripple, lift and shadow, glow pulse, busy state), 8 inputs (floating label, growing underline, focus ring, glow, invalid shake with :user-invalid, expanding search, lit prefix, turning select arrow) and 8 cards (lift, tilt, moving gradient border, slide-up details, flip, image zoom, folding corner, fanning stack). One stylesheet `recipes/motion-micro.css` (prefixed `mi-`, tokens with fallbacks, stopped by prefers-reduced-motion), forty catalogue effects (`mi-*`) with markup and usage notes, all generated from definitions in `scripts/dev/micro_effects/` by `scripts/dev/make_micro_effects.py`. Written, not copied: Uiverse's licence is not needed (item L4 b asked to curate its elements with attribution; we chose our own versions in our own words, so there is nothing to attribute). Proof: `tests/test_micro_effects.py` runs every effect in Edge from the same definitions (the action changes the probed property or the animation runs; reduced motion switches animations and transitions off); the catalogue part and retrieval tests pass; the Edge part was written during a benchmark run and runs when the machine is free. Retrieval: six prompts added; three existing effects got more tags because the new cards, forms and typing words had displaced them (46 of 48 old prompts still hit).

### D-383 - React motion hooks and the effect budget (tonight's list, item 23; L2)
`recipes/motion-hooks.tsx` and `motion-hooks.css`: `SplitText` (words or letters rise in with a stagger, the whole text is the aria-label), `ScrambleText` (letters settle from noise to the real text once), `Magnetic` (a child leans toward the pointer, pointer devices only), `PinnedSteps` (a list with a sticky panel; the active step follows the scroll, one column with the panel on top on a phone) and `Parallax` with `useScrollProgress` (decorative layers only). Five catalogue effects (`fx-react-*`, tag `react`). The number ticker already existed as `CountUp` in motion.tsx, so it was not duplicated. Everything is final and static under prefers-reduced-motion and the real text is always in the DOM. The skill gets the per-intensity effect budget: what each MOTION_INTENSITY level may include (1-2 none, 3-4 one entrance style, 5-6 plus one scroll effect and one ambient background, 7-8 plus magnetic, scramble and a parallax layer, 9-10 several scroll effects but never text a person needs inside a moving layer). Proof: type-check and Vite build pass now; tests/test_motion_hooks.py runs the behaviour in Edge (words visible, scramble ends on the real text, magnet moves, pinned step follows the scroll, parallax moves; reduced motion is static) when the machine is free.

### D-384 - Beam, particles and globe (tonight's list, item 24; L6)
Three showpiece effects that need a little code, written by us in `recipes/motion-canvas.tsx`: `AnimatedBeam` (an SVG curve between two measured elements with a travelling light, re-measured on resize), `Particles` (a canvas of drifting dots with faint links; pauses while the tab is hidden or the canvas is off screen; devicePixelRatio capped at 2) and `GlobeLite` (a sphere of dots in latitude rings turning about its vertical axis; no map data). Decoration only: they set aria-hidden, read `--color-primary`, and under prefers-reduced-motion the beam is a still line and the canvases are drawn once. Three catalogue effects (`fx-react-animated-beam`, `-particles`, `-globe-lite`). Proof: type-check and Vite build pass now; tests/test_motion_canvas.py checks in Edge that the beam has its line and light, both canvases paint and keep changing, and reduced motion freezes them; that test runs when the machine is free. Item L6 (d), verifying the real Magic UI components, still needs the registry on the office laptop.

### D-385 - Three more templates in new directions and five new sections (tonight's list, item 25; L1)
The template library had three landing pages (charity, SaaS, portfolio). New directions: **a craft shop** (`tpl-shop-craft`: Playfair Display and Plus Jakarta Sans, sage green on warm stone), **a conference** (`tpl-event-conference`: Space Grotesk and Inter, bold orange on cool slate, tighter corners) and **product documentation** (`tpl-docs-product`: Inter and JetBrains Mono, teal on slate). They needed five new sections, now in the section library: `ProductGrid`, `CategoryTiles`, `ScheduleList` (day tabs as real tab buttons), `SpeakerGrid` and `DocsShell` (sticky navigation, article with code block and note, On this page list; a native details menu on a phone). Each template carries its own `index.css` tokens (same token names as the other templates, so every section restyles), its fonts (variable woff2, OFL texts copied) and example copy that the model must replace. Still to come for the L1 target (20+ templates): onboarding and pricing pages, an admin template (the application screens cover that need in plain HTML and React), and more directions. Proof now: the three templates type-check (tsc strict) and build with Vite from the catalogue entries; the Edge part (audit clean at 1280 and 375 px, screenshots) is `tests/test_sections.py` with the three ids added, to run when the machine is free; the gallery test of all sections together will exercise the five new sections too.

### D-386 - A candidate DESIGN.md is told at once that it names no composition (S5 follow-up, from the night design run)
In the second brief of the design benchmark every candidate was written, refused later by `design_candidates` ("NOT USABLE until it names its composition") and then rewritten in full, three files of about 80 lines each, twice. The write of a file under `.forge/candidates/` now ends with one line when its front matter has no `composition:` (lay-..., app-... or custom ...) and says to add it with one small multi_edit, not a rewrite. Only candidate paths are reminded; the other DESIGN.md writes are unchanged. Test: tests/test_design_md_import_candidates.py. The effect on the number of rewrites is measured by the next design run (the run in progress started before this change).

### D-387 - The CC0 prompts of superdesign-prompts are not bundled (tonight's list, item 30; DS3 and DS6)
Checked 2026-10-15 (web search): no repository named `superdesign-prompts` could be found; Superdesign's prompt library lives in its web app and documentation, and no licence statement for it was found (a directory says "not explicitly stated"). The main repository `superdesigndev/superdesign` is the original open-source extension, kept for history. Nothing confirmed as CC0, so nothing is bundled; our design prompts stay written in our own words (D-348, DESIGN_STUDIO.md). The item is closed. If the owner publishes a clear licence later, a few prompts can be added with attribution.

### D-388 - The brand kit has a logo (TODO P2.1)
`BrandKit.logo` names a PNG or JPEG in the project. Word documents put it (1 cm high) at the start of the header; PDFs draw it in the top margin (reportlab) or in the browser header template (the non-Latin path). A logo that cannot be read is a clear error, not a silent skip. Options: header only (chosen: it needs no layout change in the body), a cover-page logo (later, with cover pages), or a watermark (rejected: lowers legibility). The old test that rejected a `logo` key now uses another unknown key. Decks and workbooks do not use it yet.

### D-389 - Pricing page template (tonight's list, item 25)
`tpl-pricing-invoicing`: Outfit and Manrope, burnt orange on slate, built from existing sections (NavBar, HeroCentered, LogoStrip, PricingTiers, StatsRow, FaqList, CtaBand, FooterColumns) so only the composition, tokens and copy are new. Added to the catalogue and to the template list of tests/test_sections.py; its entry says `tested: NOT YET BUILT` until that test has run (browser tests wait for the design benchmark). Chosen over a new PricingTiers variant: the section already covers three plans with one featured.

### D-390 - Font pairings for themes (P2.1)
`FONT_PAIRINGS` (modern, editorial, formal, plain, book, literary) holds only fonts every Office install has, so a pairing can never make a reader's computer substitute a font. Themes choose one with `fonts=`; forest and olive are now Cambria + Calibri, mono is Arial, the other serif themes keep Georgia + Calibri. PDFs map the serif fonts to Times (reportlab has three standard families). Options: web fonts embedded in the deck (rejected: pptx embedding is unreliable and the lint warns about unsafe fonts), or a bigger theme-specific list (later, if the user wants more). Test: tests/test_document_themes.py. The logo for decks and workbooks is still open.

### D-391 - browser_screenshot reloads the page after edits (found in benchmark night-1, brief d03)
In the ops-dashboard brief the audit reported 'BLOCKER: all the text is set in the system font stack (inter, space grotesk)' in all four screenshot pairs, even after the model had fetched and linked Manrope and DM Sans, so three of five tasks ended blocked (exit 2). Cause: the page was opened once (03:08) on a static server and never reloaded; `browser_screenshot` photographed and audited the page as loaded, not the files as edited. Fix: `BrowserSession.loaded_step` is set by `browser_open`; a screenshot after any later edit (`last_edit_step`) reloads first and says so in the result. Chosen over telling the model to call `browser_open` again (it did not, and a hidden stale page is a trap for any model). A dev server with hot reload is unaffected (one extra reload). Test: tests/test_browser_reload.py (a stub page). Consequence for the running benchmark: d03 (and d04/d05 if the model edits after opening) have audit results from stale pages; those briefs must be rerun on the fixed code before any quality or timing conclusion is drawn.

### D-392 - The brand logo on decks; not on workbooks (P2.1)
`Deck.brand.logo` (a PNG or JPEG in the project) is placed 0.34 in high at the top right of every slide of a deck built from the outline, in the top margin above the title box so it never overlaps text; template decks are left alone (the template carries its own logo). A workbook gets no logo: openpyxl cannot put a picture in the print header, and a picture on the first sheet would push the table down; the brand colours and fonts are what carry a workbook's identity. Test written, not yet run (tests/test_brand_logo.py), by the user's instruction to run tests only when development is complete.

### D-393 - S5 follow-up from the night-1 logs: decide the directions before writing candidates
Logs of d02 and d03 (scripts/dev/run_log_summary.py): both runs wrote all three candidate files, were refused as 'not different enough', and rewrote whole files (3 candidates written twice in d02, 4 file writes repeated in d03, about 40 to 140 s each). Other repeats in these logs were already handled: control-character refusals (D-379), the missing-composition refusal (D-386), the stale-page audit blocker (D-391). Changes: the skill now tells the model to decide a one-line direction per candidate before writing any file and to write each file from its line; the 'too similar' refusal now says to change only the named candidates, only their front matter, with one multi_edit each, instead of 'rewrite'. Not changed: the similarity threshold (three dimensions) because the rule itself is sound. Whether it holds is measured in the end-of-night benchmark (three runs wanted by the item).

### D-394 - Specimen pictures for the font pairings (TODO L3, item 27)
`scripts/dev/make_font_previews.py` renders each bundled pairing from its own font files in Edge (headline in the display font, a paragraph and an interface line in the text font) to `assets/preview/pair-*.jpg` and sets `preview:` in the asset's front matter. The Bengali and Hindi pairings use native sample text (checked by eye: conjuncts and matras render correctly with the Latin interface line beside them). Item L3 is closed: reach by D-330, curated pairings with pictures by this. Not done: growing the bundled set beyond 14 families (any open font is already available through find_font and fetch_font).

### D-395 - A reference picture per section and per direction (item 26, L10)
`scripts/dev/make_section_previews.py` builds the 19 sections together on the charity tokens (as tests/test_sections.py does), photographs each on its own at 1280 px and writes `assets/preview/sec-*.jpg` with `preview:` set in the asset files; each direction asset points at the specimen picture of the design system it pairs with (`ds-<name>-specimen.jpg`), which already is a demo page in that direction. Chosen over a separate demo page per direction: the specimens exist, are tested and show tokens and a real page. Run the script again after a section changes.

### D-396 - Built hero per candidate and the ask-me-first setting: not built (item 30)
Options for the built hero: (a) the specimen picture each candidate already gets (headline in the display font, buttons, colour swatches, tokens applied: `designsystem/specimen.py`); (b) a real hero section of the candidate's composition built per candidate with Vite, about 1 to 2 minutes each and three per brief. Chosen (a): the independent critic already judges the specimens and the winner is built in full right after, so (b) would add minutes to every design run for a picture of a page that is built anyway (D-161 allows time only where it improves the result; here it does not). The ask-me-first setting contradicts the escalation ladder the user agreed on 2026-10-14 (step 1 designs without asking); step 3 already asks. Both stay out unless the benchmark shows the critic picking badly from specimens.

### D-397 - React versions of all 24 application screens (item 11)
The HTML screens have no scripts, so the same HTML-to-JSX converter that made the first five now makes the other 19 (`scripts/dev/make_app_screens.py` with `REACT_IDS = None`); 19 new catalogue entries `app-react-*` (the HTML files are unchanged: the generator is deterministic). tests/test_app_screens_react.py now covers every folder in recipes/app-react (type-check, Vite build, both widths, text equal to the HTML). They have NOT been built or audited yet (tests run at the end of the night); a screen that fails gets fixed in its definition under scripts/dev/app_screens/. Risk: 19 more app assets can lower the retrieval hit rate (tests/test_assets.py, threshold 90 percent); retag if it does.

### D-398 - React versions of the seven page compositions (item 10, DS7 remainder)
`scripts/dev/make_react_compositions.py` converts each `recipes/compositions/<name>.html` with the application-screen converter into `recipes/compositions-react/<name>/` (`Composition.tsx`, `composition.css`, `tokens.css`) and writes the catalogue entry `lay-react-<name>`. Same class names, text and drawn art, so a Vite project can start from a composition. `tests/test_compositions_react.py` type-checks, builds, audits at both widths and compares the text with the HTML recipe; written, not yet run. `tests/test_compositions.py` ignores the `lay-react-` ids when it counts the seven HTML compositions; the folder is in the parity bulk list. More than seven compositions: not authored (a new layout is a design task whose value only shows in the benchmark; see how often the candidates pick a composition in the end-of-night runs).

### D-400 - Smaller checks: quick_check.py and mini design briefs
The full suite takes about 7 minutes (145 tests start Edge) and the five design briefs about 1.5 hours. Two smaller tiers: (1) `scripts/dev/quick_check.py` lints the changed files and runs only the test files that mention the changed modules (text search of tests/, no browser tests unless `--browser`), seconds to a minute; (2) `run_design_benchmark.py --mini` runs two small briefs (`m01_hero_only`, `m02_settings_card`, about 5 minutes each) marked `"mini": true` in their task.json; without the flag the five full briefs run as before. The full suite and the full briefs stay for the end of a batch and for any conclusion about quality or speed (one small brief is noise). Not done: splitting the browser tests into a smaller smoke subset; say so if the 145 browser tests are the part that hurts.

### D-401 - shadcn verified on the office laptop (2026-10-15); prerequisites to put in the skill
Result of the user's run (Node v24.7.0, PowerShell, `NODE_USE_SYSTEM_CA=1`): `npx shadcn@latest --version` printed 4.21.5; `npm create vite@latest shadcn-try -- --template react-ts` (it asks for a linter: ESLint or Oxlint), `npm install` (185 packages, 0 vulnerabilities) and `npx shadcn@latest init` reached the registry, wrote components.json, installed dependencies, created src/components/ui/button.tsx and src/lib/utils.ts and updated src/index.css. D-363 is confirmed for Node 24 outside the sandbox. A fresh Vite project fails `init` with 'No Tailwind CSS configuration found' and 'Could not find valid path aliases' until three things exist: `npm i tailwindcss @tailwindcss/vite`, `@import "tailwindcss";` in src/index.css and the `tailwindcss()` plugin in vite.config.ts, and the `@/*` alias in tsconfig.json AND tsconfig.app.json plus `resolve.alias` in vite.config.ts (and `npm i -D @types/node`). The shadcn quickstart in the skill must list these first; its edit waits for the end of the design benchmark (night-2) so the benchmark's skills do not change mid-run. VERIFIED 2026-10-15 by the user: `forge doctor` reports 'Node certificates: Node v24.7.0 reads the Windows certificate store for commands DebCraft runs', and asking DebCraft (auto mode, after the approval card for the unlisted command `npx`) to run `npx shadcn@latest --version` in a project returned 4.21.5: the sandbox can use the certificate store. Observation: `npx` is not on the command allowlist, so every npx run asks for approval ('Allow once' or 'Always allow <command>'); left as it is on purpose, since npx runs downloaded code.

### D-402 - shadcn without hand work, and certificate errors recovered by Forge (user request 2026-10-15)
Context: on the office laptop the shadcn CLI worked with NODE_USE_SYSTEM_CA=1 (D-401), but a fresh Vite project failed `init` until Tailwind and the `@/` alias existed, and any Node older than 22.15 or any other tool that ignores the Windows store would hit 'unable to get local issuer certificate' again.
Options: (1) only document the steps in the skill (a weaker model skips or reorders them); (2) a tool that does the steps as code and a shell layer that recovers from certificate failures (chosen); (3) switch certificate checking off (rejected: removes the protection, also forbidden in the advice text).
Built: `shadcn_setup` (tools/shadcn.py): creates the Vite + React + TypeScript project if there is no package.json, installs `tailwindcss` and `@tailwindcss/vite` (and `@types/node`), patches src/index.css (Tailwind import first, the template's rules kept), vite.config.ts (plugin and `resolve.alias`; a config of unusual shape is left alone and the exact edit is returned) and both tsconfig files (`baseUrl` and `@/*`, comments kept), runs `npx shadcn@latest init -b radix|base -y --no-monorepo` and `add <components> -y`; idempotent. Radix is the default because most documentation and examples use it (the CLI itself recommends Base UI; the parameter selects it). Certificates: `forge.net.windows_certificate_bundle` writes the Root and Intermediate stores of Windows (read with `ssl.enum_certificates`, no administrator needed) as one PEM file; `ShellSession` passes it as `NODE_EXTRA_CA_CERTS` from the start when the installed Node is older than 22.15 and, for any Node, after a command failed on a certificate error (`looks_like_certificate_error`); the failed command's result then tells the model to run it again, and the shadcn tool repeats the failed step once by itself. A second failure with the bundle already in use is handed to the user with what to do (invariant 6), and the advice names `NODE_TLS_REJECT_UNAUTHORIZED=0` as forbidden. The skill's shadcn section (D-401 prerequisites) now says to call the tool.
Tests: tests/test_shadcn_setup.py (patch functions on the files create-vite writes, certificate patterns, the Windows bundle read by Python as a CA file, the advice switch); the whole tool runs with `FORGE_NETWORK_TESTS=1` (npm and the network, minutes). Not changed: the command allowlist (npx still asks for approval; 'Always allow' is the user's choice, because npx runs downloaded code).
Limits: the retry only helps when the company root is in the Windows store (it is on the office laptop, D-401); Next.js projects are not handled (the tool says to run init by hand); the bundle adds about 90 KB of certificates to the sandbox folder.

### D-403 - Gemini 3 answers from the `global` endpoint: models added, designer A/B prepared (DS8)
Probe result (the user's office laptop, 2026-10-15, with the Windows certificate store): through `global`, `gemini-3.1-pro-preview` (text 3.5 s, pictures ok), `gemini-3-flash-preview`, `gemini-3.1-flash-lite` and `gemini-3.5-flash` answer text and pictures; `gemini-3-pro-image`, `gemini-3.1-flash-image` and `gemini-3.1-flash-lite-image` generate images (22 s, 14 s, 6 s); the 2.5 family answers everywhere including `global`. The earlier 'not available' came from asking `us-central1`, where the models are listed but not served. So the old certificate error (D-363) and the wrong region were the whole problem; no code change was needed in the provider, only `GOOGLE_CLOUD_LOCATION=global` in the user's .env.
Done: optional models `gemini31pro` (gemini-3.1-pro-preview) and `gemini3flash` (gemini-3-flash-preview) in defaults/config.yaml (prices are placeholders from public list prices; no role uses them until a role names them); `run_design_benchmark.py --coder-model <key>` changes only the builder roles (coder, kb_builder, summariser), so the reviewer, the vision check and the judge stay on Azure and the judge is not the builder's own family (`--all-roles` remains for the all-one-model case).
Next, on the office laptop only (this machine has no Google credentials): the design benchmark with `--coder-model gemini31pro` against the same briefs with the Azure builder, a blind comparison of the screenshots, and the decision which roles use Gemini 3 (DS8). Options if it wins: designer role for DESIGN.md candidates and page builds only (chosen first: the part where taste matters), or all builder roles. If it does not win: keep gpt-5.1 and close DS8.

### D-403 addendum - the probe finished (office laptop, 2026-10-15 11:22)
Every Gemini 3 model of the project answers text and pictures from `global`: 3.1 Pro preview, 3 Flash preview, 3.1 Flash-Lite, 3.5 Flash, 3.5 Flash-Lite, 3.6 Flash, 3.7 Flash, 3.8 Flash, plus `gemini-4-argon` and `gemini-nano-banana-2.1` (codenames; not added to the config); the two `omni` names fail with 400. Image output from `global`: gemini-3-pro-image (22 s), gemini-3.1-flash-image (14 s), gemini-3.1-flash-lite-image (6 s) and gemini-2.5-flash-image everywhere. Changes: the Gemini chat provider's default region is now `global` (the 2.5 family answers there as well, so no model loses); the image tool defaults to `global` when GEMINI_IMAGE_MODEL names a gemini-3 model and keeps us-central1 otherwise; `gemini38flash` added next to `gemini31pro` and `gemini3flash`; the setup guide, the drawer's Gemini steps and .env.example say `global`. Tests for Gemini, image generation, environment and config: 93 passed.

### D-404 - The environment panel ("Test all"): a Gemini row that says which generation works, and a Node row
Context: the panel's Gemini test called one model (the first Gemini model in the config, or gemini-2.5-flash-lite) and said only pass or fail; it could not tell a working Gemini 3 from a project that only has 2.5, and the region was invisible. Nothing in the panel checked Node, npm or the certificate path that shadcn and React builds depend on (D-363, D-401, D-402).
Changes (backend checks; the panel draws rows from the check list, so the only React edit is one word: `node` joins the rows that say 'Connected'): (1) Gemini: one short call per model, the model a role uses (else the first Gemini model in the config) and always gemini-2.5-flash-lite; the row shows each answer and the region used (`global` by default); if the newest answers and the small one does not, or the other way round, the row is a warning that names the failure and says to set `GOOGLE_CLOUD_LOCATION=global`; (2) a new optional row `Node.js and npm`, asked first (Will you build web apps with Node?) like Gemini and Tavily: Node on PATH and its version, npm, how Node gets the Windows certificates (its own store from 22.15, else the exported bundle) and one real `npm view shadcn version` against the registry, which proves the certificate path and the network; a certificate failure says the company root is missing from the Windows store and lists the steps (install it, or NODE_EXTRA_CA_CERTS, never switch checking off). Tests: tests/test_environment.py (the check list, the model list, the Node row for missing Node, a certificate failure and success). The React build (`npm run build`) waits for the end of the design benchmark.

### D-405 - The model lists show every model; Gemini 3 is the proposed default once Gemini has answered (user request 2026-10-15)
Context: the 'Models' lists of the environment panel showed only models that had answered the Azure test, so Gemini models never appeared; and the user wants Gemini 3 used by default because it is the better model family.
Done: (1) the Gemini test now records which Gemini models answered (`models`, by config key) and tests every Gemini model of the config plus the small 2.5 one; (2) the lists show every model with its state ('did not answer', 'not tested yet' or nothing when it answered) instead of hiding the ones that did not answer; (3) when the user has answered Yes to 'Is Gemini enabled for you?' and the test passed, the plan proposes Gemini 3.1 Pro (else 3.8 Flash, else 3 Flash) for the coder, knowledge-builder and vision roles and 3 Flash for the summariser; the reviewer, the judge and the fallback stay on Azure, so a reviewer or judge is never the builder's own family; a saved choice of the user still wins; with no Gemini test or a failed one every role keeps its Azure default.
Why a proposal the user confirms and not a changed config default: the default config must work for someone who has only Azure; and sending every prompt and file of a project to Google Vertex AI instead of Azure is a decision about where data goes (CLAUDE.md: security-relevant), which the user makes per machine by answering the Gemini question and confirming the plan. Not measured yet: whether Gemini 3 builds better pages (the design benchmark A/B with `--coder-model`), whether the adapter handles a long agent loop with Gemini 3 (tool calls, thought signatures; only short calls were verified) and what it costs (placeholder prices). If the first real projects show a problem, change the role in the panel; the Azure models stay listed.
Tests: tests/test_environment.py (the Gemini model list, Gemini as the proposed default, Azure kept when Gemini was not tested or failed, every model listed with its state, an earlier choice beating the default). The React build waits for the merge.

### D-406 - Compositions must be real catalogue ids (from the night-2 design run)
Seen in night-1 and night-2 (docs/DESIGN_BENCHMARK.md): candidates named `composition: app-northline-bright-logistics`, `app-kestrel-booking-wizard` and `lay-admin-table`; `design_candidates` accepted any text, so the tested screens were never copied (AS1 failed in the dashboard and wizard briefs: no `app-*` asset copied, 66k output tokens for the dashboard). Change: `design_candidates` refuses a candidate whose composition is not a catalogue section id (or `custom <idea>`), names the four nearest real ids by name similarity, and after the vote tells the model to `add_asset` the winner's composition. Chosen over a hard gate in `task_update` (a second place to maintain) and over auto-copying the asset (the model should choose the right screen). Tests: tests/test_design_candidates.py (an invented id is refused with real ids named, a real id with trailing words and `custom` are accepted). Measured in the next design run: is an `app-*` or `lay-*` asset copied in application briefs.

### D-402 addendum - the whole tool run against the real network (2026-10-15, build machine)
`FORGE_NETWORK_TESTS=1 pytest tests/test_shadcn_setup.py` creates a Vite project, installs, patches and runs shadcn and adds `button`, then runs again: 13 passed in 81 s. Two real bugs found and fixed: (1) the shell refuses a working folder that does not exist yet, so the tool now creates the project folder first; (2) `shadcn init -y` without `-p` stops at the 'Which preset' question and exits 0 without writing anything when there is no terminal: the tool now passes `-p <preset>` (new argument, default nova; names: nova, vega, maia, lyra, mira, luma, sera, rhea; the CLI rejects `radix-nova`) and no longer trusts the exit code: it checks that components.json exists after init and that each added component has its file.

### D-399 - Reference decks collected from the web; the readers swept over them (user decision 2026-10-15)
The user will not supply decks. Collected: 670 `.pptx`/`.potx`/`.ppsx` files from the test data of Apache POI (Apache-2.0), python-pptx (MIT) and LibreOffice (MPL-2.0), kept outside the repository (`scripts/dev/fetch_reference_decks.py`, docs/REFERENCE_DECKS.md); designed marketing templates were not collected (licences). `scripts/dev/reference_deck_sweep.py` ran the template, design and sample readers over all of them: 646 opened, 24 are python-pptx's limits (fuzz files, strict OOXML), and one real defect in our readers (a master listing a missing layout gave a bare KeyError) is now a clear 'the presentation is damaged' error. No reader crashed on any of the other files. What the sweep cannot tell: how well the readers understand a well-designed corporate deck (these are test files, mostly plain); that stays open until a real company template is tried.

### D-407 - Gemini 4 Argon added; first choice for the coder roles once it answers (user pointed to the announcement, 2026-10-15)
Source: Google's announcement of Gemini 4 Argon (blog.google, read 2026-10-15): a frontier model for real-world coding, enterprise knowledge work and cyber defence, built for long multi-step tasks; Google reports 77.9 percent on DeepSWE v1.1, first on Zapier's AutomationBench, output limit raised to 1M tokens (64K before), $2 / $10 per million tokens introductory and $4 / $20 later; the post gives no model id, no Vertex AI or region statement and no preview or GA label, and access is staged (trusted cyber defenders first, then paid API customers). `gemini-4-argon` answered text and pictures from `global` on the user's project (probe, same day), so it is available to this user now.
Done: optional model `gemini4argon` (model_name `gemini-4-argon`, introductory price, input context and output limit marked to confirm); the plan prefers it for the coder and knowledge-builder roles when it has answered the Gemini test, and keeps Gemini 3.1 Pro first for vision. The reviewer, the judge and the fallback stay on Azure. Nothing changes for anyone whose test did not pass.
Caveats stated plainly: the benchmark numbers are Google's; whether Argon codes better than gpt-5.1 inside this agent loop is not measured (the C1 coding benchmark and the design benchmark on the office laptop decide it); the access is staged, so a project can lose it, and the introductory price doubles later; a 'preview' model may change behind the same name. The A/B on the laptop uses `--coder-model gemini4argon` against the Azure default and `gemini31pro`.

### D-409 - Gemini 4 Argon is the critic and the judge; the builders stay on Azure (user decision 2026-10-15)
The user chose to keep Gemini 4 Argon for the critic and the judge. Finding while doing it: the design-critic subagent ('the independent designer') ran on the coder role, i.e. the builder's own model, and so did the vote between design candidates (role `vision`); the independence was only in the prompt. Changes: a new optional role `critic` (config `llm.roles.critic`, unset means the coder's model, so nothing changes for anyone who does not set it); the design-critic subagent and the candidate vote now call the `critic` role; the `critic` role needs a model that reads pictures (like `vision`). The plan proposes `gemini4argon` (else `gemini31pro`) for `critic`, `judge` and `reviewer` once the Gemini test has passed, and no longer proposes Gemini for the coder, knowledge builder, summariser or vision roles (D-405 and D-407 had proposed it): the builder side keeps its Azure model until the A/B on the user's laptop says otherwise. The code reviewer joins the critic and the judge on the same reasoning (another family than the builder, and Argon is a coding model); the panel row can be changed. The panel shows the new row as 'Design critic'. Tests: tests/test_environment.py, tests/test_config.py.

### D-410 - Two more approach gates from the challenge reruns: noticed risks and big rewrites
Rerun of c05, c08, c09, c10 (2026-10-15, night-2): the baseline gate worked (c08 ran the tests and probed the old numbers with `python -c` before editing; c05 now escapes LIKE wildcards), but two things did not follow a prompt line: c09 never mentioned the pickle loader and the committed token in the file it changed, and c10 rewrote the whole shipping function in one write before pinning any behaviour. Changes: (1) `safety/risk_scan.py` scans the source files read in the session for six patterns (unsafe deserialisation, eval/exec, SQL built from strings, hard-coded secrets, shell commands from strings, certificate checks turned off); when the model has changed something and its final reply does not name them, the loop asks once, before ending the turn, for a 'Noticed, not changed' list; (2) `tools/baseline_gate.rewrite_gate`: a `write_file` that keeps less than half of an existing source file of 30 lines or more is refused once until a test file has been written in the session, with the way to pin the behaviour. Both are notices with one reminder, never traps. Tests: tests/test_risk_scan.py, tests/test_rewrite_gate.py.

### D-411 - Roles, planner and rate-limit fallback across model families (user: decide, research first; be like Claude Code)
The user delegated the role decisions, asked for the web research first, wants Forge to behave like Claude Code, and wants a call to another model family on a rate limit. Evidence and decision: docs/MODEL_ROLES.md. Summary: coder gpt-5.4 (proposed once its resource answers; the shipped default stays gpt-5.1); a new `planner` role (plan mode and a read-only `planner` subagent, used on demand for large or ambiguous work) on Gemini 4 Argon, else Gemini 3.1 Pro, else the coder, with no permanent planning stage because the evidence for planner/executor splits is mixed; critic, judge and reviewer on another family (D-409); knowledge builder, summariser and vision stay on gpt-5.1; the fallback is another family. Built: role `planner` (unset means the coder) and the plan proposals in `environment/plan.py` (`PREFERENCE`); the Azure test now also tests unused Azure models whose .env values are set (gpt54); `Router._fallback_for` (after the retries of a retryable failure, switch to the fallback role, the coder's model or `llm.fallback_also`, preferring a model of another provider; a Gemini model that fails falls back to the coder's Azure model); `--coder-model` for the code benchmark; the planner guidance in both system prompts. Not built: per-task routing between 5.1 and 5.4 (switching models inside one conversation loses the cache and the reasoning thread; D-155 removed escalation ladders). Measured next: night-gpt54 here, the Argon critic and planner A/B on the user's laptop.

D-411 confirmed by the user on 2026-10-15 after the research and the first gpt-5.4 results. One check stays open on purpose: the speed of gpt-5.4 as the coder against gpt-5.1 (run night-gpt54); if it is clearly slower with no gain in correctness the coder proposal goes back to gpt-5.1, with the user told.

### D-413 - gpt-5.2 added as the Azure critic, judge and reviewer (user pointed to it, 2026-10-15)
Checked live from the build machine with scripts/dev/model_options.py against the second Azure resource (ai-openai-engg): `aicloud-gpt-5.2` (gpt-5.2, 1.5 s), `aicloud-gpt-5.2-chat` (a chat-tuned latest model, 0.7 s) and `aicloud-gpt-5.4` (1.4 s) all answer text and pictures. Done: optional model `gpt52` (deployment name from the new `AZURE_GPT52_DEPLOYMENT`, the second resource's endpoint, key and API version; placeholder price, 400K window to confirm); the model plan proposes it for the critic, the judge and the reviewer when no Gemini model has answered (Gemini 4 Argon, else Gemini 3.1 Pro, still come first), which is stronger than gpt-4.1 for those jobs; the planner stays with the coder in that case (a planner weaker than the coder is pointless). Not chosen as the coder: the research is mixed between 5.2 (ahead on SWE-bench Verified) and 5.4 (ahead on SWE-bench Pro, 1.05M window, trained for long agent runs) and 5.4 is being measured (night-gpt54). `aicloud-gpt-5.2-chat` was left out: its served model name is a moving alias, which makes a benchmark or a critic's verdicts hard to compare over time.

### D-414 - The coder stays gpt-5.1; gpt-5.4 is available but not proposed (result of the check D-411 left open)
The run `night-gpt54` (docs/CODE_BENCHMARK.md) gave the same result as gpt-5.1 on the fourteen coding tasks (13 of 14, 309 of 310 tests, the same miss) in 39 percent more time, with 45 percent more model calls and 2.9 times the cost. Accuracy and speed come first (D-161), and the speed went the wrong way with no accuracy gain, so the model plan no longer proposes gpt-5.4 for the coder; it stays selectable in the panel for a task the user knows is hard. gpt-5.4 and gpt-5.2 are now the first Azure choices for the fallback after Gemini 3.1 Pro (a second resource has its own quota and outage domain, so it survives a rate limit on the first). The planner follows the coder unless Gemini answered. A fair test of gpt-5.4 on hard work needs hard tasks: the four harder coding tasks and the approach challenges are the nearest we have, and no run so far shows 5.4 ahead there; add tasks before reopening this.

### D-415 - The doctor runs at every start; the model lists unlock only after a full test (user request 2026-10-15)
Two requests. (1) `Start-DebCraft.cmd` (through scripts/run_forge.ps1) now runs DebCraft's doctor after the install step and before the UI opens: one line per check, the same text saved to doctor-report.txt, a note when a line says FAIL, and DebCraft starts anyway (the Environment panel explains each failure). It adds about half a minute (the model calls); `-SkipDoctor` or `DEBCRAFT_SKIP_DOCTOR=1` skips it. `Debcraft-Doctor.cmd` stays for running it alone. (2) In the Environment panel the Models section is locked until every test that applies has finished in the current session of the panel: while tests run it says 'Testing: N of M tests finished', before a full test it says to press Test all, and the role lists and Save models appear only afterwards. Reason: the saved results can come from an older version of DebCraft that did not know gpt-5.4 or the Gemini models, and a list chosen from them is wrong (seen on the user's laptop: gpt-5.4 and gpt-4o 'not tested yet' in the lists). Questions the user has not answered (Gemini, Node, Tavily, Tesseract) do not block the unlock; the section names them as not tested and not offered. Cost: the lists are no longer shown on opening the panel, so changing a model always starts with Test all. Tests: tests/test_web_login_e2e.py (locked before and after reopening, ready after Test all, screenshot environment-models-locked-light.png).

### D-416 - A saved model plan no longer freezes the old proposals (seen on the user's laptop, 2026-10-15)
On the laptop every row said 'Your earlier choice', including the reviewer (gpt-4.1) and the fallback (gpt-4.1) that were saved when gpt-4o and the Gemini models did not answer; the new proposals (Argon as reviewer, Gemini 3.1 Pro as fallback) never showed, because any saved value beat a proposal. Now `environment.json` records which roles the user changed by hand when saving (`manual`, the roles whose saved model differs from the proposal at that moment); only those keep their value, the others follow the current proposal. A plan saved by an older version has no `manual` list, so all its roles follow the new proposals once; the user confirms with Save. The saved plan that sessions apply at start is unchanged until the panel is saved again. Tests: tests/test_environment.py (stale values replaced, a hand-chosen role kept).

### D-417 - Skill A/B loop (C14): what is one skill worth?
FORGE_DISABLED_SKILLS=name1,name2 switches skills off for a process (neither listed nor loadable; forge.parity.skills.discover). scripts/benchmark/run_skill_ab.py runs the coding benchmark twice on the same tasks, as shipped and with the named skill off, one after the other so that they never compete for the machine, and prints one comparison (tasks and hidden tests passed, calls, wall time, cost, per task and in total; --record appends it to docs/SKILL_AB.md). One run per condition is noisy, so a difference is a hint unless it is large; repeat before removing or rewriting a skill. Not run yet: the first measurement (test-first on t11 to t14) is cheap and listed in the overnight summary. Tests: tests/test_skill_ab.py.

### D-418 - The Gemini A/B is ready to run on the laptop
scripts/benchmark/run_design_benchmark.py gets --critic-model (the critic, judge and reviewer roles of a run) and --scorer-model (the benchmark scoring judge, the same in every condition, so use a model that built nothing in the run); docs/LAPTOP_AB.md has the exact commands: a quick pair on the two mini briefs (about 25 minutes), the full pair on four briefs (about 1.5 hours each) and an optional planner check, with what to send back and what I do with each outcome. Nothing in the build is changed between conditions: the coder is gpt-5.1 in both, only the checking roles move.

### D-419 - The audit finds what the user disliked on the night-2 pages
The user looked at the four pages of night-2 and said: no pictures, misaligned areas and texts, improper fonts. Measured on the real pages: three of four had no picture at all (the audit exempted a page with nine form fields as an 'application'), the booking page had prices running into names ('Cyclorama\u00a380'), a grooved default fieldset next to rounded cards, controls in the browser font, and cards of one row at different heights. New audit checks (tools/ui_audit.py): controls and legends that kept the browser font (compared with the fonts of the page's own text); text that runs into the text beside it in a flex or grid row (measured on the text lines of the text nodes, not on the boxes); cards of a row whose tops or heights differ when the row does not stretch them; a fieldset with the browser border. The imagery rule now follows DESIGN.md: a composition that is not an `app-...` screen (a `lay-...` or `custom ...` page) makes the page a brand page and a missing picture a BLOCKER, whatever controls it holds; with no DESIGN.md the old heuristic stays. The skill (ui-design-quality) says pictures are part of the first build (generate_image, else find_image, else a drawn SVG; one style sentence for the whole set; every picture an img with alt text and a fixed size) and lists the alignment and font rules. The new checks also found real defects in our own recipes, now fixed: no `font: inherit` on controls in all 24 app screens, a mini calendar too cramped on a phone, a total with no gap between label and amount, a kanban board with columns of uneven height. Limits: the audit finds hygiene, not taste; whether a page is distinctive stays with the critic and the user. Tests: tests/test_ui_audit_alignment.py, tests/test_ui_audit_brand.py.

### D-417 addendum - first skill measurement: test-first
`run_skill_ab.py` on t11 to t14 (docs/SKILL_AB.md): with and without the `test-first` skill both pass 2 of 4 tasks and 173 of 175 hidden tests; calls 48 against 49, wall 1,140 s against 1,305 s, cost $1.57 against $1.83. No difference in correctness on these tasks: gpt-5.1 already tests first without the skill, and the other gates (D-408, D-410) cover the approach. One run per condition is noisy (t12 scored 68 of 69 in both conditions, 69 of 69 on 2026-10-13); the skill is kept, it costs nothing, and it is not what carries the result.

### D-420 - unDraw is not used automatically (user asked, 2026-10-15)
Official terms (undraw.co/license, read 2026-10-15): free for commercial use without credit and the assets may be modified, but they may not be distributed in packs, integrations are discouraged, automated or manual scraping, searching or downloading is covered by the restriction, use for AI or ML training is prohibited, and compiling the assets for a competing service is not allowed. Third-party mirrors call it MIT but are unofficial and the sources conflict. So Forge neither bundles nor fetches unDraw files. It is also the flat purple startup-people style found on thousands of sites, which works against distinctiveness. The user may download illustrations by hand into a project assets folder and Forge uses those files as the user's own (DIE6). Open sets that allow automated use (Open Peeps, Humaaans, Open Doodles are candidates) need a licence check before they are added.

### D-421 - Design blueprint checks are notes, not warnings (DIE2, 2026-10-15)
Options: (a) new blueprint sections required, as warnings; (b) notes (`info`) only; (c) a stricter mode switched on by a front-matter key. The shipped examples, the catalogue and the inspire drafts are tested to lint clean of warnings, and older project files should stay valid, so (b) now: `designsystem/blueprint.py` reports `blueprint-missing` for Page Composition, Imagery and Icons, Motion and Interaction, Responsive Behavior and Accessibility (skipped when listed under `omitted`), and `decision-without-purpose` when more than half of a section's bullets give no reason (a reason word such as because or so that, a dash, or a colon). The new headings are known extras. The template recipe gained the three new sections. Open: the `design_inspire` drafts do not write these sections yet, and (c) can be added when the benchmark shows the notes help.

### D-422 - Discovery first is a skill step plus richer measurements, not a new tool or a gate (DIE1, 2026-10-15)
Claude Code has no discovery step; it is a Forge-specific aid for a weaker model (user asked, 2026-10-15). Options: (A) mandatory first step with a gate; (B) a skill step and a tool, no gate; (C) only references the user supplies. Chosen (B). `design_inspire` already opened pages in the guarded browser and read colours, fonts, sizes and radii, and the model already had `web_search`, so nothing new was built for the search. Added: the type scale per level, the sections in order (height, padding, columns, pictures, buttons) in the browser read, and a per-page reference note (`designsystem/reference.py`, `.forge/inspiration/<page>.reference.md`) with the measurements and two lists for the model to fill after looking at the picture: principles to reuse, and the brand's own that must not be copied. SKILL.md step 1 now starts with the look at the field for brand pages (not application screens, not when a DESIGN.md is binding), read by the model and never a question to the user. To decide on the benchmark whether it helps: the `--mini` briefs with and without it, then make it the default or drop it. The page text stays data (no instructions taken), the address guard and isolated profile are unchanged, nothing is sent anywhere but the page requests.

### D-423 - The user's own pictures come first in find_image (DIE6, 2026-10-15)
Options: (a) a new `brand_assets` tool; (b) the user's files as one more source inside `find_image`/`fetch_image`; (c) an automatic scan in the build loop. Chosen (b): the model already searches pictures through `find_image` and saves them through `fetch_image`, which also writes NOTICES.md, so one more source (`project:<path>`) costs no new tool or habit. `tools/brand_pictures.py` lists the pictures in `brand-assets/`, `assets/brand/` or `brand/` of the project (file names matching the query first, then the rest, up to 6), read only, licence "supplied by the user", no credit line; `fetch_image` copies the chosen file to the page's folder, refuses an SVG with a script or an outside link, and records it. unDraw and similar are therefore usable only as files the user downloads by hand (D-420); SKILL.md tells the model to ask for two or three when the brief wants a flat-illustration style and the folder is empty. Not done yet: bundling a CC0 set (Open Peeps, Open Doodles, Humaaans) after fetching its files and checking the licence texts, and an SVG recolour tool for the user's own illustrations (the model edits the colour values by hand today).

### D-424 - The Argon taste test reuses the design benchmark; no designer role yet (DIE8, 2026-10-15)
Options: (a) route the DESIGN.md step to the planner role inside Forge so one run designs with Argon and builds with gpt-5.1; (b) run the taste test as separate runs and give the builder run the other model's DESIGN.md as a binding input. Chosen (b): arm C (Argon designs and builds) already writes a DESIGN.md per brief, and `run_design_benchmark.py --design-from taste-c` copies it into a gpt-5.1 run as the user's binding design (arm B), so no product code changes before the test says a designer setting is worth having. If B wins, then (a) is built (a designer-model setting). Models do not score the pages for this test; `blind_gallery.py` shows them as Page 1, 2, 3 in a seeded random order and writes the key to a separate file (docs/DESIGN_TASTE_TEST.md). Argon runs only on the office laptop; this machine has no Google credentials.

### D-425 - Card density is measured, and the answer is guidance, not new recipes (DIE7, 2026-10-15)
Options: (a) author editorial and dense variants of every app screen and composition; (b) measure card density in the audit and point the model at the card-free recipes that exist; (c) both. Chosen (b) now: the catalogue already has card-free sections (FeaturesAlternating, StepsTimeline, StatsRow, FaqList, ScheduleList) and card-light compositions (menu-list, vertical-type, poster-hero), and the sameness came from not using them. The audit finds, on a page that is not an application, nine or more outermost rounded boxes (shadow, border or fill, at least 160 x 80 px, with text) in three or more different parents, as a normal finding with the cure; buttons, list items, table cells and fieldsets are not counted. (a) stays open until the benchmark shows the sameness persists.

### D-426 - The design knowledge base is a small word-indexed store in the profile folder (DIE3, 2026-10-15)
Options: (a) embeddings and a vector store; (b) a JSON index searched by word overlap, like the picture library; (c) markdown notes only. Chosen (b): `tools/design_knowledge.py`, `<forge home>/library/design/index.json` plus thumbnails. Two record kinds: references (industry, mood, layout, principles, measured tokens, section order, source link, thumbnail; the model supplies the words and the principles after looking at the page) and uses (accent, background, font pair, composition of a finished design; product and client names are not stored, so Mode B projects leave no host name in it). Industry and mood count double in the search. `design_kb_search` also lists the last five uses so a new design is told what to avoid repeating; a use is recorded automatically when a DESIGN.md is imported (the ladder's winner). Limits kept: 400 references, 60 uses. Word overlap is enough for a few hundred records and needs no new dependency; embeddings can replace the scorer later without changing the tools. Nothing leaves the machine; the page's own text is never stored, only the model's principles and the measurements.

### D-427 - The art director is a read-only subagent on the planner role whose DESIGN.md is one candidate (DIE4, 2026-10-15)
Options: (a) a new model role "designer"; (b) a subagent type on the existing planner role; (c) a tool that writes the file itself. Chosen (b): the planner role already exists, already falls back to the coder's model and is chosen in the Environment panel, and the user's idea (a stronger model plans the design, another codes it) is exactly "planner designs, coder builds". The subagent only reads (references, the knowledge base, the catalogue, view_image) and returns the whole DESIGN.md as text, so it cannot write into the project or change it behind the builder's back (the write jail is untouched); the caller saves it as a candidate, and `design_candidates` still chooses, so the existing independent check is not bypassed. It may run in parallel with other readers. A separate "designer" role stays a later option if the taste test (DIE8) shows a designer should differ from the planner.

### D-428 - The quality gate measures sameness with earlier designs; it advises, it does not block (DIE5, 2026-10-15)
Built before: pictures present, alignment, font hygiene (D-419), card density (D-425), distance from the generic default (the fingerprint, D-350). Added: a use record keeps the design's fingerprint (tone, accent hue, display font, corner style, density, energy, composition), and `design_md_lint` appends a note when the checked DESIGN.md differs in fewer than three dimensions from any of the last five designs (`repeats_recent`, same rule as the candidates). Options: block the design gate on a repeat (rejected: a client may want the same look for a second project, and the fingerprint is coarse); a note the builder reads and the critic can quote (chosen). The blind side-by-side comparison with the user is `scripts/benchmark/blind_gallery.py` (DIE8). Not added: distance from the knowledge-base references (they are other people's sites, and copying their look is not the goal).

### D-429 - Open Doodles is bundled; Open Peeps and Humaaans are not (DIE6, 2026-10-15)
Licence read on opendoodles.com on 2026-10-15: CC0 / public domain, free for commercial use, no credit. Its 32 drawings are published as ready SVG files (ink #000000, accent #FF5678, shade #CF536D), so they were downloaded from the site's file store unchanged into `src/forge/data/illustrations/open-doodles/` (2.1 MB, with LICENSE.txt, added to the package data) after a check for scripts and outside links (none). `find_image` lists them for a kind of illustration or any, by what each picture shows (a keyword map; no match returns nothing, so a technical query gets no doodle), and `fetch_image` copies one with `accent` and `ink` recoloured to the project's colours and records CC0 in NOTICES.md. The skill limits them to friendly, playful or educational brands. Open Peeps and Humaaans (also CC0) are Figma, Sketch or Illustrator kits without a plain SVG download that Forge can fetch, so they were left out; the user can download pieces by hand into `brand-assets/` (D-423). Other CC0 sets can be added the same way when one with distinctive, ready SVG files is found.

### D-430 - Candidate designs are shown to the user when the look is open (user chose option B, 2026-10-15)
Options discussed: (A) always ask, (B) ask only when the brief leaves the look open, (C) a project setting. The user chose B and added that DebCraft may ask for confirmation to display designs from time to time when required. Built: `OptionSpec.image` (a picture path inside the project) so an `ask_user` option can carry a picture; the question card shows it through the existing narrow `/api/image` route (images only, inside the workspace, never a secret file), in the card and in the pop-up; the result of `design_candidates` ends with a note that tells the model to call `ask_user` once, one option per candidate with its specimen as the image and the critic's winner as `recommended`, before importing the winner; the skill (section 0e) says when to ask (the look is open) and when not (a DESIGN.md, brand guide or sites supplied, the style named in the brief, the user said not to ask) and to ask again after a rejection. Whether the look is open is the model's judgement, as the user wanted, not a hard gate. A headless run answers a question with its recommended option (`engine/headless.py`), so benchmarks and campaigns are unchanged. The terminal client prints the options without the picture. Not built: a project setting (C), and pictures in the answered-question summary.

### D-431 - Several screenshot widths in one call (X6, 2026-10-15)
`browser_screenshot` gained `widths` (up to four, e.g. [1280, 375]). Options: (a) shoot them one after another in the same page (no gain); (b) separate pages opened at the same time in the one browser context (chosen); (c) separate browser contexts (loses shared cookies). The session now creates one explicit browser context, so the extra pages share cookies and local storage; each page loads the current address fresh, so a menu the model opened or text it typed is not in the picture, which the argument description says (use `width` for that). Each width has its own file (`shot-...-w<width>.png`), its own audit and its own screenshot notice; a width that fails is reported and the others still return. Saves one model turn and one tool call per width; the design critic's first step uses it. The browser tools stay limited to the local machine.

### D-432 - Three card-free sections added to the library (L12, first batch, 2026-10-15)
After the card-density check (D-425) the catalogue needed more card-free and distinctive building blocks. Authored and tested to the L0 acceptance bar (Vite + Tailwind v4, strict TypeScript, tokens only, audit clean at 1280 and 375 px on a page of the section alone, screenshots looked at, licence "original", catalogue entry and preview): `HeroEditorial` (an oversized headline, a tall picture pushed right, a ruled facts strip; asymmetric, not a split or a centred column), `FeaturesRuled` (a ruled list with a large numeral, a title, a sentence and a label per row, instead of three cards), `GalleryMosaic` (six captioned tiles of different sizes filling a 4 by 3 grid, a caption strip readable on every tone; real photographs through `src`). Things found while building: the audit's h1-lines count was wrong for a grid item that stretches to its row (fixed in the section with `self-start`), a caption on a partly transparent strip fails the contrast check because it is measured against the tile (the strip is solid), and a six-tile pattern must fill the grid or leaves a hole. `tests/test_sections.py` builds each of the three alone, in addition to the gallery of all sections; the gallery now allows the many-sizes finding, as it already allowed the many-colours one. The skill names them in the box-density bullet. Open: more batches (a card-free pricing, a people strip, a map and hours band) when the benchmark shows the sameness persists.

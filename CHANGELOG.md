# Changelog

Newest first. Decision numbers (D-nnn) refer to docs/DECISIONS.md.

## Unreleased — web UI redesign (2026-10-03 / 2026-10-04)
- **Login and landing (D-184, D-197):** a local account (user ID + password kept as a salted scrypt hash in
  `<forge home>\account.json`; "forgot password" = delete the file), a home screen (new project / open an existing
  one), a project list with each project's last request and what Forge remembers (handoff goal and next step, note count,
  FORGE.md; D-196), and an account screen to change the password. Every request but the page shell needs a signed-in session.
- **New look (D-185, docs/DESIGN.md):** one blue accent, white and parchment surfaces with near-black tiles, Inter,
  pill buttons; green only for success. `python -m forge ...` works like `forge ...`.
- **Setup (D-186, D-204):** the first run shows **where the `.env` file is**, a copyable template built from Forge's own
  settings and which names are filled in (never a value; "this page cannot see your keys"). Keys are never typed into the
  app and no endpoint can write the file. The **Environment drawer** (right side, also on New project) tests the system,
  Azure OpenAI, the **Forge database** (`LOCAL_PG_URL`) and the **read-only Development database** (`DEV_PG_URL`) one at a
  time or all at once (Connected / Failed with the reason), and proposes the model for each role, which the user confirms
  and Forge remembers (D-186). Tesseract and Gemini are asked about first and tested only after a yes (D-201).
- **Chat (D-188, D-189, D-190, D-191, D-192):** a welcome with starter prompts, a conversation layout (your message a soft
  pill, Forge's reply as plain text), tool calls as quiet lines with IN / OUT blocks, edits as inline diffs, runs of
  read/search calls folded, narration between calls, failures open by themselves, subagent steps nested in their row,
  Forge's todo list above the message box, a floating pill composer.
- **Full tool output (D-195):** long results are saved (redacted, capped at 200 MB per workspace, D-199) and shown on request.
- **Run map (D-193), Contracts panel (D-194):** the Run map's tests are rewritten for the live-growing graph and show what
  each helper agent cost (`agent_finished` now carries `cost_usd`); Standalone projects get a Contracts tab to pin, revise and
  forget interface contracts. The empty Learning tab is gone and the "/" suggestions match the real commands (D-198).
- **OCR (D-203):** a read-only `ocr_image` tool reads exact text from images and PDFs with Tesseract, on this computer; it
  is offered only after a yes on the drawer and a passing test.
- **Safety (D-187, D-202):** a read of Forge's `.env` by variable or inside a quoted string always asks; commands the model
  runs no longer inherit Forge's own variables (the names in `.env`, `FORGE_ENV_FILE`, `FORGE_HOME`, the provider settings).
- **Other fixes:** FORGE.md is no longer listed as a memory note (D-199); a Run-map node added later could stay hidden under load;
  the browser-test servers take a free port from the OS.

## Unreleased — revamp: Forge behaves like Claude Code (2026-10-02)
- **Run log (D-151):** every model call writes an `llm_call` event (latency, time to first token, tokens, tool
  calls) to `.forge/transcripts/events.jsonl`; `forge log-summary --workspace <dir>` prints where the time went.
- **Modules (D-152, D-154):** tiered modules with enforced import boundaries and a `MODULE.md` each
  (docs/MODULES.md). `agent` is split into `agent`, `subagents` and `workflow`; new `toolkit` and `protocol`.
- **A chat message answers open approval cards (D-153):** typing while a card is open declines it with your
  message as the instruction, so Forge no longer looks deaf. `forge --version` and `forge doctor` show a build id.
- **No stuck detector, no escalation ladder (D-155):** the model improvises failure recovery.
- **Direction (D-156, docs done, code staged):** verification, memory/learning and repo knowledge replicate
  Claude Code (shell checks, FORGE.md + auto-memory + skills, on-demand search).
- **Tests:** `pytest-xdist` added for dev; `pytest -n 12 --dist loadfile` runs the whole suite (about 45 s
  after D-182's test speed-up). The browser tests no longer stop at the first-run setup screen.
- **`learning` retired, auto-memory added (D-158):** no more library cards, lessons, retro or proposals; the model
  saves typed memories (user and project scope) with `memory_write`, shown in an index pinned every session.
- **Verification ladders retired (D-159):** the model runs tests, linters and builds itself through the shell; the
  `verify` and `run_tests` tools, the ladders, the test guard and the export smoke check are gone. Mode B still
  loads its host stand-ins for any pytest run.
- **Knowledge base retired (D-160):** Forge reads the repository on demand with glob/grep/read and the explore
  subagent. The list of credential tables the database guard refuses to read is still computed (now in `db`).
  `/init` has the model explore the repo and write FORGE.md.
- **First Mode B end-to-end campaign (D-162..D-170, docs/E2E_CAMPAIGN_2026-10-03.md):** three projects built and
  enhanced; follow-ups now always reach the model, one conversation across tasks, work without a task list is
  delivered, UI work must be checked in a browser, new `verifier` subagent that writes and runs independent Playwright
  checks; no runtime budget cap.
- **Reasoning summaries and progress (D-174, D-179):** the model's reasoning summaries stream as dim lines and it
  narrates before tool calls; a running subagent's steps are relayed as `subagent_step` events (terminal today).
- **Codex-comparison gaps (D-175..D-180):** read-only `explore`/`reviewer` subagents run in parallel (cap 4);
  `pre_compact`/`post_compact` hooks; `todo_write` (the model's own todo list, survives compaction); `monitor`
  (wait on a background process for a pattern, exit or timeout); custom agents may set `max_steps` and
  `write_only_under`.
- **Settings permission rules (D-183):** `<home>/settings.json` `permissions.allow` / `deny` (`tool(pattern)`).
  Deny always wins; allow never lifts a block, the always-ask list or plan mode, and never covers chained commands.
- **Speed (D-182):** benchmark of three settings; no change to model or effort. **Tests:** the full suite now runs
  in about 45 s (test workspaces use a venv without pip; shorter stress test; pruned secrets scan).
- **Decisions awaiting the UI work:** subagent calls nested and collapsed (D-181); Claude Code layout for tool
  calls in the web chat (TODO).
- **Parked:** Gemini provider (D-150).

## 0.1.0 — 2026-09-26 … 2026-09-29
- 2026-09-29: flat-loop orchestrator replaces the phase pipeline (D-128..D-132); React and Angular support
  (Mode A) and from-scratch frontends (Mode B); guided first-run setup (D-146) and `run_forge.ps1` (D-147);
  retro/lesson approval no longer blocks the turn.
- 2026-09-28: milestones M0–M11 (workspace, tools, context management, knowledge base, orchestrator, database,
  verification, web UI, diagnose, Mode B, learning, Claude Code parity features, multimodal evals, hardening);
  React UI and Run map (D-114..D-127); Windows certificate store support (D-110).

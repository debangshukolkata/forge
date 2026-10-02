# Changelog

Newest first. Decision numbers (D-nnn) refer to docs/DECISIONS.md.

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
- **Tests:** `pytest-xdist` added for dev; `pytest -n 12 --dist loadfile` runs the whole suite in about 3.5
  minutes. The browser tests no longer stop at the first-run setup screen.
- **`learning` retired, auto-memory added (D-158):** no more library cards, lessons, retro or proposals; the model
  saves typed memories (user and project scope) with `memory_write`, shown in an index pinned every session.
- **Verification ladders retired (D-159):** the model runs tests, linters and builds itself through the shell; the
  `verify` and `run_tests` tools, the ladders, the test guard and the export smoke check are gone. Mode B still
  loads its host stand-ins for any pytest run.
- **Knowledge base retired (D-160):** Forge reads the repository on demand with glob/grep/read and the explore
  subagent. The list of credential tables the database guard refuses to read is still computed (now in `db`).
  `/init` has the model explore the repo and write FORGE.md.
- **Parked:** Gemini provider (D-150).

## 0.1.0 — 2026-09-26 … 2026-09-29
- 2026-09-29: flat-loop orchestrator replaces the phase pipeline (D-128..D-132); React and Angular support
  (Mode A) and from-scratch frontends (Mode B); guided first-run setup (D-146) and `run_forge.ps1` (D-147);
  retro/lesson approval no longer blocks the turn.
- 2026-09-28: milestones M0–M11 (workspace, tools, context management, knowledge base, orchestrator, database,
  verification, web UI, diagnose, Mode B, learning, Claude Code parity features, multimodal evals, hardening);
  React UI and Run map (D-114..D-127); Windows certificate store support (D-110).

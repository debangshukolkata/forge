# Spec — Gaps found in the Codex comparison (2026-10-03)

Source: high-level comparison with github.com/openai/codex (survey only, not run). Principle: keep the flat loop
(D-128, D-155); add only what improves accuracy or speed (D-161). Each item: problem → change → acceptance.
Status: **pending** — recorded in TODO.md; decisions go to DECISIONS.md when built.

## G1. Parallel subagents (verify first, then fix)
- **Problem:** Codex runs many agents at once. Forge's `spawn_subagent` is `read_only = True`, so the loop may already
  batch several calls in one turn (`agent/loop.py`, `asyncio.gather`); unverified. The verifier and debugger are not
  read-only and write under `tests/e2e/` or run commands, so two at once could collide.
- **Change:** (1) Test whether two `explore` calls in one turn really run concurrently. (2) Allow parallel only for
  read-only agents (`explore`, `reviewer`); run `verifier`/`debugger` one at a time. (3) A cap on concurrent
  subagents (config, default 4), one shared LLM rate-limit queue. (4) Keep "subagents cannot nest" (MODULE.md invariant).
  (5) Events carry a subagent id so the UI can show parallel runs.
- **Acceptance:** two explores finish in about the time of one (timing test with a real deployment, `live`); two
  verifiers are serialised; cap respected; no subagent has `spawn_subagent`; budget and redaction unchanged.

## G2. Compaction hooks
- **Problem:** Codex runs pre- and post-compact hooks. Forge has only `HooksConfig.post_edit`.
- **Change:** add `pre_compact` and `post_compact` command lists to `HooksConfig` (run in the workspace, sandboxed,
  like `post_edit`). A pre-compact hook's stdout (capped, redacted) is added to the summary input, e.g. "keep these
  facts". Hook failure never blocks compaction.
- **Acceptance:** unit test that hooks run once per compaction in order; failure logged, compaction proceeds;
  output is redacted; the tool-pair invariant in `context/compaction.py` still holds.

## G3. Compaction robustness (optional, measure first)
- **Problem:** Codex has model fallback for compaction and an image budget. Forge compaction is pure functions plus
  one summariser call.
- **Change:** (1) If the summariser call fails or exceeds the window, fall back to the emergency trim (check it exists
  for this path). (2) Count images in the budget and drop old screenshots first. Only if real runs show a need.
- **Acceptance:** injected summariser failure (MockTransport 5xx/overflow) still yields a valid, smaller message list.

## G4. Subagent roles as config
- **Problem:** Codex loads agent roles from files with their own settings. Forge custom agents (`<forge_home>/agents/`)
  carry prompt, tools and role only.
- **Change:** allow optional `max_steps`, `model role` and `write_only_under` per custom agent file; validate with
  pydantic; unknown tools rejected with a clear message. Writes still go through the jail (invariant 1).
- **Acceptance:** a custom agent with `max_steps: 5` stops at 5; a write outside its allowed folder is refused.

## G5. Task breakdown (decide, do not build yet)
- Codex has structured goal/plan tools. Forge has optional `propose_plan`/`update_plan`/`task_update`. Under D-155
  nothing is added. Revisit only if the e2e campaign shows large features losing track of steps.

## G6. Todo list tool (Claude Code TodoWrite style)
- **Problem:** Forge only has `propose_plan`/`update_plan`/`task_update`: structured, approval-bound, tied to
  verification. No lightweight list the model keeps for its own step-tracking.
- **Change:** one `todo_write` tool: the model sends the full list each time (items: text, status
  pending/in_progress/completed; at most one in_progress). No approval, no verification gate, `read_only = True`.
  Emits a typed event; the React UI shows it live and rebuilds it from the event list on reopen. Stored in session
  state only (not a user file). Prompt: use it for tasks of 3+ steps; keep it current.
- **Acceptance:** schema rejects two in_progress; event replay restores the list; list survives compaction (pinned
  context); a live test shows the model uses it on a multi-step request.

## G7. Monitor tool (wait on a background process)
- **Problem:** `start_background` / `read_background` only poll. To wait for "server ready" or "build finished" the
  model loops on `read_background`, costing steps and time.
- **Change:** one `monitor` tool: arguments = background process id, optional regex to wait for, timeout (default
  60 s, max 300 s). Returns when the pattern appears, the process exits, or the timeout hits, with the new output
  (capped, redacted). Reuses the existing background-process registry; no new process rights, runs inside the same
  sandbox.
- **Acceptance:** returns on pattern match, on exit (with exit code) and on timeout (process keeps running); output
  redacted; a dev-server start-and-wait test needs one call instead of a poll loop.

## Not copied (deliberately)
Codex's large orchestrator (thread manager, message board, forking history), remote compaction, voice, cloud tasks:
they conflict with the flat-loop direction or need infrastructure Forge does not have.

## Order
G1 (verify, 1 test) → G2 → G6 → G7 → G4 → G3 → G5. G1 and G2 are small; none touches the safety invariants.

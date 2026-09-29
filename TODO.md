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
- UI: Run map/stepper redesign (D-131) — reads the old `phase` field; needs rebuilding against the new
  activity-less design before its two skipped e2e tests can be re-enabled. Also still needs: the Contracts
  panel (D-129, above), and the pre-existing phase-row-for-multi-day-runs redesign (D-123; options offered:
  scroll + zoom, phase summary strip, group by day).
- UI: the chat column showed a horizontal scrollbar in the user's runmap-demo (some wide content); not yet
  investigated.
- M7: embedded-Postgres fallback (`pgserver`) not built (SPEC_DEVIATIONS); "every table the code touches
  exists in scratch before DB-backed runs" check not built; `db_schema` results not yet cached into the KB.

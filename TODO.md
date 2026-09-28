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
- [x] **M6** Orchestrator — phases, approvals, tasks, resume, restructure
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
- UI: redesign the Run map's phase row for large / multi-day runs — the user will redesign it (D-123; options
  offered: scroll + zoom, phase summary strip, group by day).
- UI: the chat column showed a horizontal scrollbar in the user's runmap-demo (some wide content); not yet
  investigated.
- M7: embedded-Postgres fallback (`pgserver`) not built (SPEC_DEVIATIONS); "every table the code touches
  exists in scratch before DB-backed runs" check not built; `db_schema` results not yet cached into the KB.

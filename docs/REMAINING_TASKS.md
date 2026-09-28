# Remaining tasks (scratchpad)

Started 2026-09-28 ~00:50 IST. Worked through top to bottom; each item is ticked when its tests pass.
Details of every choice go to docs/DECISIONS.md; open issues to TODO.md / RISKS.md / SPEC_DEVIATIONS.md.

## 1. M10B — Mode B (standalone): close it
- [x] Live acceptance 1+2 (harness passes; since D-109 the FIRST delivery also passes in the clean host copy)
      (rerun after the sandbox/.venv fix; evidence saved to test-artifacts/ on failure)
- [x] Live acceptance 3 (2026-09-28 07:50 run: revision 2 passes 13/13 in a fresh host copy; notes = exactly the 2 changed files): a wrong assumption fails a contract test in the host; the pasted
      failure produces a revision that passes; REVISION_NOTES lists only the changed files
- [x] Mode B jail (file/grep/shell outside the workspace rejected) and web-search term filter (offline tests)
- [x] Mark M10B done in TODO.md; full offline suites (3.13 and 3.14: 426 passed, 1 failed — the secret scan of test-artifacts/; fixed, and that test re-run green on both)

## 2. M10C — Learning & self-improvement
- [x] Requirement cards at EXPORT/DONE + library index/search (same repo/profile only); `library_read`
- [x] Plan cites related past requirements (explore/plan prompt + tool)
- [x] Lesson store (scopes repo/profile/global/user, evidence, confidence, usage), approval, retrieval into
      the pinned `lessons` slot at task start (top-k, ~800 tokens), hygiene (dedupe, redaction)
- [x] Metrics per task/run (metrics.jsonl), RETRO phase after EXPORT (retros/<id>.md, proposed lessons)
- [x] Improvement proposals (tiers 1–3) with patch validation in a sandbox copy; `/improve list|show|apply`
- [x] `/library`, `/lessons`, `/retro`, `/stats`, `/improve`; web screens (library, lessons, improvements)
- [x] Offline acceptance items (scopes, approved-only lessons, no self-writes, tier-3 sandbox validation)
- [x] Live acceptance: second live run's plan cites the first run's card (tests/test_live_learning.py — passed 2026-09-28, 28 min)

## 3. M10E — Claude Code parity (spec §13B)
- [x] FORGE.md instruction files (hierarchy), `/init`
- [x] @-mentions (@file, @file:10-80, @DBR-n, @REQ-n, images); pasted images / long text as attachments
- [x] `/effort`, per-message `think hard:`; `/style concise|explanatory|learning`
- [x] Skills (SKILL.md packs, only descriptions pinned), custom subagents (<forge_home>/agents/*.md)
- [x] Optional MCP client (stdio/HTTP servers from config)
- [x] Notebook tools (notebook_read / notebook_edit_cell)
- [x] Local git history inside the workspace (auto-commit per task)
- [x] `/bg`, `/rename`, `forge sessions list`, `/export-chat`

## 4. M10D — Multimodal & eval-driven development
- [x] Vision tools (image read/crop/describe via the vision role), PDF rendering
- [x] Eval-set format, synthetic sample generator, labelling helper page
- [x] Metrics (IoU, field match), eval runner with overlays, LLM judge, eval-driven loop + target-miss discussion
- [x] Sensitive-sample rules; Evals + labelling web screens
- [x] Deterministic gate: unit tests for all of the above (tests/test_vision.py 8 pass; live view_image passes)

## 5. M11 — Hardening & packaging
- [x] Redaction, PowerShell-classifier and prompt-injection test fixtures (tests/test_hardening.py 100+ cases; live injection passes)
- [x] cp313 wheelhouse build script (offline install on the office laptop) + install/run guide (verified: 66 wheels, offline install, forge.cmd)
- [x] evals/ folder: 6 fixture tasks with hidden acceptance tests + scripts/run_fixture_evals.py — live: 6/6 hidden tests pass, full suite green 6/6
- [x] Carried-over items: embedded-Postgres fallback → documented deviation (no cp313 wheel); web search as
      stuck-escalation step 3 (built); app smoke in Diagnose (built, in-process)
- [x] "tables exist in scratch before DB-backed runs" check (D-107: reported before each test run; schema-qualified writes on the shared DB refused)

## 6. After development: the user's end-to-end check
- [x] Run Forge (new-project workspace, Mode A on an empty repo) and ask it to build a Python **multimodal RAG chatbot** using **FAISS**
      for the embeddings index (Azure OpenAI embeddings + vision from Forge's .env)
- [x] Then ask it to use that chatbot to **extract the signature** from
      `C:\Work\Projects\Handwritten Prescription.jpg`
- [x] Review the code Forge wrote (structure, correctness, tests) and report honestly what worked and what didn't (D-106)

## Notes
- The prescription image is personal health data: it is only sent to the user's own Azure OpenAI deployment
  (as the user asked), never to web search, and the generated app keeps no copy outside its workspace.
- If a model token/rate limit stops work, retry later (the user said 05:20 IST is fine).

## 7. Follow-ups after the overnight run (2026-09-28, daytime)
- [x] Full offline suite baseline (3.13): 427 passed
- [x] Tables-exist-in-scratch check (D-107)
- [x] Reviewer: evidence-checked findings, at most 5 blocking (D-108) — live: 2/2 fixture evals pass
- [x] Mode B: tests using host setup must request a host fixture (D-109) — live: first delivery passes in host
- [ ] Chatbot change request 4 (vision probe bug, tighter signature crop) — running
- [ ] Final offline suites on 3.13 and 3.14, then commit and push

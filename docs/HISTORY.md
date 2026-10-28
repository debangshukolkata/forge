# History of build sessions

Merged from four one-off session logs (2026-09-28 run, first Mode B campaign, two overnight runs). Background only; open work is in ../TODO.md.

---

## Overnight run 2026-09-28 (remaining-tasks checklist)


> **History only (2026-10-15).** This was the working list of the 2026-09-28 overnight run. All open work lives in `TODO.md`; do not add tasks here.

Started 2026-09-28 ~00:50 IST. Worked through top to bottom; each item is ticked when its tests pass.
Details of every choice go to docs/DECISIONS.md; open issues to TODO.md / RISKS.md / SPEC_DEVIATIONS.md.

### 1. M10B — Mode B (standalone): close it
- [x] Live acceptance 1+2 (harness passes; since D-109 the FIRST delivery also passes in the clean host copy)
      (rerun after the sandbox/.venv fix; evidence saved to test-artifacts/ on failure)
- [x] Live acceptance 3 (2026-09-28 07:50 run: revision 2 passes 13/13 in a fresh host copy; notes = exactly the 2 changed files): a wrong assumption fails a contract test in the host; the pasted
      failure produces a revision that passes; REVISION_NOTES lists only the changed files
- [x] Mode B jail (file/grep/shell outside the workspace rejected) and web-search term filter (offline tests)
- [x] Mark M10B done in TODO.md; full offline suites (3.13 and 3.14: 426 passed, 1 failed — the secret scan of test-artifacts/; fixed, and that test re-run green on both)

### 2. M10C — Learning & self-improvement
- [x] Requirement cards at EXPORT/DONE + library index/search (same repo/profile only); `library_read`
- [x] Plan cites related past requirements (explore/plan prompt + tool)
- [x] Lesson store (scopes repo/profile/global/user, evidence, confidence, usage), approval, retrieval into
      the pinned `lessons` slot at task start (top-k, ~800 tokens), hygiene (dedupe, redaction)
- [x] Metrics per task/run (metrics.jsonl), RETRO phase after EXPORT (retros/<id>.md, proposed lessons)
- [x] Improvement proposals (tiers 1–3) with patch validation in a sandbox copy; `/improve list|show|apply`
- [x] `/library`, `/lessons`, `/retro`, `/stats`, `/improve`; web screens (library, lessons, improvements)
- [x] Offline acceptance items (scopes, approved-only lessons, no self-writes, tier-3 sandbox validation)
- [x] Live acceptance: second live run's plan cites the first run's card (tests/test_live_learning.py — passed 2026-09-28, 28 min)

### 3. M10E — Claude Code parity (spec §13B)
- [x] FORGE.md instruction files (hierarchy), `/init`
- [x] @-mentions (@file, @file:10-80, @DBR-n, @REQ-n, images); pasted images / long text as attachments
- [x] `/effort`, per-message `think hard:`; `/style concise|explanatory|learning`
- [x] Skills (SKILL.md packs, only descriptions pinned), custom subagents (<forge_home>/agents/*.md)
- [x] Optional MCP client (stdio/HTTP servers from config)
- [x] Notebook tools (notebook_read / notebook_edit_cell)
- [x] Local git history inside the workspace (auto-commit per task)
- [x] `/bg`, `/rename`, `forge sessions list`, `/export-chat`

### 4. M10D — Multimodal & eval-driven development
- [x] Vision tools (image read/crop/describe via the vision role), PDF rendering
- [x] Eval-set format, synthetic sample generator, labelling helper page
- [x] Metrics (IoU, field match), eval runner with overlays, LLM judge, eval-driven loop + target-miss discussion
- [x] Sensitive-sample rules; Evals + labelling web screens
- [x] Deterministic gate: unit tests for all of the above (tests/test_vision.py 8 pass; live view_image passes)

### 5. M11 — Hardening & packaging
- [x] Redaction, PowerShell-classifier and prompt-injection test fixtures (tests/test_hardening.py 100+ cases; live injection passes)
- [x] cp313 wheelhouse build script (offline install on the office laptop) + install/run guide (verified: 66 wheels, offline install, forge.cmd)
- [x] evals/ folder: 6 fixture tasks with hidden acceptance tests + scripts/run_fixture_evals.py — live: 6/6 hidden tests pass, full suite green 6/6
- [x] Carried-over items: embedded-Postgres fallback → documented deviation (no cp313 wheel); web search as
      stuck-escalation step 3 (built); app smoke in Diagnose (built, in-process)
- [x] "tables exist in scratch before DB-backed runs" check (D-107: reported before each test run; schema-qualified writes on the shared DB refused)

### 6. After development: the user's end-to-end check
- [x] Run DebCraft (new-project workspace, Mode A on an empty repo) and ask it to build a Python **multimodal RAG chatbot** using **FAISS**
      for the embeddings index (Azure OpenAI embeddings + vision from DebCraft's .env)
- [x] Then ask it to use that chatbot to **extract the signature** from
      `C:\Work\Projects\Handwritten Prescription.jpg`
- [x] Review the code DebCraft wrote (structure, correctness, tests) and report honestly what worked and what didn't (D-106)

### Notes
- The prescription image is personal health data: it is only sent to the user's own Azure OpenAI deployment
  (as the user asked), never to web search, and the generated app keeps no copy outside its workspace.
- If a model token/rate limit stops work, retry later (the user said 05:20 IST is fine).

### 7. Follow-ups after the overnight run (2026-09-28, daytime)
- [x] Full offline suite baseline (3.13): 427 passed
- [x] Tables-exist-in-scratch check (D-107)
- [x] Reviewer: evidence-checked findings, at most 5 blocking (D-108) — live: 2/2 fixture evals pass
- [x] Mode B: tests using host setup must request a host fixture (D-109) — live: first delivery passes in host
- [x] Chatbot change requests 4–5: vision probe bug FIXED (works on the real deployment); signature crop NOT improved on the real photo (still 406,907–600,1045: scribble + printed caption, handwritten number missed) although DebCraft's new synthetic tests pass — synthetic samples didn't transfer to the real photo
- [x] Final offline suites on 3.13 and 3.14 (432 passed each), committed and pushed (a3c6819)

---

## First Mode B end-to-end campaign 2026-10-03


Goal: run DebCraft for real on three different projects, give each several enhancements and feedback, check the results
with independent Playwright scripts, and fix DebCraft wherever it fell short. Everything ran on the build machine, in
Mode B (standalone), with the Azure models, in an isolated DebCraft home (`C:\Work\ForgeRuns\home`) so the real profiles and
memory were untouched. Scripts and prompts are in `scripts/campaign/` (see its README).

### Result

| Project | Capability tested | Rounds | Independent check at the end |
|---|---|---|---|
| Employee attendance system (Flask, SQLite) | forms, state rules, CSV export, charts without libraries, calendar, dark mode | build + 6 enhancements + 3 feedback | 62 / 62 |
| Bakery website (Flask, JS, i18n) | responsive layout, client-side filtering, validation, capacity rules, cart, English/Hindi switch, dark mode | build + 3 enhancements + 3 feedback | 58 / 58 |
| Invoice extraction tool (rule-based parsing) | messy text and PDF input, date/amount normalisation, duplicates, corrections, CSV/JSON | build + 1 enhancement + 2 feedback | 26 / 26 |

Offline test suite at the end: 485 passed, 2 skipped on purpose. DebCraft's own request/response logs are in each
workspace's `.forge/transcripts/events.jsonl`; `forge log-summary --workspace <dir>` reads them.

### What was wrong in DebCraft, and what changed

Found by the run log and the independent checks, in the order they showed up. Each has a decision record.

| # | Problem | Fix |
|---|---|---|
| D-162 | The conversation was wiped at every task boundary, so the model re-read the same files after each task; the "already briefed" check never matched and re-sent the brief with every message | one conversation across tasks; brief sent once |
| D-163 | **A follow-up message after delivery never reached the model** (re-exported and printed "Done"); a plain answer was followed by a pointless "call task_update" nudge; a bad `cwd` switched the sandbox off | the model always runs on a new message; no nudge; a missing folder is an error |
| D-164 | `cwd="project"` (which the model keeps writing) failed; a blocked task could not be marked done after the fix | `project` means the project root; any task can be updated |
| D-165 | A follow-up was buried in a long system brief; the model answered an older request and claimed the new features existed. The restructure brief never contained the user's instruction | a follow-up arrives as the user's own message; the restructure brief carries the instruction |
| D-166 | A project built without a task list was never delivered (`output/` empty) | work is settled when no task is open and files changed |
| D-167 / D-169 | DebCraft reported UI features done that were not there (no "Add to cart" button; CSV export missing) because it only ran unit tests and never opened the app | `task_update(done)` is refused after UI edits without a browser check; if the turn ends after UI edits without one, the model is sent back once; skill `web-ui-verification` |
| D-168 / D-170 | DebCraft could not write and run independent checks itself | built-in **verifier** subagent: derives acceptance checks from the requirement, writes and runs Playwright/test scripts under `tests/e2e/`, checks static errors, tests, server log, browser console/network, screenshots and stored data, reports PASS/FAIL per check; step budget 90, final report forced when it runs out, no invented wording, scripts must not break the project's `pytest` |
| D-161 | Cost-saving defaults at runtime (a $20 budget cap, summariser at low effort) | no budget cap, summariser at normal effort; rule: accuracy and speed over cost for DebCraft, token savings only while building DebCraft with Claude Code |

### What DebCraft did well

- Built all three projects from a plain-language requirement; the first attempt of most enhancements passed every check.
- Acted on feedback: given the failing output and the expected values it fixed the parser (invoice numbers with `/`, totals,
  currency); given a one-line layout complaint it fixed the CSS.
- Once the rules above were in place it verified its own UI work in a real browser (started the app, six clicks, five
  screenshots, looked at four of them) without being told how.
- The verifier found a bug the independent scripts missed (an order without a name showed no message at all); DebCraft then
  found the root cause itself (native `required` validation was blocking the page's own handler) and fixed it.

### Still open

- Unattended runs cannot install packages (`pip install` is always-ask by design); the campaign driver approves pip
  installs into the workspace environment only. Interactive use is unaffected.
- The verifier is offered to the main agent by prompt and by the refusal text; DebCraft judged the dark-mode work simple
  enough to check directly and did not call it. A larger feature is the case to watch.
- A long network outage ended a run with a connection error after retries and the fallback model; DebCraft's retry and
  resume held up, but a half-finished enhancement had to be re-sent.
- The verifier's e2e suite is delivered under `tests/e2e/`; the first one assumed a running server and Playwright (fixed in
  the prompt, not yet re-run end to end).
- Not touched: the web UI (timeline, Run map), the plugin system design, MCP/LSP, and the parked Gemini provider.

---

## Overnight run 2026-10-14


Nothing was pushed. All work is in local commits on `main` (last pushed: `a69f1fe`). Say "push" when you have looked.

### Done tonight (each with tests and a D-note)
| Item | Result |
|---|---|
| Merge `web-design`, one speed rerun | Merged (D-312, D-313). Speed-4, page redesign: 509 s, $0.62, 6/7 checks (speed-1 was 1487 s, $1.51) |
| Template imitation for tests | A 10-slide infographic-style test template (dark/light twins, sticky "Delete before using" note, shape-drawn infographic); DebCraft removes the notes, picks matching dark/light samples, fits text, fills picture frames (D-334, D-335) |
| P2.24 | `describe_design`: reads the design of any deck (D-336) |
| P2.25 | `analyze_reference_image` / `compare_to_reference`: a design shown as a picture is measured and scored (D-337). Skill now says: judge essence over an exact copy, and say plainly what was kept or changed |
| P2.19 | `read_source_document`: Word, Excel, CSV, PDF into a digest for a deck (D-338) |
| W0 | `docs/DOCUMENTS_CLEAN_ROOM.md` |
| W2 | Excel: `build_workbook`, `read_workbook`, `edit_workbook`, `check_workbook`, skill `make-spreadsheet`; Excel recalculation checked live on this machine (D-339) |
| W1 | Word: `build_document`, `read_document`, `edit_document`, `check_document`, skill `make-document`; opens in Word, fields update (D-342) |
| S6 (part) | npm uses its cache, no audit/fund calls (D-340) |
| C17 | "Run report" download button in the Files panel (D-341) |

### For you in the morning
1. `git push` (say "push").
2. On the office laptop, pull and run: `scripts/dev/reach_smoke.py`, `scripts/dev/template_look.py`, `forge template-probe <your template>` (see `docs/TEMPLATE_PROBE.md`); send the report back.
3. Send reference pictures of designs you want matched (P2.25) and a few sample Word/Excel/PDF files.
4. Still owed from before: S7 deployment name, the three-design web task rerun, the `npx shadcn` test, optional Pexels/Unsplash/Pixabay keys.

### Not done / open
- Word extras (preview pictures, footnotes, tracked changes), PDF (W3), shared pieces (W4), document benchmark (W5); Excel: messy-CSV cleaning and modelling-convention checks.
- S6: audit only changed pages; sandbox start-up measure.
- Nothing has been verified on your real company template yet: only on the test template.

---

## Overnight run 2026-10-15


Written for the person who owns DebCraft, not for a programmer. Everything below is pushed to `main` (the last push was `46a16a5`; later local commits are listed in `git log`). The list of work was TODO.md section 0c;
every decision has a number in docs/DECISIONS.md (D-362 to D-430).

### What to do next (about 30 minutes, then the A/B when you have an hour free)

1. **Update the laptop:** `git pull` in `C:\Work\LocalDevelopment\forge-main` (or copy the folder over), then double-click `Start-DebCraft.cmd`. It now runs the doctor first (one line per check, saved in `doctor-report.txt`).
2. **Check the `.env`** (`C:\Users\211258\.forge\.env`): the second Azure resource needs `AZURE_FALLBACK_ENDPOINT`, `AZURE_FALLBACK_API_KEY`, `AZURE_FALLBACK_API_VERSION`, `AZURE_FALLBACK_DEPLOYMENT`, `AZURE_STRONG_DEPLOYMENT="aicloud-gpt-5.4"` and `AZURE_GPT52_DEPLOYMENT="aicloud-gpt-5.2"`. You did this; the doctor showed all models OK.
3. **Environment panel:** answer Yes to Gemini, press **Test all** (the model lists stay locked until every test has finished), look at the proposals and press **Save models**. The proposals are: coder gpt-5.1, knowledge builder, summariser and vision gpt-5.1; planner, design critic, judge and reviewer Gemini 4 Argon (else Gemini 3.1 Pro, else gpt-5.2); fallback Gemini 3.1 Pro (else gpt-5.4, gpt-5.2). Rows you change by hand are remembered; the others follow later proposals.
4. **The Gemini A/B** (docs/LAPTOP_AB.md): two small briefs first, about 25 minutes. It tells whether Argon as critic and judge makes the pages better. Send me the two `results.md` files and say which pages you like more.

### What was built and measured

| Area | Result |
|---|---|
| **Speed** | Parallel design builders (`build_variants`): three throwaway designs 46 percent faster and 18 percent cheaper than one after the other (D-380). Where time goes was measured: subagents are 34 percent of the wall time. |
| **Benchmarks** | Design: all four briefs complete on the final code with 0 or 1 audit findings (docs/DESIGN_BENCHMARK.md); a bug found on the way (the audit judged a stale page) is fixed (D-391). Coding: 13 of 14 tasks, 309 of 310 tests, no regression; gpt-5.4 as coder gave the same results, 39 percent slower and 2.9 times the cost (D-414). Approach challenges: ten, three rounds (docs/CODE_BENCHMARK.md). |
| **Design material** | 24 application screens, each also as React; 7 page compositions, also as React; 40 small animations, 5 React effects, 3 canvas effects; shop, conference, docs and pricing templates with pictures; a picture for every section and direction; font pairings with Bengali and Hindi pictures; the gallery `docs/DESIGN_GALLERY.md`. |
| **Documents and decks** | True PDF redaction; PDFs in Bengali, Devanagari and other scripts; company look saved with the project (`brand.json`), logo in Word, PDF and decks; six font pairings; 670 real decks from open repositories swept through the readers (one defect fixed, D-399). |
| **Models** | Gemini 3 models and Gemini 4 Argon answer on your project from the `global` region (the earlier failure was a certificate error plus the wrong region). New roles: design critic and planner. The "independent" design critic had been running on the builder's own model; now it is a separate role (D-409). A rate limit or outage falls back to a model of another provider (D-411). gpt-5.2 added (D-413). |
| **shadcn and certificates** | `shadcn_setup` does the whole setup (Tailwind, alias, init, components) and was run against the real network; a certificate failure is recovered by exporting the Windows certificates for Node (D-401, D-402). Verified on your laptop. |
| **Environment panel and start-up** | Models list every model with its state; the lists unlock only after a full test (D-415); saved choices no longer freeze old proposals (D-416); a Node row; the doctor runs at every start; `Debcraft-Doctor.cmd`. |
| **Everyday tools** | `scripts/dev/quick_check.py` (lint plus only the tests that touch what changed), `--mini` design briefs, `night_status.py`, the skill A/B loop `run_skill_ab.py` (D-417), the reference-deck sweep. |

### Gates added (for your review): each is one reminder, never a trap, only in real sessions

1. Before the first edit of existing code the tests must have run (or a test been written): refused once, with the reason (D-408).
2. Replacing most of an existing file of 30 lines or more in one write is refused once until a test has been written (D-410).
3. Before a turn ends, the loop asks once for the risks found in the files it read (unsafe loading, committed secrets, SQL built from strings, shell commands from strings, eval, certificate checks off) if the reply does not name them (D-410).
4. `design_candidates` refuses a composition that is not a catalogue id (D-406).
5. A control character in a file write is refused with the place and the fix (D-379).

### Later the same day: the Design Intelligence Engine (D-415 to D-429)

| Item | What it is now |
|---|---|
| Pages that looked machine-made (D-419) | The audit finds controls in the browser font, text running together, uneven cards, grooved fieldsets, and a booking page with no pictures; recipes fixed. |
| DIE1 discovery (D-422) | `design_inspire` also measures the type scale and the sections; each page gets a reference note (principles to reuse, the brand's own not to copy); the design skill starts with a look at the field for brand pages. Not proven to help yet. |
| DIE2 blueprint (D-421) | `design_md_lint` notes missing Page Composition, Imagery, Motion, Responsive and Accessibility sections and decisions with no reason; the template and the drafts carry the sections. |
| DIE3 knowledge base (D-426) | `design_kb_add`, `design_kb_search`; references and the last designs' palette, fonts and composition live in your profile folder. |
| DIE4 art director (D-427) | A read-only subagent on the planner role returns a complete DESIGN.md; it is one of the design candidates. |
| DIE5 gate (D-425, D-428) | Card density in the audit; a note when a design resembles one of the last five. |
| DIE6 imagery (D-423, D-429) | Your `brand-assets` folder first; the bundled CC0 Open Doodles recoloured to the accent; unDraw only as files you download by hand (D-420). |
| DIE8 taste test (D-424) | Runbook docs/DESIGN_TASTE_TEST.md: Argon against gpt-5.1 in three arms, a blind gallery. Waits for the office laptop. |
| Candidates shown to you (D-430) | When the look is open, DebCraft asks which candidate design you want, with each specimen picture in the question card. Skipped when you supplied a DESIGN.md or brand guide, the brief names the style, or you said not to ask. |
| Live check (DIE9) | Two `--mini` briefs on the new code: both delivered, 0 audit findings. The model ignored the knowledge base, art director and candidate question at first; the steps were then moved into the system prompt and tool results and re-checked (`live-check-2`). |

### What is still open

- **Measuring Gemini on your laptop** (docs/LAPTOP_AB.md): Argon as critic and judge, and as planner. This machine has no Google credentials. Nothing about Gemini inside a long agent session has been verified, only short calls.
- **Prices in the config** for Gemini and gpt-5.2/5.4 are placeholders; replace them with your contract prices for correct cost numbers.
- **The skill A/B** (C14) is built; its first measurements (for example `test-first` on the four hard coding tasks) are cheap and not run yet.
- **A real company template** would still test the template mode better than 670 public test decks; only if you want it.
- **Not built on purpose:** best-of-N design candidates (no run-to-run variance seen), per-task routing between gpt-5.1 and gpt-5.4 (loses the cache and the reasoning thread; the benchmark gave no reason), a built hero per candidate, the ask-me-first setting, a logo for workbooks.

### Mistakes worth knowing

- I stopped every Python process once (it killed your `forge ui` on port 8765). I stop only the processes I started now.
- The first design benchmark judged stale pages (fixed, D-391) and was rerun.
- The gpt-5.4 benchmark first failed in seconds because the deployment name was not passed in; fixed and rerun.

## Overnight run 2026-10-29 (D-525 to D-537)

Agreed before the night: Azure spend up to about $40, local commits only (nothing pushed), a bug found by a live check is fixed and re-checked. Plan: TODO.md section 0f. Spent: about $24 (estimate from the run reports).

### What was built and measured
- **Workbooks (W6, W7; D-525, D-532).** The "wrong series" charts were builder faults: no `varyColors` (Excel then colours each point and lists the months as series) and row-shaped data read as columns. New `sheets/charts.py`: series along rows or columns from the ranges, one colour per series, straight lines, charts moved off each other, every sheet printed one page wide. `edit_workbook` no longer refuses a workbook with charts (openpyxl 3.1 keeps them; the old refusal made the model set `allow_loss` without asking). `check_workbook` now finds chart faults however the file was made.
- **Word (W8; D-526, D-532).** `kind: "letter"`, table defaults (shaded header, right-aligned numbers, bold total, fitted widths), a `callout` block for the key figure. Two checker faults fixed (paragraphs either side of a table counted as empty spacing; a bold "Subject:" line taken for a fake heading).
- **Document benchmark doc-3:** where the builders were used, the named problems moved on (chart complaints of w02 and w14 gone, w07 page split gone, w11 5/5/5/5); w06 still failed because the model wrote its own openpyxl script after failing to write a long JSON outline. Table in docs/DOCUMENT_BENCHMARK.md.
- **"Three design options" (BV1; D-527).** The model answered in text with no tool at all; a per-request note now names `build_variants`: 0/3 before, 2/2 after.
- **Catalogue hint (RH1; D-528).** Back-end requests offered UI screens: 10 of 15 before, 1 of 15 after; UI requests unchanged.
- **C1b and coding tasks (D-529, D-531, D-536).** Why four coding tasks lost tests; the security recipe got a web section; new task t23 (a second security review). Rerun t15 to t23: 411/447 hidden tests. A security note helped little (t22 70 -> 76, t23 47 -> 46); the model never opens the security recipe (TODO SEC1).
- **Recipes (D-530).** The five never-run recipes run for real in a scratch venv; Flask and Django lacked imports between their files (fixed).
- **LT1 live checks (D-533, D-534).** MCP allow-list, stop hook, `code_outline`, forked skills, `--auto-approve --allow-installs` and the run report all work live. Fixed: an MCP server that dies on start now shows its stderr (it said only "Connection closed"); the run report no longer prints an empty "Totals:". Egress guard inconclusive live (the model never tried to send code).
- **C14 (D-535).** Skill triggers: 10 of 12 skills at 85 to 100 %; test-first (1/10) and verify-before-done (4/10) retuned to 7/10 and 10/10, others unchanged.
- **C16 (D-537).** Skill arms on three tasks: baseline 162/170, ours 167, Superpowers 168, mattpocock 166; ours cheapest of the three skill sets. One run each: a hint only.
- **Small:** flaky browser test polls (FL1), scroll-progress preview (PX1), WU1 and WU2 confirmed live.

### Tests
Non-browser suite 1995 passed, 3 skipped (network-only and bandit); ruff, ruff format, mypy (348 files) and check_secrets clean. Browser suite: see the end of this entry.

### What you may want to do
- Say "push" when you have read this (19+ local commits).
- Security-relevant changes for your review: the MCP client now writes each server's stderr to a temporary file and shows its last 600 characters in the error (it can contain whatever the server prints); the security note and recipe (advice only, no gate).
- Decide whether SEC1 (attach the security recipe automatically for security requests) is worth a third security task.

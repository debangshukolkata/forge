# First Mode B end-to-end campaign (2026-10-03)

Goal: run Forge for real on three different projects, give each several enhancements and feedback, check the results
with independent Playwright scripts, and fix Forge wherever it fell short. Everything ran on the build machine, in
Mode B (standalone), with the Azure models, in an isolated Forge home (`C:\Work\ForgeRuns\home`) so the real profiles and
memory were untouched. Scripts and prompts are in `scripts/campaign/` (see its README).

## Result

| Project | Capability tested | Rounds | Independent check at the end |
|---|---|---|---|
| Employee attendance system (Flask, SQLite) | forms, state rules, CSV export, charts without libraries, calendar, dark mode | build + 6 enhancements + 3 feedback | 62 / 62 |
| Bakery website (Flask, JS, i18n) | responsive layout, client-side filtering, validation, capacity rules, cart, English/Hindi switch, dark mode | build + 3 enhancements + 3 feedback | 58 / 58 |
| Invoice extraction tool (rule-based parsing) | messy text and PDF input, date/amount normalisation, duplicates, corrections, CSV/JSON | build + 1 enhancement + 2 feedback | 26 / 26 |

Offline test suite at the end: 485 passed, 2 skipped on purpose. Forge's own request/response logs are in each
workspace's `.forge/transcripts/events.jsonl`; `forge log-summary --workspace <dir>` reads them.

## What was wrong in Forge, and what changed

Found by the run log and the independent checks, in the order they showed up. Each has a decision record.

| # | Problem | Fix |
|---|---|---|
| D-162 | The conversation was wiped at every task boundary, so the model re-read the same files after each task; the "already briefed" check never matched and re-sent the brief with every message | one conversation across tasks; brief sent once |
| D-163 | **A follow-up message after delivery never reached the model** (re-exported and printed "Done"); a plain answer was followed by a pointless "call task_update" nudge; a bad `cwd` switched the sandbox off | the model always runs on a new message; no nudge; a missing folder is an error |
| D-164 | `cwd="project"` (which the model keeps writing) failed; a blocked task could not be marked done after the fix | `project` means the project root; any task can be updated |
| D-165 | A follow-up was buried in a long system brief; the model answered an older request and claimed the new features existed. The restructure brief never contained the user's instruction | a follow-up arrives as the user's own message; the restructure brief carries the instruction |
| D-166 | A project built without a task list was never delivered (`output/` empty) | work is settled when no task is open and files changed |
| D-167 / D-169 | Forge reported UI features done that were not there (no "Add to cart" button; CSV export missing) because it only ran unit tests and never opened the app | `task_update(done)` is refused after UI edits without a browser check; if the turn ends after UI edits without one, the model is sent back once; skill `web-ui-verification` |
| D-168 / D-170 | Forge could not write and run independent checks itself | built-in **verifier** subagent: derives acceptance checks from the requirement, writes and runs Playwright/test scripts under `tests/e2e/`, checks static errors, tests, server log, browser console/network, screenshots and stored data, reports PASS/FAIL per check; step budget 90, final report forced when it runs out, no invented wording, scripts must not break the project's `pytest` |
| D-161 | Cost-saving defaults at runtime (a $20 budget cap, summariser at low effort) | no budget cap, summariser at normal effort; rule: accuracy and speed over cost for Forge, token savings only while building Forge with Claude Code |

## What Forge did well

- Built all three projects from a plain-language requirement; the first attempt of most enhancements passed every check.
- Acted on feedback: given the failing output and the expected values it fixed the parser (invoice numbers with `/`, totals,
  currency); given a one-line layout complaint it fixed the CSS.
- Once the rules above were in place it verified its own UI work in a real browser (started the app, six clicks, five
  screenshots, looked at four of them) without being told how.
- The verifier found a bug the independent scripts missed (an order without a name showed no message at all); Forge then
  found the root cause itself (native `required` validation was blocking the page's own handler) and fixed it.

## Still open

- Unattended runs cannot install packages (`pip install` is always-ask by design); the campaign driver approves pip
  installs into the workspace environment only. Interactive use is unaffected.
- The verifier is offered to the main agent by prompt and by the refusal text; Forge judged the dark-mode work simple
  enough to check directly and did not call it. A larger feature is the case to watch.
- A long network outage ended a run with a connection error after retries and the fallback model; Forge's retry and
  resume held up, but a half-finished enhancement had to be re-sent.
- The verifier's e2e suite is delivered under `tests/e2e/`; the first one assumed a running server and Playwright (fixed in
  the prompt, not yet re-run end to end).
- Not touched: the web UI (timeline, Run map), the plugin system design, MCP/LSP, and the parked Gemini provider.

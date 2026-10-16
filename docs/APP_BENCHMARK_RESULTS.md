# Business-application benchmark: results (2026-10-16)

Method and reference designs: `docs/APP_BENCHMARK.md`. What was judged is the **planning layer** (the questions asked, the planner's report, REQUIREMENTS.md, PLAN.md, assumptions), because that is where DebCraft's understanding, decisions and scope show; each run is stopped when the first project file is written. Scoring is a regular-expression check of 21 reference scenarios per domain plus 10 "habits" of the solution-thinking skill (`scripts/dev/score_planning.py`): crude and repeatable, a direction and not a grade. One run per setting, so differences of two or three scenarios are noise.

## 1. What DebCraft did before the change (baseline, unchanged code)
- Its "understanding" restated the technology (stack, one-command start, README) and not the problem. Its "not asked" list removed things the brief's own complaints needed: public holidays, accrual and audit in HR; KYC and real banking rules in lending; stock control, returns and units in procure-to-pay.
- It opened every run with a question about the company's data-protection approval (answer changed nothing) and then a question about the look. No domain question was asked.
- Acceptance criteria were feature checks ("pytest passes", "pages render"), not outcomes tied to the problem. No states, no ways back (withdraw, send back, delegate), no scope ledger, tasks layer by layer (design, scaffold, routes, tests, verify).
- Reference scenarios found: HR 9/21, banking 7/21, supply chain 7/21 (habits 1 to 2 of 10). On the unseen fourth domain (plant maintenance): 8/21.

## 2. What was changed (D-455)
1. Planner prompt rewritten: objective and users with their pains and a pain-point trace; observable acceptance criteria; the decision with the reuse chosen; an expert pass; a scope ledger (Essential / High-value / Optional, what is left out and the risk); assumptions and only the questions that change the design; vertical-slice tasks; risks and edge cases. It loads the new `solution-thinking` skill for business applications.
2. Four rules in the system prompt: solve the problem behind the request; build what pays for itself and list the rest; ask only when the answer changes the design (never about the company's approvals); carry the planner's criteria and ledger into REQUIREMENTS.md and PLAN.md without shortening (found necessary: the first version dropped the planner's authority limits when writing the requirements).
3. `phases.md`: the data-protection question only when real data will be used.
4. `role_reasoning_effort: planner: high` in the default config.

## 3. Results (reference scenarios found, of 21 per domain)
| Run | HR | Banking | Supply chain | Total of 63 | Habits |
|---|---|---|---|---|---|
| Baseline (old code) | 9 | 7 | 7 | 23 | 1 to 2 / 10 |
| v2: new prompts and skill | 19 | 14 | 12 | 45 | 8 to 9 / 10 |
| v3: + pain-point trace, expert pass | 17 | 14 | 14 | 45 | 7 to 9 |
| v4: + structured expert pass | 16 | 12 | 14 | 42 | 6 to 7 |
| **v5: v2 text + planner at high effort** | 17 | 16 | 18 | **51** | 6 to 9 |

Reading: the large gain came with v2 (23 to 45). More wording (v3, v4) gave nothing measurable. Thinking harder in the planner (v5) added about 6 more scenarios, mostly in banking and supply chain, at the cost of a slower plan (4 to 15 minutes against 4 to 9). The planner runs once per large task, and accuracy comes before speed at runtime (D-161), so it is kept.

**Generalisation (fourth domain, plant maintenance, reference written before the runs):** old code 8/21, new code 18/21; the old run asked about the visual direction, the new run asked nothing.

## 4. What the planner now does well, and what is still missing
Does well: names each role with what hurts them today; states observable acceptance criteria; separates Essential, High-value and Optional and says what leaving out costs; finds the controls a reviewer would look for (self-approval, authority by amount, duplicate checks, tolerances, audit with before and after values); plans vertical slices; asks only about the visual direction.
Still missing in places: domain depth the model does not volunteer (lending: affordability, pricing, offer expiry, co-applicant, regulatory disclosures; supply chain: PO amendments, transfers between the two warehouses, negative stock; HR: pro-rata joiners, notice periods; plant: the asset register, contractors, handover). The planner sometimes shrinks its own analysis to "demo level" because the brief says fictional data.

## 5. Status of the open items
- Done after the first write-up: the verifier walks the plan's acceptance criteria as each role and the last task is gated on it (D-456; tests added). A full HR build with the new plan and the gate was started to see it work on a real model (section 7).
- Small tasks: checked, no added ceremony (section 6).
- Domain playbooks: not built, on purpose (D-456): a playbook for the same three domains as the reference lists would raise our own score without proving general value. Revisit when the user names the domains they build often, or when a stronger planner model on the office laptop still leaves a measured gap.
- The office laptop: the planner can run on a stronger model there (Gemini); not measured. The user's first large task there is the test.
- Whether the better plan makes a better finished application: section 7.

## 6. Small-task check (the log-analyser task of the overnight kit, hidden checks, gpt-5.4)
| | Old code | New code |
|---|---|---|
| Time | 525 s | 289 s |
| Hidden checks | 10 of 10 | 10 of 10 |
| Tool calls | 38 | 28 |
| Planner called / solution-thinking loaded | no / no | no / no |
| Questions | 0 | 1 (at the end: "one useful follow-up?", recommended "Stop here"; the existing follow-up offer) |

A small, clear task is handled directly, with no planner and no analysis, as intended: the proportionality rule works (one run each; the time difference is probably noise, but there is no sign of added ceremony). The final question is the existing offer of optional follow-ups, which fits the principle that optional ideas are listed and not silently built.

## 7. Full build with the new plan and the gate
Filled in when the run finishes.

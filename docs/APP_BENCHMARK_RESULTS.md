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

## 5. Not yet done
- Small tasks: a check that simple tasks are not slowed or loaded with ceremony (section 6).
- A "user" reviewer that walks the built application in a browser as each role and reports where the real user would be stuck; a gate that a large task cannot be marked done without its acceptance criteria checked (path C of D-454). Not built: the benchmark stops before building, so it could not be measured here.
- Domain playbooks: the results show the model knows the structure but not always the depth. Whether curated playbooks pay for themselves depends on which domains the user builds; not started.
- The office laptop: the planner can run on a stronger model there (Gemini); not measured.
- Full builds: whether the better plan produces a better application was not measured (the runs stop when building begins, on purpose).

## 6. Small-task check
Filled in when the run finishes.

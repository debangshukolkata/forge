# Study of obra/superpowers and mattpocock/skills (TODO C18, 2026-10-13)

Both repositories are MIT licensed. Rule for DebCraft: ideas and structure may be taken, the wording is always our own, and each
skill we write carries a one-line credit in its decision record (D-numbers below). Read on 2026-10-13 from the repositories' README
files and the skill files named here; neither publishes outcome data, so every adoption below is judged on our own benchmarks
(docs/CODE_BENCHMARK.md, docs/SPEED_BENCHMARK.md) and rejected when the score drops (D-161).

## What each repository is

**obra/superpowers** (about 298k stars): a methodology for coding agents made of 14 skills plus a "use the skills" bootstrap. Core flow:
brainstorm a design, isolate work in a git worktree, write a plan of 2-5 minute tasks, execute it with a fresh subagent per task and a
review after each, test first, systematic debugging, verify before saying done, finish the branch. Skills: test-driven-development,
systematic-debugging, verification-before-completion, diagnosing-superpowers, brainstorming, writing-plans, executing-plans,
dispatching-parallel-agents, requesting/receiving-code-review, using-git-worktrees, finishing-a-development-branch,
subagent-driven-development, writing-skills, using-superpowers.

**mattpocock/skills**: about 30 small skills for alignment and feedback loops. Engineering: grill-with-docs (interview about a plan
while building a glossary and decision records), to-spec, to-tickets (tracer-bullet tickets with blocking edges), implement,
implement-spec (a task graph run by parallel subagents on one integration branch), tdd, diagnosing-bugs, code-review (two axes),
codebase-design (deep modules), domain-modeling (glossary and ADRs), research, prototype, pr, wizard (a script for steps only a human
can do), triage, retro. Productivity: grill-me, handoff, teach, to-questionnaire, wait-what, writing-for-agents.

## The protocols we care about, in our own words

**Subagent-driven development (superpowers).**
- A controller never writes code. Per task a fresh implementer gets: one line of where the task fits, the path of a task brief file, the
  interface decisions from earlier tasks, the controller's rulings on any ambiguity, and the path where it writes its report. History of
  earlier tasks is not pasted in.
- The implementer ends with one of four statuses: done; done with concerns (the controller handles correctness or scope concerns before
  review); needs context (supply it and re-dispatch); blocked (add context, use a stronger model, split the task, or fix the plan: never
  retry unchanged). An implementer never starts reviewers.
- After each task a reviewer judges two things, spec compliance and code quality, from a diff file taken against a recorded base commit.
  A finding it cannot confirm from the diff must be resolved by the controller before the task counts.
- Fix loop at most five rounds: rounds 1-3 resume the same implementer, rounds 4-5 use a fresh one on a stronger model; every round ends
  with a re-review of only the fix. After round five the controller rules on each open finding (reviewer wrong or contestable: park with a
  ruling; real but nothing depends on it: defer; real and something depends on it: smallest unblocking ruling). Minor findings are
  logged, never looped on.
- A git-ignored ledger file records progress and rulings, because the conversation does not survive compaction. A pre-flight scan lists
  task pairs that share a file or interface before any task starts. Implementers never run in parallel in this skill.
- Models are chosen per role (cheap for mechanical tasks, strongest for architecture and the final whole-branch review) and always named
  explicitly.

**Parallel agents (superpowers).** Dispatch in parallel only for independent problems with no shared state and no shared cause; each
agent gets one scope, a concrete goal, the relevant errors pasted in, constraints on what it must not touch, and an output format. All
dispatches go out in one turn. Afterwards read every summary, check for edits to the same code, run the whole suite, spot-check.

**to-tickets and implement-spec (mattpocock).**
- A ticket is a thin vertical slice through every layer that can be verified on its own and fits one fresh context. It names the tickets
  that must finish first. Wide mechanical refactors are sequenced expand, migrate (in batches by blast radius), contract. The breakdown is
  shown to the user as a numbered list (title, blocked by, what it delivers) and agreed before anything runs.
- implement-spec reads the tickets as a graph, starts an implementer per ready ticket (the frontier) in its own worktree and branch, each
  merging the integration branch tip before it reports done so conflicts show early, then a merger folds finished work in, and the next
  ready tickets start. A whole-branch review runs at the end; one implementer fixes everything it finds. It defines no concurrency cap and
  no file-overlap detection: both are ours to add.

**code-review (mattpocock).** Two parallel reviewers on a diff from a fixed point: standards (documented repo rules plus a smell
baseline, tool-enforced rules skipped) and spec (missing requirements, unrequested behaviour, wrong implementation). Reports stay
separate so one axis cannot hide the other.

**tdd and systematic debugging (both).** Test first with a verified red; for bugs a failing test that reproduces it before the fix.
Debugging in four phases (investigate root cause, compare with working code, one hypothesis tested with the smallest change, then fix
with a test); after three failed fixes stop and question the design.

**codebase-design and domain-modeling (mattpocock).** Deep modules: much behaviour behind a small interface; the deletion test (delete the
module: does complexity vanish or spread to callers?); one adapter means a hypothetical seam, two a real one; tests cross the same
seam as callers. A glossary file grown inline as terms are resolved; a decision record only when a choice is hard to reverse,
surprising without context and a real trade-off.

## Decisions: what DebCraft takes

| Idea | Source | Decision | Goes into |
|---|---|---|---|
| Builder protocol: brief file in, report file out, four statuses, no blind retry | superpowers | **Take** (own words) | X2 |
| Two-verdict review (spec, quality) with a diff against a recorded base | both | **Take**; DebCraft's reviewer gets both axes | C4 |
| Fix loop of five with a stronger model late, scoped re-review, breaker rulings | superpowers | **Take**, as a cap of five rounds; the stronger model is the configured fallback | X2, C4 |
| Progress ledger file that survives compaction | superpowers | **Take** (a git-ignored file in `.forge/`) | X2 |
| Task graph with blocking edges, run the frontier in parallel | mattpocock | **Take**, conservative: disjoint write scopes, concurrency cap, queue approvals, fall back to sequential | X7 |
| Pre-flight scan for tasks that share a file or interface | superpowers | **Take**; this is our disjoint-scope check | X7 |
| Expand / migrate / contract for wide refactors | mattpocock | **Take** as a short rule in the planning skill | X7, C6 |
| Test first with a verified red; reproduce a bug with a failing test | both | **Take** as a nudge, not a hard rule (a hard rule hurt nothing on t01-t14 so far; measure) | C6 |
| Four-phase debugging, stop after three failed fixes | superpowers | **Take** | C7 |
| Verification before claiming done | superpowers | **Already ours** (task_update needs a passing test run, quality gates D-295, import check) | done |
| Deep-module checklist and deletion test | mattpocock | **Take** as a short design skill | C19 |
| "Design it twice" (two radically different interfaces compared) | mattpocock (summary only) | **Take** as an optional step for new modules; own text | C19 |
| Glossary and light decision records in built projects | mattpocock | **Take**, lazily created, only when the conditions hold | C20 |
| Script for steps only the human can do | mattpocock | **Take**: `request_user_action` already exists; add a generated checklist script for long ones | C21 |
| Fresh worktree per implementer | both | **Adapt**: DebCraft writes into a per-requirement workspace, so a builder gets its own folder under it (X2's write jail), not a git worktree | X2 |
| Brainstorm / grilling interview before building | both | **Skip**: DebCraft already has `propose_requirements` and `ask_user`; revisit only if the benchmark shows misunderstood requests | none |
| Issue-tracker integration (triage, labels, GitHub tickets) | mattpocock | **Skip** | none |
| A single "use the skills" bootstrap skill | superpowers | **Skip**: DebCraft pins a skills index every session | none |
| Skill evaluation / writing-skills guide | superpowers | **Later**: C13 and C14 | C13, C14 |

## What this unblocks
X2 (parallel builders, using the protocol above), X7 (planning graph and scheduler), C4, C6, C7, C13, C16, C19, C20, C21 and D7 are
no longer waiting for the study. Each still gets its own decision record and a measured before and after.

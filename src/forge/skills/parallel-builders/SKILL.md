---
name: parallel-builders
description: Use when one request has two or more independent pieces (design variants, screens, services, documents): build them at the same time with builders in separate folders, then verify each yourself
---

# Parallel builders

Use this when one request has two or more pieces that are **independent**: they can live in different folders, share no files and no
decisions, and none needs another's output. Typical: the three design variants, separate pages or screens of one site, several small
services, several documents. Do not use it for work that edits the same files, for one small task, or when the pieces depend on a design
you have not decided yet: decide that first, alone.

## Before you start
1. List the pieces and give each a **folder** of its own below the repository root (for example `designs/design-a`). No folder may be
   inside another. Shared files (a root `package.json`, lock files, the database schema, configuration, a shared component) are yours:
   make them first, or tell the builders to leave them alone.
2. Write a **brief** for each builder: one line on where the piece fits, the requirement in your words with the exact facts (names,
   numbers, texts), the interfaces or tokens it must follow (`DESIGN.md`, an API shape), what it must not touch, and how it should check
   its own work. A builder sees only its brief, not this conversation. Do not paste history.
3. Start the builders **in one turn**: several `spawn_subagent` calls with `agent: "builder"`, each with its own `folder` and a short `name`.
   At most three run at once (`limits.max_parallel_builders`; set to 1 to switch it off); more wait their turn.

## Let the plan do the scheduling (run_ready_tasks)
When you plan with `propose_plan`, give every task that could run alongside others a `folder` (where it writes) and, when it needs
something exclusive, `resources` (a fixed port, the database schema, a root `package.json`). Then call **`run_ready_tasks`**: it takes the
pending tasks whose dependencies are done, keeps only those that are provably independent (separate, non-overlapping folders, no shared
resource, at most `limits.max_parallel_builders`), builds each with its own builder at the same time and returns every report. A task
without a folder, or one that overlaps another, is never run in parallel; the answer names the reason, and you work on it yourself. Pass
facts a builder needs in `notes` (task id to text). Dependent tasks wait: call `run_ready_tasks` again after you have verified the
first group. The scheduler marks a BLOCKED or NEEDS_CONTEXT piece as blocked; the others stay in progress until **you** verify them
and call `task_update(done)`, which asks for a passing test run (and a look in a browser for pages) as for your own edits.

## A hard or ambiguous problem: candidate solutions (tests as the judge)
When a problem is hard (an algorithm with many edges, a bug you cannot pin down, a design with two plausible shapes) and you can write
down what a correct answer must satisfy, write that check first (a test file, a script, a list of cases). Then start two or three builders
in separate folders with the **same brief but different approaches** (for example "iterative with an explicit stack" and "recursive with
memoisation"), each told to make your check pass and to run it. Keep the candidate that passes the check and the review (`code-review`);
copy it into place yourself, discard the others, and say which you chose and why. Do not do this for easy work: it costs several runs.

## What a builder does
It writes only below its folder, works in its own shell session, takes its own free port, runs its own checks, stops what it started and
ends with one status. The report is saved to `.forge/builders/<name>-report.md` and a line goes to `.forge/builders/ledger.md` (it survives
a compaction: read it after one).

## The four statuses and your response
- **DONE**: do not take it on trust. Run its checks and look at it (tests, `browser_screenshot`, the verifier or the design critic) before
  you count it.
- **DONE_WITH_CONCERNS**: handle concerns about correctness or scope first, note the rest, then verify.
- **NEEDS_CONTEXT**: supply the missing fact in a new brief and start that builder again. Do not guess for it.
- **BLOCKED**: never retry unchanged. Add context, split the piece, change the brief, or do it yourself. A report with no status counts as BLOCKED.

## Fixing what is wrong
Findings go back to the builder in a new brief that names the finding and the file. At most **five rounds** per piece; after the fifth,
decide each open finding yourself: the check is wrong or contestable (park it and say why), real but nothing depends on it (defer it),
real and something depends on it (the smallest change that unblocks, then carry on). Say in your final message what you ruled and what a wrong
ruling would cost. Small findings do not start a round: list them as deferred.

## Finishing
Integrate the pieces yourself (links, shared files, the whole app running), run the full tests and the audit, have the design reviewed once
for the whole (not once per builder), and tell the user which pieces are done, which had concerns and what you ruled.

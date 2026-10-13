---
name: parallel-builders
description: Build independent pieces of one request at the same time with builder subagents, each in its own folder (design variants, separate screens, services, documents), then verify each result yourself
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

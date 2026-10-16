---
name: solution-thinking
description: Think like a product architect before building. Use when you are asked to build an application or a significant feature, especially one that supports a business process (approvals, requests, orders, cases, payments), and whenever the request leaves the users, the rules or the definition of success open.
---
# Solution thinking: understand the problem before you build the answer

A request names a solution ("build a web app for X"). The person has a problem ("our approvals are slow, nobody can see the status, audit takes days"). A correct solution to the named request that does not solve the problem is a failed task.
Spend a small, fixed effort on the thinking below, write it in one file (`ANALYSIS.md`, one to two pages, tables not essays), then build. A small, clear change needs none of this: say the objective and the check in two sentences and go.

## 1. The objective, the users, the success test
- The objective in one sentence, in the requester's words, and the problem behind it (what hurts today, how often, for whom).
- Every kind of person who touches the system, and for each one a **day in their life**: what they open first, what they are waiting for, what they chase, what they are afraid of getting wrong, what they do today instead (Excel, email, paper) and what that gets right that a new system must not lose.
- **Acceptance criteria**: five to ten sentences, each observable by someone who is not you ("a manager approving a request can see who else is away on those days", "the approver cannot approve a case they entered", "the reconciliation that took a week is one export"). They are what you will check at the end.
- Constraints you were given and the ones you assumed. Mark each assumption as such.
- **The pain-point trace.** Copy every complaint about the business problem in the requester's own words (constraints such as the stack, the start command or fictional data are not complaints; leave them out of this table) ("we run out of fast-moving items", "nobody is confident the numbers are right", "audit takes days") and, beside each, the scope item that answers it. A complaint with no item is a defect in the plan: either add the item or say in the ledger why it is left out and what that risks. Do this before anything else, because the headline complaints are what the requester will judge the result by.
- **The expert pass.** Name the domain (leave management, retail lending, procure-to-pay). Then write a table with these six rows and at least two items **specific to this domain** in each, that someone who has run the process for ten years would insist on and the requester did not say: (1) controls and limits (who may approve what, separation of duties); (2) standard checks and documents; (3) regulatory or policy duties; (4) standard reference data (calendars, rate or price bands, units, tolerances, reason codes); (5) the usual exceptions; (6) the numbers each role will be measured on. "Audit trail" or "role-based access" alone is not an item: say what is recorded or which rule applies. Each item then goes into the scope ledger with a class. A prototype or a demo limits how deep the **build** goes, never what the analysis names: name it, then let the ledger decide (Essential, High-value, or Optional with the risk of leaving it out). This is where a good plan differs from a restated request.

## 2. The process, as states and hand-offs (for anything that moves through people)
- The states a record passes through, who owns it in each state, what moves it on, and every way back: send back, reject, withdraw, expire, escalate, reopen, cancel after the fact, delegate while someone is away.
- For each state: what the owner sees to decide (the context, not just the record), what they can do, what the next owner sees, how long it may sit (deadline, ageing) and what happens when it sits too long.
- Who may do what: a role matrix. Where money or personal data moves, two different people (maker and checker); nobody approves their own work; limits by role; what each role cannot see.

## 3. Data and rules
- The fields the domain needs, with units, currency, time zone, valid ranges and what makes a record unique (what a duplicate is). History: who changed what, when and why, kept, not overwritten.
- Rules that the business will want to change (limits, tolerances, entitlements, accrual, policy bands, holiday calendars) are **data an administrator edits**, not constants in code. Say what happens when a rule blocks someone: the message tells them which rule and what to do.
- Money, time and quantity are where numbers go wrong: rounding rules, partial amounts, part days, units of measure, time zones, year boundaries, calendars that differ by place.

## 4. What the real world does to the process (scenarios)
Think of the awkward cases the way someone who has run this process for ten years would, then list them in a table with a decision for each: **handled** (and how), **deferred** (and why it is safe to defer), or **out of scope** (and who is told). Cover at least: the same thing entered twice; a partial or late or wrong input; a change after approval; someone absent; two people acting on one record at once; a rule that has an exception; a record that crosses a period boundary (month end, year end, cut-off); a bulk case (many at once); a correction after the fact; a person who leaves or joins; data from before the system existed (migration).
Name the first-week problems: what will the first real user hit that the happy path hides (an empty screen, an unknown term, a number that does not match their Excel)?

## 5. Value decisions: the scope ledger
List what you would build in a short table: item, the user need it serves, the benefit, the cost to build and keep, the downside, and its class.
- **Essential**: the objective fails without it. Build it.
- **High-value**: it clearly improves correctness, reliability, safety or usability for a named user and costs little next to the benefit. Build it, and say why in the ledger.
- **Optional**: nice, common in similar tools, or technically possible. Do **not** build it; list it for the user in the final report.
Test every item that is not Essential: *would the application work equally well without it?* If yes, it is Optional. "Similar products have it" is not a need. Prefer the smallest complete solution; reuse what exists (the framework's feature, an existing component, a library already installed) before writing new code. Do not add a setting, a role, a screen or a table that no scenario above needs.

## 6. Then build, and check against section 1
- Build in vertical slices (one complete path through the process, then the next), not layer by layer. Seed data is realistic and includes the awkward cases from section 4, so the screens show real states.
- Tests check the **rules** (the limits, the transitions, who may do what, the arithmetic, the duplicate case), not only that a page loads.
- Before you say you are finished, walk the acceptance criteria one by one in the running application, as the person in each role would, with real clicks, and write what you saw. A criterion you could not check is reported as unchecked, not as met.
- The final report states: what was built and checked; the assumptions you made; what you deliberately left out (the Optional items and deferred scenarios) and why; the known limits; and what the user should look at first.

## ANALYSIS.md skeleton
```
# <name>: analysis
## Objective and problem
## People and their day            (role | what they do | what they chase | today they use)
## Acceptance criteria             (numbered, observable)
## Process                         (states, owners, transitions, ways back, deadlines)
## Roles and limits                (role | can | cannot | limit)
## Data and rules                  (entities and key fields; rules kept as data)
## Scenarios                       (case | decision: handled / deferred / out | how or why)
## Scope ledger                    (item | need | benefit | cost | downside | Essential / High-value / Optional)
## Assumptions and open points
```

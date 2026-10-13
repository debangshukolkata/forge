---
name: project-docs
description: Use in a project that will take more than one session or has its own domain vocabulary or notable design choices - keep a short glossary and brief decision records so the next session and the user are not lost
---

# A glossary and light decision records

For a small one-off script none of this is needed. For a project with its own terms (invoice, claim, tenant, run) or several sessions,
keep two small files in the project and read them first when you resume.

## docs/GLOSSARY.md
- One short entry per term the project uses: the **word as it appears in code and messages**, one sentence of meaning, and what it is
  *not* if people confuse it with something else.
- Create it when the first term needs defining; update it as terms are settled, not in a batch at the end.
- Use the glossary's words in names, tests, comments and what you say to the user. Do not keep two words for one thing.
- Terms only; no implementation details, no decisions, no to-do items.

## docs/decisions/NNNN-short-title.md
Write a record only when all three are true: the choice is **hard to reverse**, a future reader would be **surprised** without context,
and there was a **real trade-off** (genuine alternatives and a reason). Otherwise skip it. Keep a record to a few lines: the decision, the
options you considered, why this one, and what would make you revisit it. Number them in order. You decide and write it down; do not stop
to interview the user (ask only if a missing fact blocks the work).

## Keep the pieces apart
- Project state for the next session (what is done, what is next) belongs in the task list and the handoff note, not here.
- Instructions for DebCraft belong in `FORGE.md`.
- The README is for users of the project; the glossary and decisions are for its maintainers.

## Gotchas
- A glossary that restates the code (every class name) is noise: only the words people could misread.
- A decision record written after the fact still helps; write it as soon as you notice you made the choice.

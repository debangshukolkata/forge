# context

Keeps each model request inside the context window: budget, pinned context, compaction.

- **Depends on:** config, llm
- **Invariants:** Tool call/result pairs are never split by compaction.
- **Tests:** test_context.py, test_live_context.py
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.

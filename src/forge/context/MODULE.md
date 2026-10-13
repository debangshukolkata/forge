# context

Keeps each model request inside the context window: budget, pinned context, compaction.

- **Depends on:** config, llm, safety
- **Invariants:** Tool call/result pairs are never split by compaction.
- **Tests:** test_context.py, test_live_context.py
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
- **Usage warnings (D-298):** `warnings.py` decides when the user is told the context is filling up (`context.warn_at` 0.7 and `warn_again_at` 0.9 of the usable window, once per level); the agent loop publishes it as a `context_warning` notice. Tests: test_context_warnings.py.

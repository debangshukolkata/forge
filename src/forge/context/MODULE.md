# context

Keeps each model request inside the context window: budget, pinned context, compaction.

- **Depends on:** config, llm, safety
- **Invariants:** Tool call/result pairs are never split by compaction.
- **Tests:** test_context.py, test_live_context.py
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
- **Usage warnings (D-298):** `warnings.py` decides when the user is told the context is filling up (`context.warn_at` 0.7 and `warn_again_at` 0.9 of the usable window, once per level); the agent loop publishes it as a `context_warning` notice. Tests: test_context_warnings.py.
- **Facts-only fallback (D-467):** when the model's summary is incomplete twice, `fallback_summary` builds one in code (requests, files, plan, todo list, last assistant text) instead of keeping the whole history; every summary also has an "Assumptions to verify" section.

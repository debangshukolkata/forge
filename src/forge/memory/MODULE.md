# memory

Cross-repository user memory (preferences).

- **Depends on:** safety
- **Invariants:** Stored under Forge home only.
- **Tests:** test_m10_tools.py
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.

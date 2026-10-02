# workspace

The per-requirement workspace: copy, baseline manifest, the single write gate (jail + checkpoint), output/ builder, checkpoints, Python/Node environment detection.

- **Depends on:** errors, safety
- **Invariants:** Every write goes through Workspace (safety invariant 1). Preserve BOM and line endings.
- **Tests:** test_agent_loop.py, test_angular_ladder.py, test_context.py, test_contracts.py, test_db.py, test_diagnose.py, test_frontend_setup.py, test_frontend_smoke.py (+30 more)
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
